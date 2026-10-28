"""Prepara y renderiza animaciones meteorológicas con ParaView."""

from __future__ import annotations

import json
import shutil
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import yaml
from netCDF4 import Dataset, num2date

from visualize.paraview.jet import projected_horizontal_coordinates, write_jet_vts
from visualize.paraview.terrain import create_coordinate_system, prepare_static_scene


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
    """Obtiene un valor obligatorio e informa su ruta meteorológica si falta."""

    current: object = configuration
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise RuntimeError(f"Falta '{'.'.join(path)}' en la configuración {description}.")
        current = current[key]
    return current


def get_enabled_layer(layers: dict, layer_name: str, animation_name: str) -> dict | None:
    """Obtiene una capa de animación solamente cuando el YAML la habilita."""

    configuration = layers.get(layer_name)
    if configuration is None:
        return None
    if not isinstance(configuration, dict):
        raise RuntimeError(f"La capa '{layer_name}' de {animation_name} debe ser un mapa YAML.")
    return configuration if require_value(configuration, ("enabled",), f"de la capa {layer_name}") is True else None


def read_netcdf_metadata(netcdf_file: Path, required_variables: list[str], product_name: str) -> dict:
    """Revisa la corrida y obtiene su identidad y eje temporal."""

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
        if len(time_coordinate) < 2:
            raise RuntimeError(f"El NetCDF {netcdf_file.name} requiere al menos dos tiempos para una animación.")
        if not hasattr(time_coordinate, "units"):
            raise RuntimeError(f"La coordenada temporal de {netcdf_file.name} no declara unidades.")

        return {
            "center": str(dataset.center).strip().lower(),
            "model": str(dataset.model).strip().lower(),
            "forecast_date": datetime.fromisoformat(str(dataset.forecast_date)),
            "time_values": np.asarray(time_coordinate[:], dtype=np.float64),
            "valid_times": list(num2date(time_coordinate[:], time_coordinate.units, only_use_cftime_datetimes=False)),
        }


def select_time_indices(animation: dict, metadata: dict, animation_name: str) -> list[int]:
    """Selecciona los plazos del NetCDF que formarán la animación."""

    timeline = require_value(animation, ("timeline",), f"de la animación {animation_name}")
    if not isinstance(timeline, dict):
        raise RuntimeError(f"La línea de tiempo de {animation_name} debe ser un mapa YAML.")
    selection = require_value(timeline, ("selection",), f"de la animación {animation_name}")
    time_values = metadata["time_values"]
    if selection == "all_available":
        return list(range(len(time_values)))
    if selection == "first_hours":
        maximum_hours = float(require_value(timeline, ("max_forecast_hours",), f"de la animación {animation_name}"))
        selected_indices = [index for index, value in enumerate(time_values) if value <= maximum_hours]
        if len(selected_indices) < 2:
            raise RuntimeError(f"El horizonte de {maximum_hours:g} horas de {animation_name} no contiene dos plazos.")
        return selected_indices
    raise RuntimeError("timeline.selection debe ser 'all_available' o 'first_hours'.")


def color_values(color: str) -> list[float]:
    """Convierte un color hexadecimal declarado en YAML a RGB de ParaView."""

    if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
        raise RuntimeError(f"El color '{color}' debe usar el formato hexadecimal #RRGGBB.")
    return [int(color[position : position + 2], 16) / 255.0 for position in (1, 3, 5)]


def write_collection_file(collection_file: Path, frame_files: list[Path], time_values: list[float]) -> None:
    """Escribe la colección PVD que asocia cada VTS con su plazo de pronóstico."""

    datasets = "\n".join(
        f'    <DataSet timestep="{time_value:.8g}" group="" part="0" file="{escape(frame_file.name)}"/>'
        for frame_file, time_value in zip(frame_files, time_values, strict=True)
    )
    collection_file.write_text(
        "<?xml version=\"1.0\"?>\n"
        "<VTKFile type=\"Collection\" version=\"0.1\" byte_order=\"LittleEndian\">\n"
        "  <Collection>\n"
        f"{datasets}\n"
        "  </Collection>\n"
        "</VTKFile>\n",
        encoding="utf-8",
    )


def require_complete_atmospheric_field(
    values: np.ndarray,
    variable_name: str,
    valid_time: object,
    pressure_hpa: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> np.ndarray:
    """Detiene la animación cuando un campo no permite construir su geometría 3D."""

    masked_values = np.ma.asarray(values)
    invalid = np.ma.getmaskarray(masked_values) | ~np.isfinite(masked_values.filled(np.nan))
    if np.any(invalid):
        level_index, latitude_index, longitude_index = np.argwhere(invalid)[0]
        raise RuntimeError(
            f"La variable {variable_name} no tiene un valor utilizable para el plazo {valid_time.isoformat()}, "
            f"nivel {pressure_hpa[level_index]:g} hPa, latitud {latitude[latitude_index]:.4f}, "
            f"longitud {longitude[longitude_index]:.4f}."
        )
    return np.asarray(masked_values, dtype=np.float32)


def inspect_geopotential_height_holes(
    values: np.ndarray,
    valid_time: object,
    pressure_hpa: float,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> list[dict]:
    """Describe huecos aislados de altura geopotencial o detiene ante una ausencia no rellenable."""

    masked_values = np.ma.asarray(values)
    invalid = np.ma.getmaskarray(masked_values) | ~np.isfinite(masked_values.filled(np.nan))
    holes = np.argwhere(invalid)
    corrections = []
    for latitude_index, longitude_index in holes:
        neighbors = []
        for latitude_offset, longitude_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor_latitude = latitude_index + latitude_offset
            neighbor_longitude = longitude_index + longitude_offset
            if 0 <= neighbor_latitude < values.shape[0] and 0 <= neighbor_longitude < values.shape[1]:
                if invalid[neighbor_latitude, neighbor_longitude]:
                    raise RuntimeError(
                        f"hgtprs contiene huecos contiguos en el plazo {valid_time.isoformat()}, "
                        f"nivel {pressure_hpa:g} hPa, latitud {latitude[latitude_index]:.4f}, "
                        f"longitud {longitude[longitude_index]:.4f}."
                    )
                neighbors.append(float(masked_values[neighbor_latitude, neighbor_longitude]))

        expected_neighbors = 4
        if latitude_index in (0, values.shape[0] - 1):
            expected_neighbors -= 1
        if longitude_index in (0, values.shape[1] - 1):
            expected_neighbors -= 1
        if len(neighbors) != expected_neighbors or len(neighbors) < 2:
            raise RuntimeError(
                f"hgtprs no tiene vecinos suficientes para rellenar el hueco del plazo {valid_time.isoformat()}, "
                f"nivel {pressure_hpa:g} hPa, latitud {latitude[latitude_index]:.4f}, "
                f"longitud {longitude[longitude_index]:.4f}."
            )
        corrections.append(
            {
                "latitude_index": int(latitude_index),
                "longitude_index": int(longitude_index),
                "latitude": float(latitude[latitude_index]),
                "longitude": float(longitude[longitude_index]),
                "neighbor_values_gpm": neighbors,
                "filled_value_gpm": float(np.mean(neighbors)),
            }
        )
    return corrections


def inspect_required_fields_and_height_holes(
    dataset: Dataset,
    variables: dict,
    time_indices: list[int],
    selected_levels: np.ndarray,
    selected_pressure_hpa: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
    metadata: dict,
    missing_values: dict,
) -> dict[tuple[int, int], list[dict]]:
    """Revisa viento completo y registra los huecos de hgtprs antes de escribir VTS."""

    corrections_by_level: dict[tuple[int, int], list[dict]] = {}
    for time_index in time_indices:
        valid_time = metadata["valid_times"][time_index]
        for variable_key in ("wind_u", "wind_v"):
            require_complete_atmospheric_field(
                dataset.variables[variables[variable_key]][time_index, selected_levels, :, :],
                variables[variable_key],
                valid_time,
                selected_pressure_hpa,
                latitude,
                longitude,
            )
        for pressure_index, level_index in enumerate(selected_levels):
            corrections = inspect_geopotential_height_holes(
                dataset.variables[variables["geopotential_height"]][time_index, level_index, :, :],
                valid_time,
                float(selected_pressure_hpa[pressure_index]),
                latitude,
                longitude,
            )
            if corrections:
                corrections_by_level[(time_index, int(level_index))] = corrections

    affected_times = {time_index for time_index, _ in corrections_by_level}
    affected_levels = {level_index for _, level_index in corrections_by_level}
    maximum_times = int(require_value(missing_values, ("max_affected_times",), "de ausencias de la coordenada vertical"))
    maximum_levels = int(require_value(missing_values, ("max_affected_levels",), "de ausencias de la coordenada vertical"))
    if len(affected_times) > maximum_times or len(affected_levels) > maximum_levels:
        raise RuntimeError(
            "hgtprs presenta ausencias en demasiados plazos o niveles: "
            f"{len(affected_times)} plazos y {len(affected_levels)} niveles afectados. "
            "Revise la calidad de la corrida antes de generar la animación."
        )
    return corrections_by_level


def fill_geopotential_height_holes(
    values: np.ndarray,
    selected_levels: np.ndarray,
    corrections_by_level: dict[tuple[int, int], list[dict]],
    time_index: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Completa hgtprs con promedios vecinos y marca exclusivamente los puntos corregidos."""

    filled_values = np.asarray(values, dtype=np.float32).copy()
    completed = np.zeros(filled_values.shape, dtype=np.uint8)
    for pressure_index, level_index in enumerate(selected_levels):
        for correction in corrections_by_level.get((time_index, int(level_index)), []):
            latitude_index = correction["latitude_index"]
            longitude_index = correction["longitude_index"]
            filled_values[pressure_index, latitude_index, longitude_index] = correction["filled_value_gpm"]
            completed[pressure_index, latitude_index, longitude_index] = 1
    return filled_values, completed


def prepare_jet_data(
    animation: dict,
    scene: dict,
    netcdf_file: Path,
    data_directory: Path,
    time_indices: list[int],
    metadata: dict,
) -> dict:
    """Construye la capa VTS de rapidez de viento en altura geopotencial."""

    product_name = str(animation["name"])
    jet = get_enabled_layer(require_value(animation, ("layers",), f"de la animación {product_name}"), "jet", product_name)
    variables = require_value(jet, ("variables",), f"del jet de {product_name}") if jet is not None else None
    if not isinstance(variables, dict) or jet is None:
        raise RuntimeError(f"La animación {product_name} debe habilitar la capa meteorológica jet.")
    if require_value(jet, ("type",), f"del jet de {product_name}") != "wind_speed_isosurface":
        raise RuntimeError(f"La capa jet de {product_name} debe usar type: wind_speed_isosurface.")
    missing_values = require_value(jet, ("vertical_coordinate", "missing_values"), f"del jet de {product_name}")
    if not isinstance(missing_values, dict):
        raise RuntimeError(f"Las ausencias de la coordenada vertical del jet de {product_name} deben ser un mapa YAML.")
    if require_value(missing_values, ("policy",), f"del jet de {product_name}") != "fill_isolated_orthogonal_mean":
        raise RuntimeError(
            f"La coordenada vertical del jet de {product_name} sólo admite "
            "missing_values.policy: fill_isolated_orthogonal_mean."
        )

    pressure = require_value(jet, ("pressure",), f"del jet de {product_name}")
    if not isinstance(pressure, dict):
        raise RuntimeError(f"La presión del jet de {product_name} debe ser un mapa YAML.")
    bottom_hpa = float(require_value(pressure, ("bottom_hpa",), f"del jet de {product_name}"))
    top_hpa = float(require_value(pressure, ("top_hpa",), f"del jet de {product_name}"))
    if bottom_hpa <= top_hpa:
        raise RuntimeError(f"El jet de {product_name} debe cumplir bottom_hpa > top_hpa.")
    sample_rate = int(require_value(jet, ("preparation", "horizontal_sample_rate"), f"del jet de {product_name}"))
    if sample_rate < 1:
        raise RuntimeError(f"El muestreo horizontal del jet de {product_name} debe ser al menos uno.")
    vertical_exaggeration = float(require_value(animation, ("vertical_exaggeration",), f"de la animación {product_name}"))
    if vertical_exaggeration <= 0:
        raise RuntimeError(f"La exageración vertical de {product_name} debe ser positiva.")

    required_variables = [
        str(require_value(variables, ("wind_u",), f"del producto {product_name}")),
        str(require_value(variables, ("wind_v",), f"del producto {product_name}")),
        str(require_value(variables, ("vertical_coordinate",), f"del jet de {product_name}")),
        "lev",
        "latitude",
        "longitude",
        "time",
    ]
    target_coordinate_system = create_coordinate_system(scene["projection"]["proj4"])
    frame_files: list[Path] = []
    frame_metadata: list[dict] = []

    with Dataset(netcdf_file) as dataset:
        missing_variables = [name for name in required_variables if name not in dataset.variables]
        if missing_variables:
            raise RuntimeError(f"Faltan variables requeridas para el jet: {', '.join(missing_variables)}.")
        height_variable_name = str(variables["vertical_coordinate"])
        height_variable = dataset.variables[height_variable_name]
        expected_units = str(require_value(jet, ("vertical_coordinate", "units"), f"del jet de {product_name}"))
        if getattr(height_variable, "units", None) != expected_units:
            raise RuntimeError(
                f"La coordenada vertical {height_variable_name} debe tener unidades {expected_units}, "
                f"no '{getattr(height_variable, 'units', None)}'."
            )

        pressure_hpa = np.asarray(dataset.variables["lev"][:], dtype=np.float64)
        selected_levels = np.flatnonzero((pressure_hpa >= top_hpa) & (pressure_hpa <= bottom_hpa))
        if selected_levels.size < 2:
            raise RuntimeError(f"El intervalo {bottom_hpa:g}--{top_hpa:g} hPa no contiene suficientes niveles.")
        selected_pressure_hpa = pressure_hpa[selected_levels]

        full_latitude = np.asarray(dataset.variables["latitude"][:], dtype=np.float64)
        full_longitude = np.asarray(dataset.variables["longitude"][:], dtype=np.float64)
        corrections_by_level = inspect_required_fields_and_height_holes(
            dataset,
            {"wind_u": variables["wind_u"], "wind_v": variables["wind_v"], "geopotential_height": height_variable_name},
            time_indices,
            selected_levels,
            selected_pressure_hpa,
            full_latitude,
            full_longitude,
            metadata,
            missing_values,
        )
        for (time_index, level_index), corrections in corrections_by_level.items():
            valid_time = metadata["valid_times"][time_index]
            event_pressure_hpa = pressure_hpa[level_index]
            warnings.warn(
                f"fill_holes completó {len(corrections)} huecos de hgtprs en el plazo {valid_time.isoformat()}, "
                f"nivel {event_pressure_hpa:g} hPa.",
                stacklevel=2,
            )

        latitude = full_latitude[::sample_rate]
        longitude = full_longitude[::sample_rate]
        x_coordinate_m, y_coordinate_m = projected_horizontal_coordinates(
            latitude, longitude, target_coordinate_system
        )
        for frame_number, time_index in enumerate(time_indices):
            selection = (time_index, selected_levels, slice(None), slice(None))
            valid_time = metadata["valid_times"][time_index]
            wind_u = np.asarray(dataset.variables[variables["wind_u"]][selection], dtype=np.float32)
            wind_v = np.asarray(dataset.variables[variables["wind_v"]][selection], dtype=np.float32)
            geopotential_height_m, completed_height = fill_geopotential_height_holes(
                height_variable[selection], selected_levels, corrections_by_level, time_index
            )
            wind_u = wind_u[:, ::sample_rate, ::sample_rate]
            wind_v = wind_v[:, ::sample_rate, ::sample_rate]
            geopotential_height_m = geopotential_height_m[:, ::sample_rate, ::sample_rate]
            completed_height = completed_height[:, ::sample_rate, ::sample_rate]
            wind_speed_m_s = np.hypot(wind_u, wind_v).astype(np.float32)
            threshold_m_s = float(require_value(jet, ("isosurface", "value_m_s"), f"del jet de {product_name}"))
            if float(wind_speed_m_s.max()) < threshold_m_s:
                raise RuntimeError(
                    f"El jet de {product_name} no alcanza {threshold_m_s:g} m/s en el plazo {valid_time.isoformat()}."
                )

            frame_file = data_directory / f"jet_{frame_number:04d}.vts"
            write_jet_vts(
                frame_file,
                x_coordinate_m,
                y_coordinate_m,
                geopotential_height_m,
                wind_speed_m_s,
                selected_pressure_hpa,
                vertical_exaggeration,
                completed_height,
            )
            frame_files.append(frame_file)
            frame_metadata.append(
                {
                    "file": frame_file.name,
                    "time_value": float(metadata["time_values"][time_index]),
                    "valid_time_utc": metadata["valid_times"][time_index].isoformat(),
                }
            )

    collection_file = data_directory / "jet.pvd"
    write_collection_file(collection_file, frame_files, [frame["time_value"] for frame in frame_metadata])
    metadata_file = data_directory / "jet_metadata.json"
    metadata_file.write_text(
        json.dumps(
            {
                "animation": product_name,
                "source_netcdf": str(netcdf_file),
                "pressure_range_hpa": [top_hpa, bottom_hpa],
                "selected_pressure_levels_hpa": selected_pressure_hpa.tolist(),
                "horizontal_sample_rate": sample_rate,
                "vertical_coordinate": "geopotential height at isobaric levels (gpm)",
                "vertical_exaggeration": vertical_exaggeration,
                "missing_values": missing_values,
                "fill_holes": {
                    "affected_time_count": len({time_index for time_index, _ in corrections_by_level}),
                    "affected_level_count": len({level_index for _, level_index in corrections_by_level}),
                    "events": [
                        {
                            "valid_time_utc": metadata["valid_times"][time_index].isoformat(),
                            "pressure_hpa": float(pressure_hpa[level_index]),
                            "corrections": corrections,
                        }
                        for (time_index, level_index), corrections in corrections_by_level.items()
                    ],
                },
                "frames": frame_metadata,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"collection": collection_file, "metadata": metadata_file, "frames": frame_files}


def prepare_animation(project_root: Path, animation_file: Path, netcdf_file: Path) -> dict[str, object]:
    """Materializa los datos y la configuración transitoria de una animación ParaView."""

    # Leer escena y capas meteorológicas propias de ParaView.
    animation = load_yaml_configuration(animation_file, "de la animación ParaView")
    product_name = str(require_value(animation, ("name",), "de la animación ParaView"))
    scene_file = project_root / str(require_value(animation, ("scene",), f"de la animación {product_name}"))
    scene = load_yaml_configuration(scene_file, "de la escena ParaView")
    layers = require_value(animation, ("layers",), f"de la animación {product_name}")
    if not isinstance(layers, dict):
        raise RuntimeError(f"Las capas de {product_name} deben ser un mapa YAML.")
    jet = get_enabled_layer(layers, "jet", product_name)
    terrain = get_enabled_layer(layers, "terrain", product_name)
    if jet is None:
        raise RuntimeError(f"La animación {product_name} debe habilitar una capa tridimensional.")
    jet_volume_box = get_enabled_layer(jet, "volume_outline", product_name)

    # Revisar la corrida y definir las capas temporales de la escena.
    variables = require_value(jet, ("variables",), f"del jet de {product_name}")
    if not isinstance(variables, dict):
        raise RuntimeError(f"Las variables del jet de {product_name} deben ser un mapa YAML.")
    required_variables = [str(require_value(variables, (name,), f"del jet de {product_name}")) for name in ("wind_u", "wind_v", "vertical_coordinate")]
    metadata = read_netcdf_metadata(netcdf_file, required_variables, product_name)
    model_identifier = f"{metadata['center']}-{metadata['model']}"
    forecast_date = metadata["forecast_date"]
    run_identifier = forecast_date.strftime("%Y%m%d_%HZ")
    scene_data_directory = project_root / "paraview" / "render_data" / scene["name"]
    data_directory = scene_data_directory / "jet"
    render_directory = project_root / "paraview" / "render_cache" / scene["name"]
    if data_directory.exists():
        shutil.rmtree(data_directory)
    if render_directory.exists():
        shutil.rmtree(render_directory)
    data_directory.mkdir(parents=True)
    render_directory.mkdir(parents=True)
    time_indices = select_time_indices(animation, metadata, product_name)

    # Preparar el terreno solamente si la configuración física cambió.
    files: dict[str, Path] = {}
    vertical_exaggeration = float(require_value(animation, ("vertical_exaggeration",), f"de la animación {product_name}"))
    if terrain is not None:
        terrain_files = prepare_static_scene(
            project_root,
            scene_file,
            overwrite=True,
            vertical_exaggeration=vertical_exaggeration,
            reuse_matching_terrain=True,
        )
        files["terrain"] = terrain_files["terrain_vts"]
        files["terrain_metadata"] = terrain_files["metadata"]

    # Construir todos los plazos atmosféricos en coordenada de altura geopotencial.
    jet_files = prepare_jet_data(animation, scene, netcdf_file, data_directory, time_indices, metadata)
    files["jet_collection"] = jet_files["collection"]
    files["jet_metadata"] = jet_files["metadata"]

    jet_color = color_values(str(require_value(jet, ("isosurface", "color"), f"del jet de {product_name}")))
    render_configuration = {
        "animation": product_name,
        "scene": scene,
        "camera": require_value(animation, ("camera",), f"de la animación {product_name}"),
        "output": require_value(animation, ("output",), f"de la animación {product_name}"),
        "frames_directory": str((render_directory / "frames").resolve()),
        "layers": [
            *(
                [{
                    "name": "terrain",
                    "type": "terrain",
                    "file": str(files["terrain"].resolve()),
                    "metadata_file": str(files["terrain_metadata"].resolve()),
                }]
                if "terrain" in files else []
            ),
            {
                "name": "jet",
                "type": "wind_speed_isosurface",
                "collection_file": str(files["jet_collection"].resolve()),
                "isosurface": {
                    "value_m_s": float(require_value(jet, ("isosurface", "value_m_s"), f"del jet de {product_name}")),
                    "color": jet_color,
                    "opacity": float(require_value(jet, ("isosurface", "opacity"), f"del jet de {product_name}")),
                },
                "volume_outline": (
                    {
                        "color": color_values(str(require_value(jet_volume_box, ("color",), f"del contorno del jet de {product_name}"))),
                        "opacity": float(require_value(jet_volume_box, ("opacity",), f"del contorno del jet de {product_name}")),
                        "line_width_px": float(require_value(jet_volume_box, ("line_width_px",), f"del contorno del jet de {product_name}")),
                    }
                    if jet_volume_box is not None
                    else None
                ),
            },
        ],
    }
    configuration_file = render_directory / "render_configuration.json"
    configuration_file.write_text(json.dumps(render_configuration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["render_configuration"] = configuration_file
    video_file = (
        project_root
        / "outputs"
        / "paraview"
        / product_name
        / model_identifier
        / f"{product_name}_{model_identifier}_{run_identifier}.mp4"
    )
    return {
        "animation": animation,
        "scene": scene,
        "metadata": metadata,
        "files": files,
        "data_directory": data_directory,
        "render_directory": render_directory,
        "video_file": video_file,
    }


def render_animation(preparation: dict[str, object], pvpython_executable: str) -> Path:
    """Renderiza los PNG con ParaView y los codifica como un MP4 histórico."""

    files = preparation["files"]
    animation = preparation["animation"]
    video_file = preparation["video_file"]
    render_directory = preparation["render_directory"]
    if not isinstance(files, dict) or not isinstance(animation, dict) or not isinstance(video_file, Path) or not isinstance(render_directory, Path):
        raise RuntimeError("La preparación no contiene los archivos necesarios para renderizar.")

    renderer_file = Path(__file__).resolve().parents[3] / "paraview" / "scripts" / "render_animation.py"
    command = [
        pvpython_executable,
        "--disable-registry",
        "--force-offscreen-rendering",
        "--opengl-window-backend",
        "EGL",
        str(renderer_file),
        "--configuration",
        str(files["render_configuration"]),
    ]
    print("ParaView está renderizando los fotogramas PNG...", flush=True)
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró pvpython: {pvpython_executable}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError("ParaView no pudo renderizar los fotogramas de la animación.") from error

    frames_directory = render_directory / "frames"
    if not list(frames_directory.glob("frame-*.png")):
        raise RuntimeError("ParaView terminó sin escribir fotogramas PNG para la animación.")
    output = require_value(animation, ("output",), f"de la animación {animation['name']}")
    if not isinstance(output, dict):
        raise RuntimeError(f"La salida de {animation['name']} debe ser un mapa YAML.")
    video_file.parent.mkdir(parents=True, exist_ok=True)
    print("Codificando los fotogramas PNG como video MP4...", flush=True)
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(output["frames_per_second"]),
        "-i",
        str(frames_directory / "frame-%04d.png"),
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
