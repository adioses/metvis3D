"""Prepara, abre y renderiza animaciones meteorológicas con Met.3D."""

from __future__ import annotations

import math
import os
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from netCDF4 import Dataset, num2date


XVFB_SERVER_ARGUMENTS = "-screen 0 1920x1080x24 +extension GLX +render -noreset"


def load_yaml_configuration(configuration_file: Path, description: str) -> dict:
    """Lee una configuración YAML y detiene el flujo si no es un mapa."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración {description}: {configuration_file}")

    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)

    if not isinstance(configuration, dict):
        raise RuntimeError(f"La configuración {description} debe contener claves YAML: {configuration_file}")
    return configuration


def require_value(configuration: dict, path: tuple[str, ...], description: str) -> object:
    """Obtiene un valor obligatorio e informa su ruta científica si falta."""

    current: object = configuration
    for key in path:
        if not isinstance(current, dict) or key not in current:
            joined_path = ".".join(path)
            raise RuntimeError(f"Falta '{joined_path}' en la configuración {description}.")
        current = current[key]
    return current


def read_netcdf_metadata(netcdf_file: Path, required_variables: list[str], product_name: str) -> dict:
    """Lee metadatos, variables y tiempos que determinan la animación."""

    if not netcdf_file.exists():
        raise RuntimeError(f"No existe el NetCDF estandarizado: {netcdf_file}")

    with Dataset(netcdf_file) as dataset:
        missing_attributes = [name for name in ("center", "model", "forecast_date") if not hasattr(dataset, name)]
        if missing_attributes:
            raise RuntimeError(
                f"El NetCDF {netcdf_file.name} no declara los metadatos requeridos: {', '.join(missing_attributes)}."
            )

        missing_variables = [name for name in required_variables if name not in dataset.variables]
        if missing_variables:
            raise RuntimeError(
                f"El NetCDF {netcdf_file.name} no contiene las variables requeridas por {product_name}: "
                f"{', '.join(missing_variables)}."
            )

        if "time" not in dataset.variables:
            raise RuntimeError(f"El NetCDF {netcdf_file.name} no contiene la coordenada temporal 'time'.")

        time_coordinate = dataset.variables["time"]
        time_values = time_coordinate[:]
        if len(time_values) < 2:
            raise RuntimeError(
                f"El NetCDF {netcdf_file.name} requiere al menos dos tiempos para generar una animación."
            )
        if not hasattr(time_coordinate, "units"):
            raise RuntimeError(f"La coordenada 'time' de {netcdf_file.name} no declara unidades.")

        valid_times = num2date(time_values, time_coordinate.units, only_use_cftime_datetimes=False)
        return {
            "center": str(dataset.center).strip().lower(),
            "model": str(dataset.model).strip().lower(),
            "forecast_date": datetime.fromisoformat(str(dataset.forecast_date)),
            "valid_times": list(valid_times),
        }


def build_timeline(animation: dict, metadata: dict, product_name: str) -> dict:
    """Convierte la selección temporal declarada a los parámetros batch de Met.3D."""

    timeline = require_value(animation, ("timeline",), f"de animación {product_name}")
    if not isinstance(timeline, dict):
        raise RuntimeError("La sección 'timeline' debe ser un mapa YAML.")

    selection = require_value(timeline, ("selection",), f"de animación {product_name}")
    valid_times = metadata["valid_times"]
    available_seconds = int((valid_times[-1] - valid_times[0]).total_seconds())
    step_seconds = int((valid_times[1] - valid_times[0]).total_seconds())
    if step_seconds <= 0:
        raise RuntimeError("Los dos primeros tiempos del NetCDF no permiten avanzar la animación.")

    if selection == "all_available":
        range_seconds = available_seconds
    elif selection == "first_hours":
        maximum_hours = require_value(timeline, ("max_forecast_hours",), f"de animación {product_name}")
        range_seconds = min(available_seconds, int(float(maximum_hours) * 3600))
    else:
        raise RuntimeError("timeline.selection debe ser 'all_available' o 'first_hours'.")

    return {"range_seconds": range_seconds, "step_seconds": step_seconds}


def create_runtime_directory(project_root: Path, model_identifier: str) -> Path:
    """Limpia solamente el runtime transitorio del modelo que se ejecutará."""

    model_slug = re.sub(r"[^a-z0-9-]+", "-", model_identifier.lower()).strip("-")
    if not model_slug:
        raise RuntimeError("No se pudo construir el identificador de modelo para el runtime Met.3D.")

    runtime_root = project_root / "met3D" / ".runtime"
    runtime_directory = runtime_root / model_slug
    if runtime_directory.exists():
        shutil.rmtree(runtime_directory)
    runtime_directory.mkdir(parents=True)
    return runtime_directory


def encode_qrectf_variant(west: float, south: float, width: float, height: float) -> str:
    """Serializa un QRectF para QSettings sin exponer su codificación en YAML."""

    encoded_rectangle = struct.pack(">I4d", 20, float(west), float(south), float(width), float(height))
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_rectangle)
    return f"@Variant({escaped_bytes})"


def encode_saved_views_variant(number_of_views: int) -> str:
    """Serializa los índices de vistas que Met.3D debe capturar en batch."""

    if number_of_views < 1:
        raise RuntimeError("La sesión base no contiene vistas para capturar.")
    encoded_views = struct.pack(">II", 9, number_of_views)
    encoded_views += b"".join(struct.pack(">II", 2, view_index) for view_index in range(number_of_views))
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_views)
    return f"@Variant({escaped_bytes})"


def render_template(template_environment: Environment, template_name: str, output_file: Path, context: dict) -> Path:
    """Genera una configuración nativa de Met.3D desde una plantilla Jinja."""

    rendered = template_environment.get_template(template_name).render(context)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(f"{rendered.rstrip()}\n", encoding="utf-8")
    return output_file


def create_camera_orbit(camera: dict, scene: dict, timeline: dict, sequence_file: Path, product_name: str) -> Path:
    """Construye una órbita de cámara alrededor del centro de la escena."""

    orbit = require_value(camera, ("orbit",), f"de cámara de {product_name}")
    zoom = float(require_value(orbit, ("zoom_factor",), f"de cámara de {product_name}"))
    zoom_fraction = float(require_value(orbit, ("zoom_fraction",), f"de cámara de {product_name}"))
    tension = float(require_value(orbit, ("tension",), f"de cámara de {product_name}"))
    target_z = float(require_value(orbit, ("target_world_z",), f"de cámara de {product_name}"))
    if not 0 < zoom <= 1 or not 0 < zoom_fraction < 1 or not -1 <= tension <= 1:
        raise RuntimeError(f"La órbita de {product_name} requiere zoom_factor en (0, 1], zoom_fraction en (0, 1) y tension entre -1 y 1.")
    origin = camera["origin"]
    y_axis = camera["y_axis"]
    z_axis = camera["z_axis"]
    center_lon = (float(scene["area"]["west"]) + float(scene["area"]["east"])) / 2
    center_lat = (float(scene["area"]["south"]) + float(scene["area"]["north"])) / 2
    offset_lon = float(origin["longitude"]) - center_lon
    offset_lat = float(origin["latitude"]) - center_lat
    yaw = math.degrees(math.atan2(-float(z_axis["longitude"]), float(z_axis["latitude"])))
    pitch = math.degrees(math.atan2(float(y_axis["world_z"]), -float(z_axis["world_z"])))
    target_yaw = math.degrees(math.atan2(offset_lon, -offset_lat))
    yaw_difference = (target_yaw - yaw + 180) % 360 - 180
    target_pitch = math.degrees(math.atan2(float(origin["world_z"]) - target_z, math.hypot(offset_lon, offset_lat)))
    yaw_radians = math.radians(yaw)
    roll = math.degrees(math.atan2(
        float(y_axis["longitude"]) * math.cos(yaw_radians) + float(y_axis["latitude"]) * math.sin(yaw_radians),
        math.hypot(float(y_axis["world_z"]), float(z_axis["world_z"])),
    ))
    sequence = ET.Element("CameraSequence", name=f"{product_name} orbit", tension=str(tension))
    # Cada punto corresponde a un plazo; el giro comienza después del acercamiento.
    intervals = timeline["range_seconds"] // timeline["step_seconds"]
    if intervals < 2:
        raise RuntimeError(f"La órbita de {product_name} requiere al menos tres plazos para el acercamiento y el giro.")
    for index in range(intervals + 1):
        progress = index / intervals
        angle = 2 * math.pi * max(0.0, (progress - zoom_fraction) / (1 - zoom_fraction))
        zoom_progress = min(1.0, progress / zoom_fraction)
        scale = 1 - (1 - zoom) * zoom_progress
        lon = center_lon + scale * (offset_lon * math.cos(angle) - offset_lat * math.sin(angle))
        lat = center_lat + scale * (offset_lon * math.sin(angle) + offset_lat * math.cos(angle))
        z = target_z + scale * (float(origin["world_z"]) - target_z)
        ET.SubElement(sequence, "SequenceKey", {
            "label": str(index), "lon": str(lon), "lat": str(lat), "z": str(z),
            "pitch": str(pitch + (target_pitch - pitch) * zoom_progress),
            "yaw": str(yaw + yaw_difference * zoom_progress + math.degrees(angle)),
            "roll": str(roll * (1 - zoom_progress)),
            "advanceTimestep": "0", "isOrthographic": "0", "transition": "1",
        })
    ET.indent(sequence, space="  ")
    sequence_file.write_text('<!DOCTYPE CameraSequence>\n' + ET.tostring(sequence, encoding="unicode") + '\n', encoding="utf-8")
    return sequence_file


def prepare_runtime_session(
    session_source_file: Path,
    runtime_directory: Path,
    frames_directory: Path,
    animation: dict,
    for_render: bool,
    timeline: dict,
) -> Path:
    """Copia la sesión base y aplica cámara, resolución y directorio temporal."""

    if not session_source_file.exists():
        raise RuntimeError(
            f"No existe la sesión base: {session_source_file}."
        )

    animation_name = str(require_value(animation, ("name",), "de animación Met.3D"))
    runtime_session_file = runtime_directory / f"{animation_name}.session.config"
    shutil.copy2(session_source_file, runtime_session_file)

    camera = require_value(animation, ("camera",), f"de animación {animation_name}")
    output = require_value(animation, ("output",), f"de animación {animation_name}")
    if not isinstance(camera, dict) or not isinstance(output, dict):
        raise RuntimeError(f"La cámara y la salida de {animation_name} deben ser mapas YAML.")

    session_settings = {
        "MSceneViews\\MSceneView_0\\MCamera\\origin_lon": require_value(camera, ("origin", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\origin_lat": require_value(camera, ("origin", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\origin_worldZ": require_value(camera, ("origin", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_lon": require_value(camera, ("y_axis", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_lat": require_value(camera, ("y_axis", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_worldZ": require_value(camera, ("y_axis", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_lon": require_value(camera, ("z_axis", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_lat": require_value(camera, ("z_axis", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_worldZ": require_value(camera, ("z_axis", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\custom_resolution_width": require_value(output, ("width_px",), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\custom_resolution_height": require_value(output, ("height_px",), f"de animación {animation_name}"),
        "Animation\\save_directory": frames_directory.resolve(),
    }
    orbit = camera.get("orbit")
    if orbit and orbit.get("enabled"):
        session_settings["Animation\\cam_runtime_seconds"] = timeline["range_seconds"] // timeline["step_seconds"]
        session_settings["Animation\\delay_ms"] = 500
        session_settings["Animation\\advance_type"] = 0
        session_settings["Animation\\advance_interval"] = 2

    session_lines = runtime_session_file.read_text(encoding="utf-8").splitlines(keepends=True)
    settings_found = {setting: False for setting in session_settings}
    for line_index, line in enumerate(session_lines):
        for setting, value in session_settings.items():
            if line.startswith(f"{setting}="):
                ending = "\n" if line.endswith("\n") else ""
                session_lines[line_index] = f"{setting}={value}{ending}"
                settings_found[setting] = True
                break
    missing_settings = [setting for setting, found in settings_found.items() if not found]
    if missing_settings:
        raise RuntimeError(
            f"La sesión base {session_source_file.name} no contiene: {', '.join(missing_settings)}."
        )

    if not for_render:
        runtime_session_file.write_text("".join(session_lines), encoding="utf-8")
        return runtime_session_file

    saved_images_setting = "Animation\\save_images=false"
    session_text = "".join(session_lines)
    if saved_images_setting not in session_text:
        raise RuntimeError(f"La sesión base {session_source_file.name} no contiene 'Animation\\save_images'.")
    session_text = session_text.replace(saved_images_setting, "Animation\\save_images=true", 1)
    number_of_views = None
    for line in session_text.splitlines():
        if line.startswith("MSceneViews\\numSceneViews="):
            number_of_views = int(line.partition("=")[2])
            break
    if number_of_views is None:
        raise RuntimeError(f"La sesión base {session_source_file.name} no declara sus vistas de escena.")

    saved_views_prefix = "Animation\\saved_views="
    session_lines = session_text.splitlines(keepends=True)
    for line_index, line in enumerate(session_lines):
        if line.startswith(saved_views_prefix):
            ending = "\n" if line.endswith("\n") else ""
            session_lines[line_index] = f"{saved_views_prefix}{encode_saved_views_variant(number_of_views)}{ending}"
            break
    else:
        raise RuntimeError(f"La sesión base {session_source_file.name} no contiene el ajuste 'Animation\\saved_views'.")

    runtime_session_file.write_text("".join(session_lines), encoding="utf-8")
    return runtime_session_file


def get_enabled_object(objects: dict, object_name: str, product_name: str) -> dict | None:
    """Obtiene un objeto de producto sólo cuando su YAML lo habilita."""

    configuration = objects.get(object_name)
    if configuration is None:
        return None
    if not isinstance(configuration, dict):
        raise RuntimeError(f"El objeto '{object_name}' de {product_name} debe ser un mapa YAML.")
    enabled = require_value(configuration, ("enabled",), f"del objeto {object_name} de {product_name}")
    return configuration if enabled is True else None


def prepare_animation(
    project_root: Path,
    animation_file: Path,
    netcdf_file: Path,
    for_render: bool = False,
) -> dict[str, object]:
    """Materializa los archivos temporales de una animación Met.3D completa."""

    # Leer configuración meteorológica y geometría estática.
    animation = load_yaml_configuration(animation_file, "de animación Met.3D")
    product_name = str(require_value(animation, ("name",), "de animación Met.3D"))
    scene_relative = require_value(animation, ("scene",), f"de animación {product_name}")
    scene = load_yaml_configuration(project_root / str(scene_relative), "de escena Met.3D")
    variables = require_value(animation, ("variables",), f"de animación {product_name}")
    if not isinstance(variables, dict):
        raise RuntimeError(f"La sección 'variables' de {product_name} debe ser un mapa YAML.")
    objects = require_value(animation, ("objects",), f"de animación {product_name}")
    if not isinstance(objects, dict):
        raise RuntimeError(f"La sección 'objects' de {product_name} debe ser un mapa YAML.")

    surface_pressure = get_enabled_object(objects, "surface_pressure", product_name)
    potential_vorticity = get_enabled_object(objects, "potential_vorticity", product_name)
    horizontal_section = get_enabled_object(objects, "horizontal_section", product_name)
    jet = get_enabled_object(objects, "jet", product_name)
    if potential_vorticity is None and jet is None:
        raise RuntimeError(f"La animación {product_name} debe habilitar al menos un objeto tridimensional.")

    required_variables: list[str] = []
    derived_variable_mappings: list[str] = []
    if potential_vorticity is not None:
        for variable_name in ("air_temperature", "wind_u", "wind_v"):
            required_variables.append(str(require_value(variables, (variable_name,), f"de animación {product_name}")))
        derived_variable_mappings.extend(
            [
                f"eastward_wind:{variables['wind_u']}",
                f"northward_wind:{variables['wind_v']}",
                f"air_temperature:{variables['air_temperature']}",
            ]
        )
        require_value(potential_vorticity, ("pressure", "bottom_hpa"), f"del objeto PV de {product_name}")
        require_value(potential_vorticity, ("pressure", "top_hpa"), f"del objeto PV de {product_name}")
        require_value(potential_vorticity, ("isosurface_pvu",), f"del objeto PV de {product_name}")
        opacity = float(require_value(potential_vorticity, ("opacity",), f"del objeto PV de {product_name}"))
        if not 0.0 <= opacity <= 1.0:
            raise RuntimeError(f"La opacidad de la isosuperficie de PV de {product_name} debe estar entre 0 y 1.")
    if jet is not None:
        for variable_name in ("wind_u", "wind_v"):
            variable = str(require_value(variables, (variable_name,), f"de animación {product_name}"))
            required_variables.append(variable)
        if not any(mapping.startswith("eastward_wind:") for mapping in derived_variable_mappings):
            derived_variable_mappings.extend(
                [
                    f"eastward_wind:{variables['wind_u']}",
                    f"northward_wind:{variables['wind_v']}",
                ]
            )
        require_value(jet, ("pressure", "bottom_hpa"), f"del objeto jet de {product_name}")
        require_value(jet, ("pressure", "top_hpa"), f"del objeto jet de {product_name}")
        require_value(jet, ("wind_speed_isosurface_m_s",), f"del objeto jet de {product_name}")
    if surface_pressure is not None:
        surface_pressure_variable = str(require_value(variables, ("surface_pressure",), f"de animación {product_name}"))
        required_variables.append(surface_pressure_variable)
        derived_variable_mappings.append(f"surface_air_pressure:{surface_pressure_variable}")
    if horizontal_section is not None:
        if potential_vorticity is None:
            raise RuntimeError(f"La sección horizontal de {product_name} requiere la PV habilitada.")
        for key in ("pressure_hpa", "potential_vorticity", "wind", "geopotential_height"):
            require_value(horizontal_section, (key,), f"de la sección horizontal de {product_name}")
        geopotential_height = horizontal_section["geopotential_height"]
        if require_value(geopotential_height, ("enabled",), f"de geopotencial de {product_name}"):
            required_variables.append(str(require_value(variables, ("geopotential_height",), f"de animación {product_name}")))
    require_value(animation, ("camera",), f"de animación {product_name}")

    # Revisar la corrida NetCDF y derivar su identidad, fecha y duración.
    metadata = read_netcdf_metadata(netcdf_file, list(dict.fromkeys(required_variables)), product_name)
    model_identifier = f"{metadata['center']}-{metadata['model']}"
    timeline = build_timeline(animation, metadata, product_name)
    camera_orbit = animation["camera"].get("orbit")
    if camera_orbit and camera_orbit.get("enabled"):
        valid_times = metadata["valid_times"]
        for earlier, later in zip(valid_times, valid_times[1:]):
            if (later - valid_times[0]).total_seconds() > timeline["range_seconds"]:
                break
            if (later - earlier).total_seconds() != timeline["step_seconds"]:
                raise RuntimeError(
                    f"{model_identifier}, {netcdf_file.name}: la órbita requiere plazos regulares; "
                    f"entre {earlier} y {later} no se conserva el intervalo inicial."
                )
    if horizontal_section is not None:
        requested_pressure = float(horizontal_section["pressure_hpa"])
        with Dataset(netcdf_file) as dataset:
            if "lev" not in dataset.variables or getattr(dataset["lev"], "units", "") != "millibars":
                raise RuntimeError(f"El NetCDF {netcdf_file.name} de {model_identifier} requiere lev en millibars.")
            pressure_levels = [float(value) for value in dataset["lev"][:]]
            if not pressure_levels:
                raise RuntimeError(f"El NetCDF {netcdf_file.name} de {model_identifier} no contiene niveles de presión.")
            pressure_hpa = min(pressure_levels, key=lambda level: (abs(level - requested_pressure), -level))
            level_index = pressure_levels.index(pressure_hpa)
            if not float(scene["view_pressure"]["top_hpa"]) <= pressure_hpa <= float(scene["view_pressure"]["bottom_hpa"]):
                raise RuntimeError(f"{model_identifier}, {netcdf_file.name}: el nivel {pressure_hpa:g} hPa queda fuera de la escena {product_name}.")
            section_variables = [str(variables[key]) for key in ("air_temperature", "wind_u", "wind_v")]
            if horizontal_section["geopotential_height"]["enabled"]:
                section_variables.append(str(variables["geopotential_height"]))
            for variable_name in section_variables:
                variable = dataset[variable_name]
                if variable.dimensions != ("time", "lev", "latitude", "longitude"):
                    raise RuntimeError(f"{model_identifier}, {netcdf_file.name}: {variable_name} no tiene dimensiones isobáricas canónicas.")
                if horizontal_section["geopotential_height"]["enabled"] and variable_name == variables["geopotential_height"] and getattr(variable, "units", "") != "gpm":
                    raise RuntimeError(f"{model_identifier}, {netcdf_file.name}: {variable_name} requiere unidades gpm para los contornos.")
                for time_index, valid_time in enumerate(metadata["valid_times"]):
                    if (valid_time - metadata["valid_times"][0]).total_seconds() > timeline["range_seconds"]:
                        break
                    field = variable[time_index, level_index, :, :]
                    if hasattr(field, "mask") and field.mask is not False and field.mask.all():
                        raise RuntimeError(f"{model_identifier}, {netcdf_file.name}: {variable_name} sin datos a {pressure_hpa:g} hPa, tiempo {valid_time}.")
        horizontal_section["effective_pressure_hpa"] = pressure_hpa
        print(f"Sección horizontal {model_identifier}, {netcdf_file.name}: nivel solicitado {requested_pressure:g} hPa; nivel utilizado {pressure_hpa:g} hPa.")
    runtime_directory = create_runtime_directory(project_root, model_identifier)

    # Completar geometría derivada sin ocultar los valores declarados en YAML.
    area = require_value(scene, ("area",), "de escena Met.3D")
    if not isinstance(area, dict):
        raise RuntimeError("La sección 'area' de la escena Met.3D debe ser un mapa YAML.")
    require_value(scene, ("title",), "de escena Met.3D")
    for coordinate in ("west", "south", "east", "north"):
        require_value(scene, ("area", coordinate), "de escena Met.3D")
    scene["area"]["width"] = float(scene["area"]["east"]) - float(scene["area"]["west"])
    scene["area"]["height"] = float(scene["area"]["north"]) - float(scene["area"]["south"])
    if scene["area"]["width"] <= 0 or scene["area"]["height"] <= 0:
        raise RuntimeError("El área Met.3D debe cumplir west < east y south < north.")
    scene["area"]["horizontal2d_coords"] = encode_qrectf_variant(
        scene["area"]["west"],
        scene["area"]["south"],
        scene["area"]["width"],
        scene["area"]["height"],
    )
    scene["bounding_boxes"] = {"scene": f"{scene['name']}_scene"}
    object_bounding_boxes: list[dict] = []
    for object_name, configuration in (("potential_vorticity", potential_vorticity), ("jet", jet)):
        if configuration is None:
            continue
        pressure = require_value(configuration, ("pressure",), f"del objeto {object_name} de {product_name}")
        if not isinstance(pressure, dict):
            raise RuntimeError(f"La presión del objeto {object_name} de {product_name} debe ser un mapa YAML.")
        bottom_hpa = float(require_value(pressure, ("bottom_hpa",), f"del objeto {object_name} de {product_name}"))
        top_hpa = float(require_value(pressure, ("top_hpa",), f"del objeto {object_name} de {product_name}"))
        if bottom_hpa <= top_hpa:
            raise RuntimeError(f"El objeto {object_name} de {product_name} debe cumplir bottom_hpa > top_hpa.")
        if bottom_hpa > float(scene["view_pressure"]["bottom_hpa"]) or top_hpa < float(scene["view_pressure"]["top_hpa"]):
            raise RuntimeError(
                f"El intervalo {bottom_hpa:g}--{top_hpa:g} hPa de {object_name} excede la escena "
                f"{scene['view_pressure']['bottom_hpa']:g}--{scene['view_pressure']['top_hpa']:g} hPa."
            )
        bounding_box = {
            "name": f"{scene['name']}_{object_name}",
            "pressure": pressure,
            "index": len(object_bounding_boxes) + 2,
        }
        object_bounding_boxes.append(bounding_box)
        scene["bounding_boxes"][object_name] = bounding_box["name"]
        configuration["bounding_box_index"] = bounding_box["index"]

    # Renderizar configuraciones de escena, objetos y modo batch.
    template_directory = project_root / "met3D" / "templates"
    template_environment = Environment(
        loader=FileSystemLoader(template_directory),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    dataset_name = str(require_value(animation, ("dataset_name",), f"de animación {product_name}"))
    session_source_file = project_root / str(require_value(animation, ("session_file",), f"de animación {product_name}"))
    frames_directory = runtime_directory / "frames"
    frames_directory.mkdir()
    session_file = prepare_runtime_session(
        session_source_file,
        runtime_directory,
        frames_directory,
        animation,
        for_render,
        timeline,
    )
    context = {
        "dataset_name": dataset_name,
        "netcdf_directory": netcdf_file.parent.resolve(),
        "netcdf_filename": netcdf_file.name,
        "variables": variables,
        "scene": scene,
        "derived_variable_mappings": derived_variable_mappings,
        "object_bounding_boxes": object_bounding_boxes,
        "potential_vorticity": potential_vorticity,
        "horizontal_section": horizontal_section,
        "jet": jet,
        "timeline": timeline,
        "frames_directory": frames_directory.resolve(),
        "session_file": session_file.resolve() if session_file.exists() else "",
        "bounding_boxes_file": (runtime_directory / "bounding_boxes.bbox.conf").resolve(),
    }

    camera_sequence = None
    if camera_orbit is not None and require_value(camera_orbit, ("enabled",), f"de cámara de {product_name}"):
        camera_sequence = create_camera_orbit(animation["camera"], scene, timeline, runtime_directory / "camera_sequence.xml", product_name)
    context["camera_sequence"] = camera_sequence

    files = {
        "dataset": render_template(template_environment, "dataset.dataset.conf.j2", runtime_directory / "dataset.dataset.conf", context),
        "bounding_boxes": render_template(template_environment, "bounding_boxes.bbox.conf.j2", runtime_directory / "bounding_boxes.bbox.conf", context),
        "basemap": render_template(template_environment, "basemap.actor.conf.j2", runtime_directory / "basemap.actor.conf", context),
        "volume": render_template(template_environment, "volume_bounding_box.actor.conf.j2", runtime_directory / "volume_bounding_box.actor.conf", context),
        "batch": render_template(template_environment, "batch_mode.batch.conf.j2", runtime_directory / "batch_mode.batch.conf", context),
    }
    if camera_sequence is not None:
        files["camera_sequence"] = camera_sequence
    actor_files = [files[name] for name in ("basemap", "volume")]
    if surface_pressure is not None:
        files["surface_pressure"] = render_template(
            template_environment,
            "surface_pressure.actor.conf.j2",
            runtime_directory / "surface_pressure.actor.conf",
            context,
        )
        actor_files.append(files["surface_pressure"])
    if potential_vorticity is not None:
        context["pv_isovalue_si"] = f"{float(potential_vorticity['isosurface_pvu']) * 1e-6:.8g}"
        opacity_byte = round(float(potential_vorticity["opacity"]) * 255)
        context["pv_isosurface_colour"] = (
            f"@Variant(\\0\\0\\0\\x43\\x1\\x{opacity_byte:02x}\\x{opacity_byte:02x}"
            "\\x75\\x75\\x5f\\x5f\\xd6\\xd6\\0\\0)"
        )
        files["potential_vorticity"] = render_template(
            template_environment,
            "potential_vorticity.actor.conf.j2",
            runtime_directory / "potential_vorticity.actor.conf",
            context,
        )
        actor_files.append(files["potential_vorticity"])
    if horizontal_section is not None:
        pv = horizontal_section["potential_vorticity"]
        for key in ("minimum_pvu", "maximum_pvu", "colour_steps", "hue", "dark_luminance", "light_luminance", "chroma"):
            require_value(pv, (key,), f"de PV en la sección horizontal de {product_name}")
        if float(pv["minimum_pvu"]) >= float(pv["maximum_pvu"]):
            raise RuntimeError(f"El mínimo de PV debe ser menor que el máximo en {product_name}.")
        wind = horizontal_section["wind"]
        for key in ("spacing_degrees", "min_length_degrees", "max_length_degrees", "line_width"):
            require_value(wind, (key,), f"del viento en la sección horizontal de {product_name}")
        if horizontal_section["geopotential_height"]["enabled"]:
            for key in ("minimum_gpm", "maximum_gpm", "interval_gpm"):
                require_value(horizontal_section["geopotential_height"], (key,), f"de geopotencial en {product_name}")
        files["pv_colourbar"] = render_template(template_environment, "horizontal_pv_colourbar.actor.conf.j2", runtime_directory / "horizontal_pv_colourbar.actor.conf", context)
        files["horizontal_section"] = render_template(template_environment, "horizontal_section.actor.conf.j2", runtime_directory / "horizontal_section.actor.conf", context)
        actor_files.extend((files["pv_colourbar"], files["horizontal_section"]))
    if jet is not None:
        files["jet"] = render_template(
            template_environment,
            "jet.actor.conf.j2",
            runtime_directory / "jet.actor.conf",
            context,
        )
        actor_files.append(files["jet"])
    context["session_file"] = session_file.resolve() if session_file.exists() else ""
    files["preferences"] = render_template(
        template_environment,
        "met3d.ini.j2",
        runtime_directory / "config" / "met3d" / "met3d.ini",
        context,
    )

    forecast_date = metadata["forecast_date"]
    output = require_value(animation, ("output",), f"de animación {product_name}")
    if not isinstance(output, dict):
        raise RuntimeError(f"La sección 'output' de {product_name} debe ser un mapa YAML.")
    output_directory = project_root / "outputs" / "met3d" / str(animation["name"]) / model_identifier
    video_file = output_directory / f"{animation['name']}_{model_identifier}_{forecast_date:%Y%m%d_%HZ}.mp4"

    return {
        "animation": animation,
        "metadata": metadata,
        "runtime_directory": runtime_directory,
        "files": files,
        "actor_files": actor_files,
        "frames_directory": frames_directory,
        "session_file": session_file,
        "session_source_file": session_source_file,
        "video_file": video_file,
    }


def met3d_environment_prefix(conda_executable: str, environment_name: str) -> Path:
    """Obtiene los recursos instalados de Met.3D en el ambiente Conda indicado."""

    try:
        result = subprocess.run(
            [conda_executable, "run", "-n", environment_name, "python", "-c", "import sys; print(sys.prefix)"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró el comando Conda: {conda_executable}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"No se pudo consultar el ambiente Conda '{environment_name}': {error.stderr}") from error

    met3d_base = Path(result.stdout.strip()) / "share" / "met3d"
    if not met3d_base.exists():
        raise RuntimeError(f"El ambiente '{environment_name}' no contiene los recursos de Met.3D: {met3d_base}")
    return met3d_base


def met3d_environment(preparation: dict[str, object], conda_executable: str, environment_name: str) -> dict[str, str]:
    """Aísla preferencias y caché de Met.3D dentro del runtime de la corrida."""

    runtime_directory = preparation["runtime_directory"]
    if not isinstance(runtime_directory, Path):
        raise RuntimeError("No se pudo localizar el runtime Met.3D preparado.")
    return {
        **os.environ,
        "MET3D_BASE": str(met3d_environment_prefix(conda_executable, environment_name)),
        "XDG_CONFIG_HOME": str(runtime_directory / "config"),
    }


def open_animation(preparation: dict[str, object], conda_executable: str, environment_name: str) -> None:
    """Abre una animación Met.3D para revisar sus objetos y cámara."""

    files = preparation["files"]
    actor_files = preparation["actor_files"]
    if not isinstance(files, dict) or not isinstance(actor_files, list):
        raise RuntimeError("No se encontraron las configuraciones de actores preparadas.")
    command = [
        conda_executable,
        "run",
        "--no-capture-output",
        "-n",
        environment_name,
        "Met3D",
        "--datasets",
        str(files["dataset"]),
        "--actors",
        ";".join(str(actor) for actor in actor_files),
    ]
    try:
        subprocess.run(command, check=True, env=met3d_environment(preparation, conda_executable, environment_name))
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró el comando Conda: {conda_executable}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Met.3D no pudo abrir la escena de animación.") from error


def render_animation(preparation: dict[str, object], conda_executable: str, environment_name: str) -> Path:
    """Renderiza PNG con Met.3D y los codifica como MP4 histórico."""

    session_file = preparation["session_file"]
    session_source_file = preparation["session_source_file"]
    if not isinstance(session_file, Path) or not session_file.exists():
        expected_session = session_source_file if isinstance(session_source_file, Path) else session_file
        raise RuntimeError(
            "No existe la sesión base requerida para renderizar: "
            f"{expected_session}."
        )
    files = preparation["files"]
    actor_files = preparation["actor_files"]
    animation = preparation["animation"]
    frames_directory = preparation["frames_directory"]
    video_file = preparation["video_file"]
    if not isinstance(files, dict) or not isinstance(actor_files, list) or not isinstance(animation, dict) or not isinstance(frames_directory, Path) or not isinstance(video_file, Path):
        raise RuntimeError("La preparación no contiene los archivos necesarios para renderizar.")

    met3d_command = [
        conda_executable,
        "run",
        "--no-capture-output",
        "-n",
        environment_name,
        "Met3D",
        "--datasets",
        str(files["dataset"]),
        "--actors",
        ";".join(str(actor) for actor in actor_files),
        "--batch",
        str(files["batch"]),
    ]
    command = [
        "xvfb-run",
        "-a",
        f"--server-args={XVFB_SERVER_ARGUMENTS}",
        *met3d_command,
    ]
    try:
        subprocess.run(command, check=True, env=met3d_environment(preparation, conda_executable, environment_name))
    except FileNotFoundError as error:
        raise RuntimeError(
            "No se encontró xvfb-run. El render batch de Met.3D requiere Xvfb y un contexto OpenGL funcional."
        ) from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Met.3D no pudo renderizar los fotogramas bajo Xvfb. Revise el detalle previo: "
            "el render batch requiere un contexto OpenGL funcional."
        ) from error

    frame_glob = frames_directory / "frame-FN*.png"
    if not list(frames_directory.glob("frame-FN*.png")):
        raise RuntimeError("Met.3D terminó sin escribir fotogramas PNG para la animación.")
    if "camera_sequence" in files:
        metadata = preparation["metadata"]
        timeline = build_timeline(animation, metadata, str(animation["name"]))
        first_time = metadata["valid_times"][0]
        frame_names = {frame.name for frame in frames_directory.glob("frame-FN*.png")}
        selected_timestamps = set()
        for valid_time in metadata["valid_times"]:
            if (valid_time - first_time).total_seconds() > timeline["range_seconds"]:
                break
            timestamp = valid_time.strftime("%Y-%m-%dT%H%M%SZ")
            selected_timestamps.add(timestamp)
            if not any(name.endswith(f"-{timestamp}.png") for name in frame_names):
                raise RuntimeError(
                    f"La animación {animation['name']} de {metadata['center']}-{metadata['model']} "
                    f"no generó fotogramas para el plazo {valid_time}; revise la sincronización de cámara y tiempo."
                )
        for frame_name in frame_names:
            match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)\.png$", frame_name)
            timestamp = match.group(1) if match else ""
            if timestamp not in selected_timestamps:
                raise RuntimeError(f"La animación {animation['name']} generó un fotograma fuera de los plazos seleccionados: {frame_name}.")

    output = animation["output"]
    video_file.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(output["frames_per_second"]),
        "-pattern_type",
        "glob",
        "-i",
        str(frame_glob),
        "-vf",
        f"scale={output['width_px']}:{output['height_px']}:flags=lanczos",
        "-c:v",
        str(output["video_codec"]),
        "-pix_fmt",
        str(output["pixel_format"]),
        str(video_file),
    ]
    try:
        subprocess.run(ffmpeg_command, check=True)
    except FileNotFoundError as error:
        raise RuntimeError("No se encontró FFmpeg para codificar el video.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError("FFmpeg no pudo codificar el video.") from error
    return video_file
