"""Define secciones isobáricas y los gráficos meteorológicos que comparten su nivel."""

from __future__ import annotations

import math
import re
import uuid
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from visualize.met3D.configuration import require_value
from visualize.met3D.native import encode_uuid_variant, encode_text_colour_variant, encode_qrectf_variant
from visualize.met3D.netcdf import pressure_level_mask


def prepare_horizontal_sections(objects: dict, variables: dict, product_name: str) -> list[dict]:
    """Resuelve los campos de cada sección según sus gráficos habilitados."""

    definitions = objects.get("horizontal_sections", {})
    if not isinstance(definitions, dict):
        raise RuntimeError(f"horizontal_sections de {product_name} debe ser un mapa de secciones con nombre.")
    sections = []
    for name, section in definitions.items():
        description = f"de sección {name} de {product_name}"
        if not isinstance(name, str) or re.fullmatch(r"[a-zA-Z0-9_-]+", name) is None:
            raise RuntimeError(f"El nombre de sección {name} de {product_name} sólo admite letras, números, guion y guion bajo.")
        if not isinstance(section, dict):
            raise RuntimeError(f"La definición {description} debe ser un mapa YAML.")
        if require_value(section, ("enabled",), description) is not True:
            continue
        pressure = float(require_value(section, ("pressure_hpa",), description))
        selection = require_value(section, ("level_selection",), description)
        if not math.isfinite(pressure) or pressure <= 0 or selection not in ("exact", "nearest_native"):
            raise RuntimeError(f"La configuración {description} requiere presión positiva y level_selection exact o nearest_native.")
        layers = require_value(section, ("layers",), description)
        if not isinstance(layers, dict):
            raise RuntimeError(f"layers {description} debe ser un mapa de gráficos con nombre.")
        section.update({"name": name, "fields": [], "wind": None, "scalar_layers": []})
        for layer_name, layer in layers.items():
            layer_description = f"del gráfico {layer_name} {description}"
            if not isinstance(layer_name, str) or re.fullmatch(r"[a-zA-Z0-9_-]+", layer_name) is None:
                raise RuntimeError(f"El nombre de gráfico {layer_name} {description} no es válido.")
            if not isinstance(layer, dict):
                raise RuntimeError(f"La definición {layer_description} debe ser un mapa YAML.")
            if require_value(layer, ("enabled",), layer_description) is not True:
                continue
            graph_type = require_value(layer, ("type",), layer_description)
            if graph_type == "wind_barbs":
                if section["wind"] is not None:
                    raise RuntimeError(f"La sección {name} de {product_name} admite un único gráfico de barbas.")
                roles = ("wind_u", "wind_v")
                for key in ("spacing_degrees", "min_length_degrees", "max_length_degrees", "line_width"):
                    value = float(require_value(layer, (key,), layer_description))
                    if not math.isfinite(value) or value <= 0:
                        raise RuntimeError(f"{key} {layer_description} debe ser positivo y finito.")
                if float(layer["min_length_degrees"]) > float(layer["max_length_degrees"]):
                    raise RuntimeError(f"La longitud mínima {layer_description} supera a la máxima.")
                layer["colour_variant"] = encode_text_colour_variant(require_value(layer, ("colour",), layer_description), layer_description)
                section["wind"] = layer
            elif graph_type in ("filled_contours", "line_contours"):
                role = str(require_value(layer, ("variable",), layer_description))
                roles = (role,)
                for key in ("minimum", "maximum"):
                    if not math.isfinite(float(require_value(layer, (key,), layer_description))):
                        raise RuntimeError(f"{key} {layer_description} debe ser finito.")
                if float(layer["minimum"]) >= float(layer["maximum"]):
                    raise RuntimeError(f"El mínimo {layer_description} debe ser menor que el máximo.")
                require_value(layer, ("units",), layer_description)
                value_scale = float(require_value(layer, ("value_scale",), layer_description))
                if not math.isfinite(value_scale) or value_scale <= 0:
                    raise RuntimeError(f"value_scale {layer_description} debe ser positivo y finito.")
                layer["minimum_data"] = float(layer["minimum"]) / value_scale
                layer["maximum_data"] = float(layer["maximum"]) / value_scale
                if graph_type == "filled_contours":
                    for key in ("colour_steps", "hue", "dark_luminance", "light_luminance", "chroma", "label", "legend_position", "extend_below_min", "extend_above_max"):
                        require_value(layer, (key,), layer_description)
                    if type(layer["colour_steps"]) is not int or layer["colour_steps"] < 2:
                        raise RuntimeError(f"colour_steps {layer_description} debe ser entero de al menos dos bandas.")
                    for key in ("extend_below_min", "extend_above_max"):
                        if type(layer[key]) is not bool:
                            raise RuntimeError(f"{key} {layer_description} debe ser booleano.")
                    layer["colourbar_name"] = f"{product_name} {name} {layer_name} [{layer['units']}]"
                    x, y, width, height = (float(require_value(layer["legend_position"], (key,), layer_description)) for key in ("x", "y", "width", "height"))
                    if not (-1 <= x < x + width <= 1 and -1 <= y - height < y <= 1):
                        raise RuntimeError(f"La leyenda {layer_description} debe quedar dentro de la pantalla con tamaño positivo.")
                    layer["colourbar_rectangle"] = encode_qrectf_variant(x, y, width, height)
                else:
                    for key in ("interval", "line_width"):
                        value = float(require_value(layer, (key,), layer_description))
                        if not math.isfinite(value) or value <= 0:
                            raise RuntimeError(f"{key} {layer_description} debe ser positivo y finito.")
                    layer["colour_variant"] = encode_text_colour_variant(require_value(layer, ("colour",), layer_description), layer_description)
                    layer["interval_data"] = float(layer["interval"]) / value_scale
                section["scalar_layers"].append(layer)
            else:
                raise RuntimeError(f"Tipo {graph_type} {layer_description} no admitido; use wind_barbs, filled_contours o line_contours.")
            for role in roles:
                identifier = uuid.uuid5(uuid.NAMESPACE_URL, f"metvis3d:{product_name}:section:{name}:{layer_name}:{role}")
                field = {
                    "role": role, "uuid": str(identifier), "uuid_variant": encode_uuid_variant(identifier),
                    "name": "potential_vorticity_baroclinic_metpy" if role == "potential_vorticity" else str(require_value(variables, (role,), layer_description)),
                    "derived": role == "potential_vorticity", "layer": layer,
                    "render_mode": {"wind_barbs": "disabled", "filled_contours": "filled contours", "line_contours": "line contours"}[graph_type],
                }
                section["fields"].append(field)
                if graph_type == "wind_barbs":
                    section[role] = field
        if not section["fields"]:
            raise RuntimeError(f"La sección {name} de {product_name} requiere al menos un gráfico habilitado.")
        sections.append(section)
    return sections


def select_horizontal_section_data(sections: list[dict], variables: dict, scene: dict,
                                   netcdf_file: Path, metadata: dict, timeline: dict,
                                   preparation_variables: dict, surface_pressure_name: str | None) -> None:
    """Comprueba niveles nativos y datos utilizables en cada sección y plazo."""

    with Dataset(netcdf_file, "r") as dataset:
        description = f"{metadata['center']}-{metadata['model']}, corrida {metadata['forecast_date']}, {netcdf_file.name}"
        if "lev" not in dataset.variables or getattr(dataset["lev"], "units", "") != "millibars":
            raise RuntimeError(f"{description}: las secciones requieren lev en millibars.")
        pressure_levels = np.asarray(dataset["lev"][:], dtype=float)
        if not pressure_levels.size or not np.all(np.isfinite(pressure_levels)) or np.any(np.diff(pressure_levels) >= 0):
            raise RuntimeError(f"{description}: los niveles nativos deben ser finitos y descendentes.")
        selected_times = [(index, time) for index, time in enumerate(metadata["valid_times"]) if time in timeline["valid_times"]]
        if surface_pressure_name is not None:
            surface = dataset[surface_pressure_name]
            if surface.dimensions != ("time", "latitude", "longitude") or getattr(surface, "units", "") != "Pa":
                raise RuntimeError(f"{description}: {surface_pressure_name} requiere dimensiones de superficie y unidades Pa para las máscaras de secciones.")
        for section in sections:
            requested = float(section["pressure_hpa"])
            if section["level_selection"] == "exact" and requested not in pressure_levels:
                raise RuntimeError(f"{description}: sección {section['name']}, falta el nivel nativo exacto {requested:g} hPa.")
            pressure = min(pressure_levels, key=lambda level: (abs(level - requested), -level))
            if not float(scene["view_pressure"]["top_hpa"]) <= pressure <= float(scene["view_pressure"]["bottom_hpa"]):
                raise RuntimeError(f"{description}: sección {section['name']}, nivel {pressure:g} hPa fuera de la escena.")
            section["effective_pressure_hpa"] = float(pressure)
            level_index = int(np.flatnonzero(pressure_levels == pressure)[0])
            required_fields = {}
            for field in section["fields"]:
                role = field["role"]
                if field["derived"]:
                    required_fields.update({variables[key]: units for key, units in (("air_temperature", "K"), ("wind_u", "m/s"), ("wind_v", "m/s"))})
                    if field["layer"]["units"] != "PVU" or float(field["layer"]["value_scale"]) != 1e6:
                        raise RuntimeError(f"{description}: la PV de sección {section['name']} requiere units PVU y value_scale 1000000.")
                else:
                    required_fields[field["name"]] = "m/s" if role in ("wind_u", "wind_v") else field["layer"]["units"]
            for variable_name, units in required_fields.items():
                field = dataset[variable_name]
                if field.dimensions != ("time", "lev", "latitude", "longitude") or getattr(field, "units", "") != units:
                    raise RuntimeError(f"{description}: sección {section['name']}, {variable_name} requiere dimensiones isobáricas canónicas y unidades {units}.")
            for time_index, valid_time in selected_times:
                common_wind = None
                for variable_name in required_fields:
                    values = np.ma.masked_invalid(dataset[variable_name][time_index, level_index])
                    if preparation_variables.get(variable_name, {}).get("mask_below_surface"):
                        below_surface = pressure_level_mask(np.array([pressure]), dataset[surface_pressure_name][time_index])[0]
                        values = np.ma.masked_where(below_surface, values)
                    if values.count() == 0:
                        raise RuntimeError(f"{description}: sección {section['name']}, {variable_name}, {pressure:g} hPa, plazo {valid_time}, sin datos utilizables.")
                    if section["wind"] is not None and variable_name in (variables["wind_u"], variables["wind_v"]):
                        valid = ~np.ma.getmaskarray(values)
                        common_wind = valid if common_wind is None else common_wind & valid
                if common_wind is not None and not common_wind.any():
                    raise RuntimeError(f"{description}: sección {section['name']}, {pressure:g} hPa, plazo {valid_time}, u/v sin puntos válidos en común.")
            print(f"Sección {section['name']}, {description}: solicitado {requested:g} hPa, utilizado {pressure:g} hPa; {len(selected_times)} plazos comprobados.", flush=True)
