"""Prepara los objetos meteorológicos, sus tiempos nativos y sus recortes."""

from __future__ import annotations

import math
import re
import struct
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, num2date

from visualize.met3D.configuration import load_yaml_configuration, require_value
from visualize.met3D.horizontal_sections import prepare_horizontal_sections, select_horizontal_section_data
from visualize.met3D.colormaps import prepare_pressure_colour_bands, encode_met3d_rgb_colour
from visualize.met3D.native import (
    encode_qrectf_variant, encode_text_position_variant, encode_text_colour_variant,
    encode_uuid_variant,
)


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
        if len(time_values) < 1:
            raise RuntimeError(
                f"El NetCDF {netcdf_file.name} no contiene tiempos para {product_name}."
            )
        if (hasattr(time_values, "mask") and time_values.mask.any()) or any(not math.isfinite(float(value)) for value in time_values):
            raise RuntimeError(f"El NetCDF {netcdf_file.name} contiene tiempos ausentes o inválidos para {product_name}.")
        if not hasattr(time_coordinate, "units"):
            raise RuntimeError(f"La coordenada 'time' de {netcdf_file.name} no declara unidades.")

        valid_times = num2date(time_values, time_coordinate.units, only_use_cftime_datetimes=False)
        return {
            "center": str(dataset.center).strip().lower(),
            "model": str(dataset.model).strip().lower(),
            "forecast_date": datetime.fromisoformat(str(dataset.forecast_date)),
            "valid_times": list(valid_times),
            "netcdf_filename": netcdf_file.name,
        }


def build_timeline(animation: dict, metadata: dict, product_name: str) -> dict:
    """Convierte la selección temporal declarada a los parámetros batch de Met.3D."""

    timeline = require_value(animation, ("timeline",), f"de animación {product_name}")
    if not isinstance(timeline, dict):
        raise RuntimeError("La sección 'timeline' debe ser un mapa YAML.")

    selection = require_value(timeline, ("selection",), f"de animación {product_name}")
    valid_times = metadata["valid_times"]
    for earlier, later in zip(valid_times, valid_times[1:]):
        if later <= earlier:
            raise RuntimeError(f"{metadata['center']}-{metadata['model']}, {metadata['netcdf_filename']}: tiempos duplicados o desordenados entre {earlier} y {later}.")
    available_seconds = int((valid_times[-1] - valid_times[0]).total_seconds())

    if selection == "all_available":
        range_seconds = available_seconds
    elif selection == "first_hours":
        maximum_hours = require_value(timeline, ("max_forecast_hours",), f"de animación {product_name}")
        range_seconds = min(available_seconds, int(float(maximum_hours) * 3600))
    else:
        raise RuntimeError("timeline.selection debe ser 'all_available' o 'first_hours'.")

    selected_times = [time for time in valid_times if (time - valid_times[0]).total_seconds() <= range_seconds]
    if not selected_times:
        raise RuntimeError(f"{metadata['netcdf_filename']}: no hay tiempos seleccionados para {product_name}.")
    # IFS puede cambiar de frecuencia fuera del tramo que se va a visualizar.
    step_seconds = None
    for earlier, later in zip(selected_times, selected_times[1:]):
        interval = (later - earlier).total_seconds()
        if step_seconds is not None and interval != step_seconds:
            raise RuntimeError(f"{metadata['center']}-{metadata['model']}, {metadata['netcdf_filename']}: tiempos irregulares en la selección entre {earlier} y {later}.")
        step_seconds = interval
    if step_seconds is not None and step_seconds != int(step_seconds):
        raise RuntimeError(f"{product_name}: el intervalo temporal debe expresarse en segundos enteros.")
    return {"valid_times": selected_times, "range_seconds": int((selected_times[-1] - selected_times[0]).total_seconds()), "step_seconds": int(step_seconds) if step_seconds is not None else None}


def get_enabled_object(objects: dict, object_name: str, product_name: str) -> dict | None:
    """Obtiene un objeto de producto sólo cuando su YAML lo habilita."""

    configuration = objects.get(object_name)
    if configuration is None:
        return None
    if not isinstance(configuration, dict):
        raise RuntimeError(f"El objeto '{object_name}' de {product_name} debe ser un mapa YAML.")
    enabled = require_value(configuration, ("enabled",), f"del objeto {object_name} de {product_name}")
    return configuration if enabled is True else None


def prepare_product_objects(project_root: Path, animation: dict, scene: dict, reuse_netcdf: bool) -> dict:
    """Resuelve capas, diagnósticos y máscaras declarados por el producto."""

    product_name = str(animation["name"])
    output = require_value(animation, ("output",), f"de animación {product_name}")
    for key in ("width_px", "height_px", "frames_per_second", "video_codec", "pixel_format"):
        require_value(output, (key,), f"de salida de {product_name}")
    for key in ("width_px", "height_px"):
        if type(output[key]) is not int or output[key] <= 0:
            raise RuntimeError(f"La salida de {product_name} requiere {key} como entero positivo.")
    if not math.isfinite(float(output["frames_per_second"])) or float(output["frames_per_second"]) <= 0:
        raise RuntimeError(f"La salida de {product_name} requiere frames_per_second positivo y finito.")
    variables = require_value(animation, ("variables",), f"de animación {product_name}")
    if not isinstance(variables, dict):
        raise RuntimeError(f"La sección 'variables' de {product_name} debe ser un mapa YAML.")
    objects = require_value(animation, ("objects",), f"de animación {product_name}")
    if not isinstance(objects, dict):
        raise RuntimeError(f"La sección 'objects' de {product_name} debe ser un mapa YAML.")

    surface_pressure = get_enabled_object(objects, "surface_pressure", product_name)
    surface_temperature = get_enabled_object(surface_pressure, "temperature", product_name) if surface_pressure is not None else None
    surface_precipitation = get_enabled_object(surface_pressure, "precipitation", product_name) if surface_pressure is not None else None
    geographic_lines = get_enabled_object(surface_pressure, "geographic_lines", product_name) if surface_pressure is not None else None
    if geographic_lines is not None:
        colour = require_value(geographic_lines, ("colour",), f"de líneas geográficas de {product_name}")
        if not isinstance(colour, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", colour) is None:
            raise RuntimeError(f"Las líneas geográficas de {product_name} requieren colour como HEX #RRGGBB.")
        rgb = [int(colour[index:index + 2], 16) for index in (1, 3, 5)]
        geographic_lines["colour_variant"] = encode_text_colour_variant([*rgb, 255], f"Líneas geográficas de {product_name}")
    if surface_temperature is not None and surface_precipitation is not None:
        raise RuntimeError(f"El relieve de {product_name} debe colorearse con temperatura o precipitación; seleccione sólo un campo.")
    potential_vorticity = get_enabled_object(objects, "potential_vorticity", product_name)
    horizontal_sections = prepare_horizontal_sections(objects, variables, product_name)
    jet = get_enabled_object(objects, "jet", product_name)
    cold_air = get_enabled_object(objects, "cold_air", product_name)
    cloud_cover = get_enabled_object(objects, "cloud_cover", product_name)
    relative_humidity = get_enabled_object(objects, "relative_humidity", product_name)
    mean_sea_level_pressure = get_enabled_object(objects, "mean_sea_level_pressure", product_name)
    streamlines = get_enabled_object(objects, "streamlines", product_name)
    time_label = get_enabled_object(objects, "time_label", product_name)
    pv_render_mode = None
    if potential_vorticity is None and jet is None and cold_air is None and relative_humidity is None and streamlines is None and cloud_cover is None and not horizontal_sections:
        raise RuntimeError(f"La animación {product_name} debe habilitar al menos un objeto volumétrico o una sección horizontal.")

    required_variables: list[str] = []
    derived_variable_mappings: list[str] = []
    if mean_sea_level_pressure is not None:
        required_variables.append(str(require_value(variables, ("mean_sea_level_pressure",), f"de animación {product_name}")))
        for key in ("display_pressure_hpa", "line_width", "line_colour", "colourmap_file", "legend"):
            require_value(mean_sea_level_pressure, (key,), f"de presión al nivel del mar de {product_name}")
        if float(mean_sea_level_pressure["line_width"]) <= 0:
            raise RuntimeError(f"Los contornos de presión de {product_name} requieren grosor positivo.")
        if not float(scene["view_pressure"]["top_hpa"]) <= float(mean_sea_level_pressure["display_pressure_hpa"]) <= float(scene["view_pressure"]["bottom_hpa"]):
            raise RuntimeError(f"El plano gráfico de presión al nivel del mar de {product_name} queda fuera de la escena.")
        colourmap_file = project_root / str(mean_sea_level_pressure["colourmap_file"])
        colourmap = load_yaml_configuration(colourmap_file, f"de colores de presión de {product_name}")
        bands = prepare_pressure_colour_bands(colourmap, f"Paleta de presión {colourmap_file}, animación {product_name}")
        mean_sea_level_pressure["line_colour_variant"] = encode_text_colour_variant(mean_sea_level_pressure["line_colour"], f"Contornos PNM de {product_name}")
        mean_sea_level_pressure["contour_levels_pa"] = ", ".join(f"{band['upper'] * 100:g}" for band in bands[:-1])
        legend = mean_sea_level_pressure["legend"]
        for key in ("position", "row_spacing", "label_spacing", "font", "font_size"):
            require_value(legend, (key,), f"de leyenda PNM de {product_name}")
        x, y, width, height = (float(require_value(legend, ("position", key), f"de leyenda PNM de {product_name}")) for key in ("x", "y", "width", "height"))
        row_spacing = float(legend["row_spacing"])
        if width <= 0 or height <= 0 or row_spacing < height or not (-1 <= x < x + width <= 1 and -1 <= y - (len(bands) - 1) * row_spacing - height < y <= 1):
            raise RuntimeError(f"La leyenda PNM de {product_name} requiere bandas positivas, separadas y dentro de la pantalla.")
        legend["labels"] = [{"text": "PNM [hPa]", "position": encode_text_position_variant(x, y + row_spacing), "anchor": 0}]
        for index, band in enumerate(bands):
            identifier = uuid.uuid5(uuid.NAMESPACE_URL, f"metvis3d:mean_sea_level_pressure:band:{index + 1}")
            band["uuid"] = str(identifier)
            band["uuid_variant"] = encode_uuid_variant(identifier)
            band["legend_rectangle"] = encode_qrectf_variant(x, y - index * row_spacing, width, height)
            legend["labels"].append({"text": band["label"], "position": encode_text_position_variant(x + width + float(legend["label_spacing"]), y - index * row_spacing - height / 2), "anchor": 0})
        mean_sea_level_pressure["bands"] = bands
    if streamlines is not None:
        for role in ("wind_u", "wind_v", "wind_omega"):
            required_variables.append(str(require_value(variables, (role,), f"de circulación 3D de {product_name}")))
        for key in ("representation", "pressure", "seed_pressure_levels_hpa", "seed_spacing_degrees", "seed_areas", "integration_method", "interpolation_method", "tube_radius", "colour"):
            require_value(streamlines, (key,), f"de circulación 3D de {product_name}")
        if streamlines["representation"] not in ("streamlines", "particles_with_trails"):
            raise RuntimeError(f"La representación del viento de {product_name} debe ser streamlines o particles_with_trails.")
        parameters = ("integration_step_seconds", "number_of_segments") if streamlines["representation"] == "streamlines" else ("trail_hours", "substeps_per_data_timestep", "sphere_radius")
        for key in parameters:
            require_value(streamlines, (key,), f"de circulación 3D de {product_name}")
        if any(not math.isfinite(float(streamlines[key])) or float(streamlines[key]) <= 0 for key in parameters):
            raise RuntimeError(f"La circulación 3D de {product_name} requiere valores positivos para {', '.join(parameters)}.")
        if streamlines["representation"] == "particles_with_trails":
            substeps = float(streamlines["substeps_per_data_timestep"])
            if not substeps.is_integer() or not 3 <= substeps <= 1000:
                raise RuntimeError(f"Los subpasos del viento de {product_name} deben ser un número entero entre 3 y 1000 para formar la geometría de las partículas.")
            if float(streamlines["sphere_radius"]) <= float(streamlines["tube_radius"]):
                raise RuntimeError(f"El radio de las partículas de {product_name} debe superar el radio de su rastro.")
        for key in ("bottom_hpa", "top_hpa"):
            require_value(streamlines, ("pressure", key), f"de circulación 3D de {product_name}")
        for key, names in (("integration_method", ("euler", "runge_kutta")), ("interpolation_method", ("lagranto", "trilinear"))):
            if streamlines[key] not in names:
                raise RuntimeError(f"La circulación 3D de {product_name} requiere {key} entre {names}.")
            streamlines[f"{key}_index"] = names.index(streamlines[key])
        if any(float(streamlines[key]) <= 0 for key in ("seed_spacing_degrees", "tube_radius")):
            raise RuntimeError(f"La circulación 3D de {product_name} requiere separación, paso de integración, segmentos y radio positivos.")
        colour = streamlines["colour"]
        if not isinstance(colour, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", colour) is None:
            raise RuntimeError(f"El viento de {product_name} requiere colour como color HEX #RRGGBB.")
        rgb = [int(colour[index:index + 2], 16) for index in (1, 3, 5)]
        streamlines["colour_variant"] = encode_text_colour_variant([*rgb, 255], f"Color del viento de {product_name}")
        # QVector3D nativo de Qt: separación horizontal en grados y vertical en hPa.
        spacing = float(streamlines["seed_spacing_degrees"])
        encoded_spacing = struct.pack(">I3f", 84, spacing, spacing, 1.0)
        streamlines["spacing_variant"] = "@Variant(" + "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_spacing) + ")"
    if surface_temperature is not None:
        required_variables.append(str(require_value(variables, ("air_temperature_2m",), f"de animación {product_name}")))
        description = f"de T2m sobre el relieve de {product_name}"
        for key in ("minimum_c", "maximum_c", "kelvin_offset", "colourmap", "reverse_colourmap", "colour_steps", "colourbar"):
            require_value(surface_temperature, (key,), description)
        minimum_c = float(surface_temperature["minimum_c"])
        maximum_c = float(surface_temperature["maximum_c"])
        kelvin_offset = float(surface_temperature["kelvin_offset"])
        if not all(math.isfinite(value) for value in (minimum_c, maximum_c, kelvin_offset)) or not minimum_c < maximum_c:
            raise RuntimeError(f"La escala de T2m de {product_name} requiere límites finitos y minimum_c < maximum_c.")
        if int(surface_temperature["colour_steps"]) < 2:
            raise RuntimeError(f"La escala de T2m de {product_name} requiere al menos dos pasos de color.")
        # La transferencia recibe kelvin; únicamente sus rótulos muestran Celsius.
        surface_temperature["minimum_k"] = minimum_c + kelvin_offset
        surface_temperature["maximum_k"] = maximum_c + kelvin_offset
        colourbar = surface_temperature["colourbar"]
        for key in ("position", "ticks_c", "title", "font", "font_size", "label_spacing", "title_spacing"):
            require_value(colourbar, (key,), description)
        x, y, width, height = (float(require_value(colourbar, ("position", key), description)) for key in ("x", "y", "width", "height"))
        if not (-1 <= x < x + width <= 1 and -1 <= y - height < y <= 1):
            raise RuntimeError(f"La leyenda de T2m de {product_name} requiere un rectángulo positivo dentro de la pantalla.")
        ticks = colourbar["ticks_c"]
        if (
            not isinstance(ticks, list) or len(ticks) < 2
            or any(not minimum_c <= float(value) <= maximum_c for value in ticks)
            or any(float(b) <= float(a) for a, b in zip(ticks, ticks[1:]))
        ):
            raise RuntimeError(f"Los rótulos Celsius de {product_name} deben estar ordenados dentro de la escala de T2m.")
        if not colourbar["font"] or not math.isfinite(float(colourbar["font_size"])) or float(colourbar["font_size"]) <= 0:
            raise RuntimeError(f"La leyenda de T2m de {product_name} requiere fuente y tamaño de letra positivo y finito.")
        surface_temperature["colourbar_rectangle"] = encode_qrectf_variant(x, y, width, height)
        colourbar["labels"] = [
            {
                "text": f"{float(value):g}", "anchor": 10,
                "position": encode_text_position_variant(
                    x - float(colourbar["label_spacing"]),
                    y - height + (float(value) - minimum_c) / (maximum_c - minimum_c) * height,
                ),
            }
            for value in ticks
        ]
        colourbar["labels"].append({
            "text": colourbar["title"], "anchor": 5,
            "position": encode_text_position_variant(x + width / 2, y + float(colourbar["title_spacing"])),
        })
    if surface_precipitation is not None:
        required_variables.append(str(require_value(variables, ("precipitation",), f"de animación {product_name}")))
        description = f"de precipitación sobre el relieve de {product_name}"
        for key in ("accumulation", "minimum_mm", "maximum_mm", "transparent_zero", "opacity", "colourmap", "reverse_colourmap", "colour_steps", "colourbar_position"):
            require_value(surface_precipitation, (key,), description)
        if surface_precipitation["accumulation"] != "since_forecast_initialization":
            raise RuntimeError(f"La precipitación de {product_name} sólo admite acumulados originales desde el inicio de la corrida.")
        minimum = float(surface_precipitation["minimum_mm"])
        maximum = float(surface_precipitation["maximum_mm"])
        if not (math.isfinite(minimum) and math.isfinite(maximum) and 0 <= minimum < maximum):
            raise RuntimeError(f"La precipitación de {product_name} requiere 0 <= minimum_mm < maximum_mm, finitos.")
        if type(surface_precipitation["transparent_zero"]) is not bool:
            raise RuntimeError(f"transparent_zero de {product_name} debe ser un booleano.")
        if surface_precipitation["transparent_zero"] and minimum != 0:
            raise RuntimeError(f"transparent_zero de {product_name} requiere minimum_mm: 0 para conservar toda lluvia positiva.")
        opacity = surface_precipitation["opacity"]
        if type(opacity) not in (int, float) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
            raise RuntimeError(f"La opacidad de precipitación de {product_name} debe ser un número finito entre 0 y 1.")
        surface_precipitation["minimum_plot_mm"] = minimum
        if type(surface_precipitation["colour_steps"]) is not int or surface_precipitation["colour_steps"] < 2:
            raise RuntimeError(f"La precipitación de {product_name} requiere al menos dos pasos de color.")
        position = surface_precipitation["colourbar_position"]
        x, y, width, height = (float(require_value(position, (key,), description)) for key in ("x", "y", "width", "height"))
        if not (-1 <= x < x + width <= 1 and -1 <= y - height < y <= 1):
            raise RuntimeError(f"La leyenda de precipitación de {product_name} requiere un rectángulo positivo dentro de la pantalla.")
        surface_precipitation["colourbar_rectangle"] = encode_qrectf_variant(x, y, width, height)
        note = require_value(surface_precipitation, ("note",), description)
        note_x, note_y = (float(require_value(note, ("position", key), description)) for key in ("x", "y"))
        if not (-1 <= note_x <= 1 and -1 <= note_y <= 1) or not require_value(note, ("font",), description) or float(require_value(note, ("font_size",), description)) <= 0:
            raise RuntimeError(f"La nota de precipitación de {product_name} requiere posición dentro de pantalla, fuente y tamaño positivo.")
        surface_precipitation["note_position"] = encode_text_position_variant(note_x, note_y)
    if relative_humidity is not None:
        if surface_pressure is None:
            raise RuntimeError(f"La humedad relativa de {product_name} requiere presión superficial para excluir niveles bajo tierra.")
        required_variables.append(str(require_value(variables, ("relative_humidity",), f"de animación {product_name}")))
        for key in ("pressure", "threshold_percent", "maximum_percent", "opacity", "hue", "chroma", "luminance", "colourmap", "reverse_colourmap", "colour_steps", "ray_step_size"):
            require_value(relative_humidity, (key,), f"de humedad relativa de {product_name}")
        if not 0 <= float(relative_humidity["threshold_percent"]) < float(relative_humidity["maximum_percent"]) <= 100:
            raise RuntimeError(f"La humedad relativa de {product_name} requiere 0 <= threshold_percent < maximum_percent <= 100.")
        if not 0 <= float(relative_humidity["opacity"]) <= 1:
            raise RuntimeError(f"La opacidad de humedad relativa de {product_name} debe estar entre 0 y 1.")
        if int(relative_humidity["colour_steps"]) < 2 or float(relative_humidity["ray_step_size"]) <= 0:
            raise RuntimeError(f"El DVR de humedad relativa de {product_name} requiere al menos dos pasos de color y ray_step_size positivo.")
        # El primer float32 superior al umbral deja RH igual al umbral transparente.
        relative_humidity["minimum_percent"] = float(np.nextafter(
            np.float32(relative_humidity["threshold_percent"]), np.float32(np.inf),
        ))
        if relative_humidity["minimum_percent"] >= float(relative_humidity["maximum_percent"]):
            raise RuntimeError(f"El intervalo de humedad relativa de {product_name} no contiene valores float32 sobre el umbral.")
        position = require_value(relative_humidity, ("colourbar_position",), f"de humedad relativa de {product_name}")
        relative_humidity["colourbar_rectangle"] = encode_qrectf_variant(*(
            require_value(position, (key,), f"de leyenda de humedad relativa de {product_name}")
            for key in ("x", "y", "width", "height")
        ))
    if cold_air is not None:
        if surface_pressure is None:
            raise RuntimeError(f"La masa fría de {product_name} requiere presión superficial para excluir niveles bajo tierra.")
        for role in ("air_temperature", "specific_humidity"):
            name = str(require_value(variables, (role,), f"de animación {product_name}"))
            required_variables.append(name)
            derived_variable_mappings.append(f"{role}:{name}")
        require_value(cold_air, ("equivalent_potential_temperature_threshold_k",), f"de masa fría de {product_name}")
        for key in ("minimum_tpe_k", "opacity", "hue", "chroma", "luminance", "colourmap", "reverse_colourmap", "colour_steps", "ray_step_size"):
            require_value(cold_air, (key,), f"de masa fría de {product_name}")
        if not 0 <= float(cold_air["opacity"]) <= 1:
            raise RuntimeError(f"La opacidad de la masa fría de {product_name} debe estar entre 0 y 1.")
        # El campo derivado es float32: el límite anterior al umbral respeta TPE < umbral.
        cold_air["maximum_tpe_k"] = float(np.nextafter(
            np.float32(cold_air["equivalent_potential_temperature_threshold_k"]), np.float32(-np.inf),
        ))
        if float(cold_air["minimum_tpe_k"]) >= cold_air["maximum_tpe_k"]:
            raise RuntimeError(f"El mínimo de la escala TPE de {product_name} debe ser inferior al umbral.")
        if int(cold_air["colour_steps"]) < 2 or float(cold_air["ray_step_size"]) <= 0:
            raise RuntimeError(f"El DVR de {product_name} requiere al menos dos pasos de color y ray_step_size positivo.")
    if cloud_cover is not None:
        if surface_pressure is None:
            raise RuntimeError(f"La nubosidad de {product_name} requiere presión superficial para excluir niveles bajo tierra.")
        required_variables.append(str(require_value(variables, ("cloud_cover",), f"de animación {product_name}")))
        for key in ("minimum_percent", "maximum_percent", "maximum_opacity", "colour_steps", "luminance", "ray_step_size", "colourbar_position"):
            require_value(cloud_cover, (key,), f"de nubosidad de {product_name}")
        if not 0 <= float(cloud_cover["minimum_percent"]) < float(cloud_cover["maximum_percent"]) <= 100:
            raise RuntimeError(f"La nubosidad de {product_name} requiere 0 <= minimum_percent < maximum_percent <= 100.")
        if not 0 <= float(cloud_cover["maximum_opacity"]) <= 1:
            raise RuntimeError(f"La opacidad de nubosidad de {product_name} debe estar entre 0 y 1.")
        if int(cloud_cover["colour_steps"]) < 2 or float(cloud_cover["ray_step_size"]) <= 0:
            raise RuntimeError(f"El volumen nuboso de {product_name} requiere al menos dos pasos de color y ray_step_size positivo.")
        if not 0 <= float(cloud_cover["luminance"]) <= 100:
            raise RuntimeError(f"La luminosidad nubosa de {product_name} debe estar entre 0 y 100.")
        position = cloud_cover["colourbar_position"]
        x, y, width, height = (float(require_value(position, (key,), f"de leyenda nubosa de {product_name}")) for key in ("x", "y", "width", "height"))
        if not (-1 <= x < x + width <= 1 and -1 <= y - height < y <= 1):
            raise RuntimeError(f"La leyenda nubosa de {product_name} requiere un rectángulo positivo dentro de la pantalla.")
        cloud_cover["colourbar_rectangle"] = encode_qrectf_variant(x, y, width, height)
        # Gris sRGB equivalente a la luminosidad CIELAB; el alfa se declara por nodos.
        luminance = float(cloud_cover["luminance"])
        linear_grey = luminance / 903.3 if luminance <= 8 else ((luminance + 16) / 116) ** 3
        grey = 12.92 * linear_grey if linear_grey <= 0.0031308 else 1.055 * linear_grey ** (1 / 2.4) - 0.055
        cloud_cover["colour_xyz"] = encode_met3d_rgb_colour([round(grey * 255)] * 3)
    section_pv = any(field["derived"] for section in horizontal_sections for field in section["fields"])
    if potential_vorticity is not None or section_pv:
        for variable_name in ("air_temperature", "wind_u", "wind_v"):
            required_variables.append(str(require_value(variables, (variable_name,), f"de cálculo de PV de {product_name}")))
        derived_variable_mappings.extend([
            f"eastward_wind:{variables['wind_u']}",
            f"northward_wind:{variables['wind_v']}",
            f"air_temperature:{variables['air_temperature']}",
        ])
    if potential_vorticity is not None:
        require_value(potential_vorticity, ("pressure", "bottom_hpa"), f"del objeto PV de {product_name}")
        require_value(potential_vorticity, ("pressure", "top_hpa"), f"del objeto PV de {product_name}")
        # Las configuraciones anteriores conservan su isosuperficie sin cambios.
        pv_render_mode = potential_vorticity.get("render_mode", "isosurface")
        if pv_render_mode == "isosurface":
            require_value(potential_vorticity, ("isosurface_pvu",), f"del objeto PV de {product_name}")
        elif pv_render_mode == "dvr":
            for key in ("threshold_pvu", "ray_step_size", "colour_steps", "colourbar_position"):
                require_value(potential_vorticity, (key,), f"del DVR de PV de {product_name}")
            reference = require_value(potential_vorticity, ("colour_reference",), f"del DVR de {product_name}")
            reference_section = next((section for section in horizontal_sections if section["name"] == require_value(reference, ("section",), f"de referencia de color de {product_name}")), None)
            reference_layer = require_value(reference, ("layer",), f"de referencia de color de {product_name}")
            if reference_section is None or reference_layer not in reference_section["layers"]:
                raise RuntimeError(f"El DVR de {product_name} requiere una sección y un gráfico de referencia habilitados.")
            colour_reference = reference_section["layers"][reference_layer]
            if colour_reference not in reference_section["scalar_layers"] or colour_reference["type"] != "filled_contours" or colour_reference["variable"] != "potential_vorticity":
                raise RuntimeError(f"La referencia del DVR de {product_name} debe ser un relleno de PV habilitado.")
            potential_vorticity["colour_style"] = colour_reference
            minimum_pvu = float(colour_reference["minimum"])
            maximum_pvu = float(colour_reference["maximum"])
            threshold_pvu = float(potential_vorticity["threshold_pvu"])
            if (
                not all(math.isfinite(value) for value in (minimum_pvu, maximum_pvu, threshold_pvu))
                or not minimum_pvu < threshold_pvu <= maximum_pvu or threshold_pvu >= 0
            ):
                raise RuntimeError(f"El DVR de {product_name} requiere minimum_pvu < threshold_pvu <= maximum_pvu y un umbral negativo.")
            if (
                not math.isfinite(float(potential_vorticity["ray_step_size"]))
                or float(potential_vorticity["ray_step_size"]) <= 0
                or int(potential_vorticity["colour_steps"]) < 2
            ):
                raise RuntimeError(f"El DVR de {product_name} requiere ray_step_size positivo y al menos dos pasos de color.")
            # Recortar la función HCL a PV <= umbral sin estirar sus extremos originales.
            fraction = (threshold_pvu - minimum_pvu) / (maximum_pvu - minimum_pvu)
            dark_luminance = float(colour_reference["dark_luminance"])
            light_luminance = float(colour_reference["light_luminance"])
            potential_vorticity["minimum_pvu"] = minimum_pvu
            potential_vorticity["minimum_si"] = minimum_pvu * 1e-6
            potential_vorticity["maximum_si"] = threshold_pvu * 1e-6
            potential_vorticity["threshold_luminance"] = dark_luminance + fraction * (light_luminance - dark_luminance)
            position = potential_vorticity["colourbar_position"]
            x, y, width, height = (float(require_value(position, (key,), f"de leyenda DVR de {product_name}")) for key in ("x", "y", "width", "height"))
            if not (-1 <= x < x + width <= 1 and -1 <= y - height < y <= 1):
                raise RuntimeError(f"La leyenda DVR de {product_name} requiere un rectángulo positivo dentro de la pantalla.")
            potential_vorticity["colourbar_rectangle"] = encode_qrectf_variant(x, y, width, height)
        else:
            raise RuntimeError(f"El modo de PV de {product_name} debe ser 'isosurface' o 'dvr': {pv_render_mode}.")
        opacity = float(require_value(potential_vorticity, ("opacity",), f"del objeto PV de {product_name}"))
        if not 0.0 <= opacity <= 1.0:
            raise RuntimeError(f"La opacidad de PV de {product_name} debe estar entre 0 y 1.")
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
    for section in horizontal_sections:
        for field in section["fields"]:
            if not field["derived"]:
                required_variables.append(field["name"])
    require_value(animation, ("camera",), f"de animación {product_name}")

    # Cada producto declara los campos y las máscaras de su NetCDF de visualización.
    data_preparation = animation.get("data_preparation")
    if reuse_netcdf and data_preparation is None:
        raise RuntimeError(f"La animación {product_name} no genera un NetCDF de visualización para --reuse-temporal.")
    if (cold_air is not None or relative_humidity is not None or streamlines is not None or cloud_cover is not None or surface_precipitation is not None or any(section["wind"] is not None for section in horizontal_sections)) and data_preparation is None:
        raise RuntimeError(f"La animación {product_name} requiere data_preparation para excluir niveles bajo tierra.")
    preparation_variables = {}
    surface_pressure_name = None
    if data_preparation is not None:
        definitions = require_value(data_preparation, ("variables",), f"de preparación de {product_name}")
        if not isinstance(definitions, dict):
            raise RuntimeError(f"data_preparation.variables de {product_name} debe ser un mapa YAML.")
        for role, definition in definitions.items():
            name = str(require_value(variables, (role,), f"de animación {product_name}"))
            preparation_variables[name] = definition
        missing_fields = [name for name in required_variables if name not in preparation_variables]
        if missing_fields:
            raise RuntimeError(f"La preparación de {product_name} no declara los campos requeridos por sus objetos: {', '.join(missing_fields)}.")
        required_variables.extend(preparation_variables)
        pressure_role = data_preparation.get("surface_pressure")
        if pressure_role is not None:
            surface_pressure_name = str(require_value(variables, (pressure_role,), f"de animación {product_name}"))
    if streamlines is not None:
        for role in ("wind_u", "wind_v", "wind_omega"):
            if preparation_variables[variables[role]].get("mask_below_surface") is not True or surface_pressure_name is None:
                raise RuntimeError(f"La circulación 3D de {product_name} requiere enmascarar {variables[role]} bajo superficie y declarar presión superficial.")
    for section in horizontal_sections:
        if section["wind"] is not None:
            for role in ("wind_u", "wind_v"):
                if preparation_variables[variables[role]].get("mask_below_surface") is not True or surface_pressure_name is None:
                    raise RuntimeError(f"La sección {section['name']} de {product_name} requiere enmascarar {variables[role]} bajo superficie y declarar presión superficial.")
    if cloud_cover is not None:
        cloud_name = variables["cloud_cover"]
        if preparation_variables[cloud_name].get("mask_below_surface") is not True or surface_pressure_name is None:
            raise RuntimeError(f"La nubosidad {cloud_name} de {product_name} requiere mask_below_surface: true y presión superficial en data_preparation.")
    if relative_humidity is not None:
        humidity_name = variables["relative_humidity"]
        if preparation_variables[humidity_name].get("mask_below_surface") is not True or surface_pressure_name is None:
            raise RuntimeError(f"La humedad relativa {humidity_name} de {product_name} requiere mask_below_surface: true y presión superficial en data_preparation.")
        if cold_air is not None:
            # El DVR conjunto comparte caja: limitar sólo las entradas de TPE a su capa.
            pressure = require_value(cold_air, ("pressure",), f"de masa fría de {product_name}")
            for role in ("air_temperature", "specific_humidity"):
                name = variables[role]
                preparation_variables[name] = {**preparation_variables[name], "pressure": pressure}

    return {
        "objects": {
            "surface_pressure": surface_pressure,
            "surface_temperature": surface_temperature,
            "surface_precipitation": surface_precipitation,
            "geographic_lines": geographic_lines,
            "potential_vorticity": potential_vorticity,
            "horizontal_sections": horizontal_sections,
            "jet": jet,
            "cold_air": cold_air,
            "cloud_cover": cloud_cover,
            "relative_humidity": relative_humidity,
            "mean_sea_level_pressure": mean_sea_level_pressure,
            "streamlines": streamlines,
            "time_label": time_label,
        },
        "variables": variables,
        "required_variables": required_variables,
        "derived_variable_mappings": derived_variable_mappings,
        "preparation_variables": preparation_variables,
        "surface_pressure_name": surface_pressure_name,
        "pv_render_mode": pv_render_mode,
    }


def select_product_data(animation: dict, scene: dict, product: dict, netcdf_file: Path) -> tuple[dict, dict]:
    """Selecciona plazos y niveles nativos y resuelve los límites gráficos solicitados."""

    product_name = str(animation["name"])
    variables = product["variables"]
    required_variables = product["required_variables"]
    surface_temperature = product["objects"]["surface_temperature"]
    surface_precipitation = product["objects"]["surface_precipitation"]
    cloud_cover = product["objects"]["cloud_cover"]
    horizontal_sections = product["objects"]["horizontal_sections"]
    relative_humidity = product["objects"]["relative_humidity"]
    mean_sea_level_pressure = product["objects"]["mean_sea_level_pressure"]
    streamlines = product["objects"]["streamlines"]
    time_label = product["objects"]["time_label"]
    # Revisar la corrida NetCDF y derivar su identidad, fecha y duración.
    metadata = read_netcdf_metadata(netcdf_file, list(dict.fromkeys(required_variables)), product_name)
    model_identifier = f"{metadata['center']}-{metadata['model']}"
    timeline = build_timeline(animation, metadata, product_name)
    if cloud_cover is not None or surface_precipitation is not None:
        with Dataset(netcdf_file) as dataset:
            description = f"{model_identifier}, corrida {metadata['forecast_date']}, {netcdf_file.name}"
            if cloud_cover is not None:
                field = dataset[variables["cloud_cover"]]
                if field.dimensions != ("time", "lev", "latitude", "longitude") or getattr(field, "units", "") != "%":
                    raise RuntimeError(f"{description}: {field.name} requiere cobertura por nivel en % y dimensiones isobáricas canónicas.")
            if surface_precipitation is not None:
                field = dataset[variables["precipitation"]]
                if field.dimensions != ("time", "latitude", "longitude") or getattr(field, "units", "") not in ("kg/m^2", "mm") or getattr(field, "statistical_process", "") != "acc":
                    raise RuntimeError(f"{description}: {field.name} requiere precipitación acumulada de superficie en kg/m^2 o mm.")
                if surface_precipitation["transparent_zero"]:
                    # Revisar sólo el campo 2D: no recorrer ni regenerar la nubosidad 3D.
                    # El corte se coloca bajo el mínimo positivo, sin rampas de alfa que
                    # atenúen la lluvia débil ni límites subnormales que la GPU redondee a cero.
                    positive_minimum = None
                    selected_times = set(timeline["valid_times"])
                    for index, valid_time in enumerate(metadata["valid_times"]):
                        if valid_time not in selected_times:
                            continue
                        values = np.ma.masked_invalid(field[index]).compressed()
                        if np.any(values < 0):
                            raise RuntimeError(f"{description}: {field.name}, plazo {valid_time}, contiene precipitación acumulada negativa; no se aplica transparencia.")
                        positive = values[values > 0]
                        if positive.size:
                            current_minimum = float(positive.min())
                            positive_minimum = current_minimum if positive_minimum is None else min(positive_minimum, current_minimum)
                    maximum = float(surface_precipitation["maximum_mm"])
                    # Si toda la selección es cero o NoData, sólo queda visible el mapa.
                    surface_precipitation["minimum_plot_mm"] = min(positive_minimum / 2, maximum / 2) if positive_minimum is not None else maximum / 2
                    print(f"Precipitación {description}: cero transparente; mínimo positivo {positive_minimum} mm, corte gráfico {surface_precipitation['minimum_plot_mm']:g} mm; positivos con opacidad {surface_precipitation['opacity']:g}.")
                # La equivalencia 1 kg/m² = 1 mm sólo afecta a la leyenda; no cambia los datos.
                surface_precipitation["initialization_text"] = metadata["forecast_date"].strftime("%Y-%m-%d %H UTC")
                print(f"Precipitación {description}: acumulado original desde inicio, sin diferencias temporales; los NoData se conservan.")
    if streamlines is not None and streamlines["representation"] == "particles_with_trails":
        trail_seconds = float(streamlines["trail_hours"]) * 3600
        if timeline["step_seconds"] is None or trail_seconds % timeline["step_seconds"]:
            raise RuntimeError(
                f"El rastro de {product_name}, {metadata['center']}-{metadata['model']}, corrida {metadata['forecast_date']}, "
                "debe abarcar un número entero de intervalos nativos de pronóstico."
            )
        # Met.3D requiere cuatro vértices incluso para dibujar una esfera en +0.
        # Un intervalo futuro aporta geometría; el modo de rastro pasado lo oculta.
        streamlines["geometry_forward_hours"] = timeline["step_seconds"] / 3600
    if mean_sea_level_pressure is not None or streamlines is not None:
        with Dataset(netcdf_file, "r") as dataset:
            description = f"{model_identifier}, corrida {metadata['forecast_date']}, {netcdf_file.name}"
            fields = [("mean_sea_level_pressure", "Pa", ("time", "latitude", "longitude"))] if mean_sea_level_pressure is not None else []
            if streamlines is not None:
                fields.extend((role, units, ("time", "lev", "latitude", "longitude")) for role, units in (("wind_u", "m/s"), ("wind_v", "m/s"), ("wind_omega", "Pa/s")))
                if getattr(dataset["lev"], "units", "") != "millibars":
                    raise RuntimeError(f"{description}: lev requiere unidades millibars para la circulación 3D.")
                seed_levels = streamlines["seed_pressure_levels_hpa"]
                if not isinstance(seed_levels, list) or not seed_levels:
                    raise RuntimeError(f"{description}: se requiere una lista no vacía de niveles de inicio del flujo.")
                for level in seed_levels:
                    if float(level) not in dataset["lev"][:] or not float(streamlines["pressure"]["top_hpa"]) <= float(level) <= float(streamlines["pressure"]["bottom_hpa"]):
                        raise RuntimeError(f"{description}: el nivel de inicio {level} hPa no es nativo o queda fuera de la capa de circulación.")
                if not isinstance(streamlines["seed_areas"], dict) or not streamlines["seed_areas"]:
                    raise RuntimeError(f"{description}: se requieren áreas de inicio para la circulación.")
                for name, area in streamlines["seed_areas"].items():
                    west, south, east, north = (float(require_value(area, (key,), f"del área {name} de {product_name}")) for key in ("west", "south", "east", "north"))
                    west_limit = max(float(dataset["longitude"][:].min()), float(scene["area"]["west"]))
                    east_limit = min(float(dataset["longitude"][:].max()), float(scene["area"]["east"]))
                    south_limit = max(float(dataset["latitude"][:].min()), float(scene["area"]["south"]))
                    north_limit = min(float(dataset["latitude"][:].max()), float(scene["area"]["north"]))
                    if not west_limit <= west < east <= east_limit or not south_limit <= south < north <= north_limit:
                        raise RuntimeError(f"{description}: el área de inicio {name} excede los datos disponibles o la escena.")
            for role, units, dimensions in fields:
                field = dataset[variables[role]]
                if field.dimensions != dimensions or getattr(field, "units", "") != units:
                    raise RuntimeError(f"{description}: {field.name} requiere dimensiones {dimensions} y unidades {units}.")
    if surface_temperature is not None:
        with Dataset(netcdf_file, "r") as dataset:
            description = f"{model_identifier}, corrida {metadata['forecast_date']}, {netcdf_file.name}"
            for role, units in (("air_temperature_2m", "K"), ("surface_pressure", "Pa")):
                field = dataset[variables[role]]
                if field.dimensions != ("time", "latitude", "longitude") or getattr(field, "units", "") != units:
                    raise RuntimeError(f"{description}: {field.name} requiere dimensiones de superficie canónicas y unidades {units}.")
    if time_label is not None:
        description = f"Etiqueta temporal de {product_name}, {model_identifier}, {netcdf_file.name}"
        for key in ("text_prefix", "text_suffix", "font", "font_size", "position", "font_colour", "background_colour"):
            require_value(time_label, (key,), description)
        if not metadata["model"]:
            raise RuntimeError(f"{description}: el NetCDF no declara un nombre de modelo utilizable.")
        if not time_label["font"] or not math.isfinite(float(time_label["font_size"])) or float(time_label["font_size"]) <= 0:
            raise RuntimeError(f"{description}: se requieren fuente y tamaño de letra positivo y finito.")
        x, y = (float(require_value(time_label, ("position", key), description)) for key in ("x", "y"))
        if not (-1 <= x <= 1 and -1 <= y <= 1):
            raise RuntimeError(f"{description}: la posición en pantalla requiere x e y entre -1 y 1.")
        time_label["position_variant"] = encode_text_position_variant(x, y)
        time_label["font_colour_variant"] = encode_text_colour_variant(time_label["font_colour"], description)
        time_label["background_colour_variant"] = encode_text_colour_variant(time_label["background_colour"], description)
    if relative_humidity is not None:
        with Dataset(netcdf_file) as dataset:
            humidity = dataset[variables["relative_humidity"]]
            description = f"{model_identifier}, corrida {metadata['forecast_date']}, {netcdf_file.name}"
            if humidity.dimensions != ("time", "lev", "latitude", "longitude") or getattr(humidity, "units", "") != "%":
                raise RuntimeError(f"{description}: {humidity.name} requiere dimensiones isobáricas canónicas y unidades %.")
            if getattr(dataset["lev"], "units", "") != "millibars":
                raise RuntimeError(f"{description}: lev requiere unidades millibars para el volumen de humedad relativa.")
            if relative_humidity["pressure"] == "all_available":
                pressure_levels = dataset["lev"][:]
                relative_humidity["pressure"] = {
                    "bottom_hpa": min(float(np.max(pressure_levels)), float(scene["view_pressure"]["bottom_hpa"])),
                    "top_hpa": max(float(np.min(pressure_levels)), float(scene["view_pressure"]["top_hpa"])),
                }
                print(f"Humedad relativa {description}: todos los niveles nativos se conservan; caja visible {relative_humidity['pressure']['bottom_hpa']:g}--{relative_humidity['pressure']['top_hpa']:g} hPa.")
    trajectory = animation["camera"].get("trajectory")
    if trajectory and require_value(trajectory, ("enabled",), f"de cámara de {product_name}"):
        trajectory_type = require_value(trajectory, ("type",), f"de cámara de {product_name}")
        if trajectory_type != "orbit":
            raise RuntimeError(f"La trayectoria '{trajectory_type}' de {product_name} no está disponible.")
        minimum_frames = int(require_value(trajectory, ("minimum_frames",), f"de cámara de {product_name}"))
        frames_per_interval = int(require_value(trajectory, ("frames_per_interval",), f"de cámara de {product_name}"))
        if minimum_frames < 3 or frames_per_interval < 1:
            raise RuntimeError(f"La trayectoria de {product_name} requiere al menos tres fotogramas y un fotograma por intervalo.")
        intervals = len(timeline["valid_times"]) - 1
        if intervals:
            frames_per_interval = max(frames_per_interval, math.ceil((minimum_frames + 1) / len(timeline["valid_times"])))
            frame_count = len(timeline["valid_times"]) * frames_per_interval
        else:
            frame_count = minimum_frames + 1
            frames_per_interval = frame_count + 1
        timeline["frames_per_interval"] = frames_per_interval
        timeline["camera_runtime_seconds"] = frame_count
        timeline["frame_count"] = frame_count
    if horizontal_sections:
        select_horizontal_section_data(horizontal_sections, variables, scene, netcdf_file, metadata, timeline,
                                       product["preparation_variables"], product["surface_pressure_name"])
    return metadata, timeline


def prepare_scene_geometry(scene: dict, product: dict, product_name: str) -> list[dict]:
    """Construye una sola definición de cajas para la escena y sus semillas."""

    potential_vorticity = product["objects"]["potential_vorticity"]
    jet = product["objects"]["jet"]
    cold_air = product["objects"]["cold_air"]
    cloud_cover = product["objects"]["cloud_cover"]
    relative_humidity = product["objects"]["relative_humidity"]
    streamlines = product["objects"]["streamlines"]
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
    for object_name, configuration in (("potential_vorticity", potential_vorticity), ("jet", jet), ("cold_air", cold_air), ("cloud_cover", cloud_cover), ("relative_humidity", relative_humidity), ("streamlines", streamlines)):
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

    if streamlines is not None:
        streamlines["seed_boxes"] = []
        for area_name, area in streamlines["seed_areas"].items():
            for level in streamlines["seed_pressure_levels_hpa"]:
                seed_box = {
                    "name": f"{scene['name']}_{area_name}_seeds_{float(level):g}",
                    "pressure": {"bottom_hpa": float(level), "top_hpa": float(level)},
                    "horizontal2d_coords": encode_qrectf_variant(area["west"], area["south"], float(area["east"]) - float(area["west"]), float(area["north"]) - float(area["south"])),
                    "index": len(object_bounding_boxes) + 2,
                }
                object_bounding_boxes.append(seed_box)
                streamlines["seed_boxes"].append(seed_box)

    return object_bounding_boxes


