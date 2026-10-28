"""Prepara, abre y renderiza animaciones meteorológicas con Met.3D."""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
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


def prepare_runtime_session(
    session_source_file: Path,
    runtime_directory: Path,
    animation: dict,
    for_render: bool,
) -> Path:
    """Copia la sesión base y aplica cámara, resolución y captura de la animación."""

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

    camera_settings = {
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
    }

    session_lines = runtime_session_file.read_text(encoding="utf-8").splitlines(keepends=True)
    settings_found = {setting: False for setting in camera_settings}
    for line_index, line in enumerate(session_lines):
        for setting, value in camera_settings.items():
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
    require_value(animation, ("camera",), f"de animación {product_name}")

    # Revisar la corrida NetCDF y derivar su identidad, fecha y duración.
    metadata = read_netcdf_metadata(netcdf_file, list(dict.fromkeys(required_variables)), product_name)
    model_identifier = f"{metadata['center']}-{metadata['model']}"
    runtime_directory = create_runtime_directory(project_root, model_identifier)
    timeline = build_timeline(animation, metadata, product_name)

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
    session_file = prepare_runtime_session(session_source_file, runtime_directory, animation, for_render)
    frames_directory = runtime_directory / "frames"
    frames_directory.mkdir()
    context = {
        "dataset_name": dataset_name,
        "netcdf_directory": netcdf_file.parent.resolve(),
        "netcdf_filename": netcdf_file.name,
        "variables": variables,
        "scene": scene,
        "derived_variable_mappings": derived_variable_mappings,
        "object_bounding_boxes": object_bounding_boxes,
        "potential_vorticity": potential_vorticity,
        "jet": jet,
        "timeline": timeline,
        "frames_directory": frames_directory.resolve(),
        "session_file": session_file.resolve() if session_file.exists() else "",
        "bounding_boxes_file": (runtime_directory / "bounding_boxes.bbox.conf").resolve(),
    }

    files = {
        "dataset": render_template(template_environment, "dataset.dataset.conf.j2", runtime_directory / "dataset.dataset.conf", context),
        "bounding_boxes": render_template(template_environment, "bounding_boxes.bbox.conf.j2", runtime_directory / "bounding_boxes.bbox.conf", context),
        "basemap": render_template(template_environment, "basemap.actor.conf.j2", runtime_directory / "basemap.actor.conf", context),
        "volume": render_template(template_environment, "volume_bounding_box.actor.conf.j2", runtime_directory / "volume_bounding_box.actor.conf", context),
        "batch": render_template(template_environment, "batch_mode.batch.conf.j2", runtime_directory / "batch_mode.batch.conf", context),
    }
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
        files["potential_vorticity"] = render_template(
            template_environment,
            "potential_vorticity.actor.conf.j2",
            runtime_directory / "potential_vorticity.actor.conf",
            context,
        )
        actor_files.append(files["potential_vorticity"])
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
