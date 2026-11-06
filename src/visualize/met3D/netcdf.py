"""Genera el NetCDF de visualización y excluye niveles bajo superficie."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, default_fillvals, num2date


def pressure_level_mask(
    pressure_levels_hpa: np.ndarray,
    surface_pressure_pa: np.ma.MaskedArray,
) -> np.ndarray:
    """Excluye niveles bajo tierra y columnas sin presión superficial conocida."""

    surface_pressure = np.ma.masked_invalid(surface_pressure_pa)
    pressure_pa = np.asarray(pressure_levels_hpa, dtype=float)[:, None, None] * 100.0
    return (
        (pressure_pa > surface_pressure.filled(np.nan)[None, :, :])
        | np.ma.getmaskarray(surface_pressure)[None, :, :]
    )


def prepare_visualization_data(
    netcdf_file: Path,
    netcdf_output: Path,
    variables: dict[str, dict],
    valid_times: list[datetime],
    surface_pressure_variable: str | None = None,
    reuse_netcdf: bool = False,
) -> Path:
    """Copia campos y aplica máscaras, o valida el NetCDF existente para reutilizarlo."""

    # Revisar campos, unidades y máscaras antes de crear el NetCDF temporal.
    with Dataset(netcdf_file, "r") as source:
        description = f"{source.center}-{source.model}, corrida {source.forecast_date}, {netcdf_file.name}"
        if not variables:
            raise RuntimeError(f"{description}: se requiere al menos una variable para preparar el NetCDF.")
        surface_dimensions = ("time", "latitude", "longitude")
        pressure_dimensions = ("time", "lev", "latitude", "longitude")
        masked_variables = []
        pressure_masks = {}
        has_pressure_fields = False
        for name, definition in variables.items():
            if name not in source.variables:
                raise RuntimeError(f"{description}: falta la variable requerida {name} para preparar el NetCDF.")
            if not isinstance(definition, dict) or "units" not in definition or type(definition.get("mask_below_surface")) is not bool:
                raise RuntimeError(f"{description}: {name} requiere units y mask_below_surface como booleano.")
            field = source[name]
            if field.dimensions not in (surface_dimensions, pressure_dimensions):
                raise RuntimeError(f"{description}: {name} requiere dimensiones canónicas de superficie o presión.")
            if getattr(field, "units", "") != definition["units"]:
                raise RuntimeError(f"{description}: {name} requiere unidades {definition['units']}.")
            has_pressure_fields |= field.dimensions == pressure_dimensions
            if definition["mask_below_surface"]:
                if field.dimensions != pressure_dimensions:
                    raise RuntimeError(f"{description}: {name} es de superficie y no admite máscara de niveles isobáricos.")
                masked_variables.append(name)
            if "pressure" in definition:
                pressure = definition["pressure"]
                if field.dimensions != pressure_dimensions or not isinstance(pressure, dict) or not {"bottom_hpa", "top_hpa"} <= pressure.keys():
                    raise RuntimeError(f"{description}: la máscara vertical de {name} requiere un campo isobárico y pressure.bottom_hpa/top_hpa.")
                bottom_hpa, top_hpa = float(pressure["bottom_hpa"]), float(pressure["top_hpa"])
                if not bottom_hpa > top_hpa > 0:
                    raise RuntimeError(f"{description}: la máscara de {name} requiere bottom_hpa > top_hpa > 0.")
                pressure_masks[name] = {"bottom_hpa": bottom_hpa, "top_hpa": top_hpa}
        coordinate_names = ("time", "lev", "latitude", "longitude") if has_pressure_fields else surface_dimensions
        for name in coordinate_names:
            if name not in source.variables:
                raise RuntimeError(f"{description}: falta la coordenada requerida {name}.")
        if has_pressure_fields and getattr(source["lev"], "units", "") != "millibars":
            raise RuntimeError(f"{description}: lev requiere unidades millibars.")
        # Un renderizador multivariable comparte caja; cada campo conserva su intervalo físico.
        vertical_masks = {
            name: ((source["lev"][:] > pressure["bottom_hpa"]) | (source["lev"][:] < pressure["top_hpa"]))[:, None, None]
            for name, pressure in pressure_masks.items()
        }
        if masked_variables:
            if surface_pressure_variable not in variables:
                raise RuntimeError(f"{description}: la máscara de {', '.join(masked_variables)} requiere declarar la variable de presión superficial.")
            surface = source[surface_pressure_variable]
            if surface.dimensions != surface_dimensions or getattr(surface, "units", "") != "Pa":
                raise RuntimeError(f"{description}: {surface_pressure_variable} requiere dimensiones de superficie y unidades Pa.")

        # Asociar cada tiempo solicitado con su muestra nativa, sin interpolación temporal.
        time = source["time"]
        source_times = list(num2date(time[:], time.units, only_use_cftime_datetimes=False))
        if any(later <= earlier for earlier, later in zip(source_times, source_times[1:])):
            raise RuntimeError(f"{description}: el NetCDF contiene tiempos duplicados o desordenados.")
        if not valid_times or any(later <= earlier for earlier, later in zip(valid_times, valid_times[1:])):
            raise RuntimeError(f"{description}: la selección temporal debe ser no vacía, creciente y sin duplicados.")
        available_indexes = {value: index for index, value in enumerate(source_times)}
        time_indexes = []
        for valid_time in valid_times:
            if valid_time not in available_indexes:
                raise RuntimeError(f"{description}: no existe el tiempo nativo {valid_time} para preparar el NetCDF.")
            time_indexes.append(available_indexes[valid_time])

        # La reutilización compara origen, selección y máscaras sin leer los volúmenes.
        source_stat = netcdf_file.stat()
        preparation = json.dumps({
            "version": 1,
            "surface_pressure_variable": surface_pressure_variable,
            "variables": {
                name: {
                    "units": definition["units"],
                    "mask_below_surface": definition["mask_below_surface"],
                    **({"pressure": pressure_masks[name]} if name in pressure_masks else {}),
                }
                for name, definition in variables.items()
            },
        }, sort_keys=True)
        if reuse_netcdf:
            instruction = "Ejecute sin --reuse-temporal para generar los datos actuales."
            if not netcdf_output.is_file():
                raise RuntimeError(f"{description}: no existe el NetCDF de visualización {netcdf_output}. {instruction}")
            try:
                with Dataset(netcdf_output, "r") as prepared:
                    reuse_description = f"{description}: no se puede reutilizar {netcdf_output.name}"
                    if getattr(prepared, "visualization_complete", None) != 1:
                        raise RuntimeError(f"{reuse_description}: preparación incompleta o sin registro de finalización. {instruction}")
                    if (
                        getattr(prepared, "visualization_source", None) != str(netcdf_file.resolve())
                        or getattr(prepared, "visualization_source_size_bytes", None) != source_stat.st_size
                        or getattr(prepared, "visualization_source_mtime_ns", None) != source_stat.st_mtime_ns
                        or any(getattr(prepared, name, None) != getattr(source, name) for name in ("center", "model", "forecast_date"))
                    ):
                        raise RuntimeError(f"{reuse_description}: el archivo de origen o la corrida cambió. {instruction}")
                    if getattr(prepared, "visualization_preparation", None) != preparation:
                        raise RuntimeError(f"{reuse_description}: la selección de variables, unidades o máscaras cambió. {instruction}")
                    if set(prepared.variables) != set(coordinate_names) | set(variables):
                        raise RuntimeError(f"{reuse_description}: las variables o coordenadas no corresponden a la preparación solicitada. {instruction}")
                    for name in coordinate_names:
                        coordinate = source[name]
                        result = prepared[name]
                        expected = coordinate[time_indexes] if name == "time" else coordinate[:]
                        if (
                            result.dimensions != coordinate.dimensions
                            or getattr(result, "units", None) != getattr(coordinate, "units", None)
                            or getattr(result, "calendar", None) != getattr(coordinate, "calendar", None)
                            or not np.array_equal(result[:], expected)
                        ):
                            raise RuntimeError(f"{reuse_description}: la coordenada {name} no coincide con los niveles, malla o tiempos solicitados. {instruction}")
                    for name in variables:
                        field, result = source[name], prepared[name]
                        expected_shape = (len(valid_times), *field.shape[1:])
                        if result.dimensions != field.dimensions or result.shape != expected_shape or result.dtype != np.dtype("f4") or getattr(result, "units", None) != variables[name]["units"]:
                            raise RuntimeError(f"{reuse_description}: {name} tiene dimensiones, tamaño, precisión o unidades incompatibles. {instruction}")
            except OSError as error:
                raise RuntimeError(f"{description}: no se pudo leer el NetCDF de visualización {netcdf_output}: {error}. {instruction}") from error
            print(f"Datos de {description}: se reutiliza {netcdf_output} tras validar origen, variables, coordenadas, tiempos y máscaras.", flush=True)
            return netcdf_output

        # Mantener coordenadas y niveles nativos; time crece como en el conversor.
        with Dataset(netcdf_output, "w") as output:
            output.setncatts({name: source.getncattr(name) for name in source.ncattrs()})
            output.visualization_source = str(netcdf_file.resolve())
            output.visualization_source_size_bytes = source_stat.st_size
            output.visualization_source_mtime_ns = source_stat.st_mtime_ns
            output.visualization_preparation = preparation
            output.visualization_complete = 0
            output.visualization_mask = (
                f"Variables {', '.join(masked_variables)}: se excluye lev * 100 > {surface_pressure_variable} y columnas sin presión superficial."
                if masked_variables else "Se conservan las máscaras originales, sin exclusión por presión superficial."
            )
            if pressure_masks:
                output.visualization_pressure_masks = "; ".join(
                    f"{name}: sólo {pressure['bottom_hpa']:g}--{pressure['top_hpa']:g} hPa"
                    for name, pressure in pressure_masks.items()
                )
            for name in coordinate_names:
                coordinate = source[name]
                output.createDimension(name, None if name == "time" else len(source.dimensions[name]))
                result = output.createVariable(name, coordinate.dtype, coordinate.dimensions)
                result.setncatts({key: coordinate.getncattr(key) for key in coordinate.ncattrs() if key != "_FillValue"})
                result[:] = coordinate[time_indexes] if name == "time" else coordinate[:]
            for name in variables:
                field = source[name]
                result = output.createVariable(
                    name, "f4", field.dimensions, zlib=True,
                    fill_value=getattr(field, "_FillValue", default_fillvals["f4"]),
                )
                result.setncatts({key: field.getncattr(key) for key in field.ncattrs() if key != "_FillValue"})

            # Calcular una sola máscara por plazo y compartirla entre los campos solicitados.
            for time_index, (source_index, valid_time) in enumerate(zip(time_indexes, valid_times)):
                if masked_variables:
                    below_surface = pressure_level_mask(source["lev"][:], source[surface_pressure_variable][source_index])
                for name, definition in variables.items():
                    field = np.ma.masked_invalid(source[name][source_index])
                    if definition["mask_below_surface"]:
                        field = np.ma.masked_where(below_surface, field)
                    if name in vertical_masks:
                        field = np.ma.array(field, mask=np.ma.getmaskarray(field) | vertical_masks[name])
                    output[name][time_index] = field
                print(f"Datos de {description}: {valid_time} preparados para visualización.", flush=True)
            # Registrar finalización sólo después de escribir todos los campos y tiempos.
            output.sync()
            output.visualization_complete = 1
    return netcdf_output
