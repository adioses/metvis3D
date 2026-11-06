"""Mapas isobáricos de TPE y viento para revisar ingresos fríos."""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
from cartopy.io.shapereader import Reader
import matplotlib
import numpy as np
import yaml
from netCDF4 import Dataset, num2date

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def equivalent_potential_temperature_bolton(
    temperature: np.ma.MaskedArray,
    specific_humidity: np.ma.MaskedArray,
    pressure_hpa: float,
    description: str,
) -> np.ma.MaskedArray:
    """Calcula Bolton (1980), ecuaciones 15 y 43, como Met.3D."""

    temperature = np.ma.masked_invalid(np.ma.asarray(temperature, dtype=np.float64))
    specific_humidity = np.ma.masked_invalid(np.ma.asarray(specific_humidity, dtype=np.float64))
    missing = np.ma.getmaskarray(temperature) | np.ma.getmaskarray(specific_humidity)
    valid = ~missing
    air_temperature = temperature.data[valid]
    humidity = specific_humidity.data[valid]
    if np.any(air_temperature <= 0) or np.any((humidity < 0) | (humidity >= 1)):
        raise RuntimeError(f"{description}: TPE requiere temperatura > 0 K y humedad específica en [0, 1) kg/kg.")

    # La rama seca es el límite de la ecuación 43 cuando la humedad es cero.
    tpe = air_temperature * (1000.0 / pressure_hpa) ** 0.2854
    moist = humidity > 0
    mixing_ratio = humidity[moist] / (1.0 - humidity[moist])
    vapour_pressure_hpa = pressure_hpa * mixing_ratio / (mixing_ratio + 0.622)
    dewpoint = 243.5 / (17.67 / np.log(vapour_pressure_hpa / 6.112) - 1.0) + 273.15
    condensation_temperature = (
        1.0 / (1.0 / (dewpoint - 56.0) + np.log(air_temperature[moist] / dewpoint) / 800.0) + 56.0
    )
    mixing_ratio_g_kg = mixing_ratio * 1000.0
    tpe[moist] = (
        air_temperature[moist]
        * (1000.0 / pressure_hpa) ** (0.2854 * (1.0 - 0.28e-3 * mixing_ratio_g_kg))
        * np.exp((3.376 / condensation_temperature - 2.54e-3)
                 * mixing_ratio_g_kg * (1.0 + 0.81e-3 * mixing_ratio_g_kg))
    )
    if not np.isfinite(tpe).all():
        raise RuntimeError(f"{description}: el cálculo de TPE produjo valores no finitos.")

    # Met.3D almacena el campo derivado en float32 antes de aplicar el umbral.
    result = np.ma.masked_all(temperature.shape, dtype=np.float32)
    result[valid] = tpe.astype(np.float32)
    return result


def run_maps(
    project_root: Path,
    configuration_file: Path,
    netcdf_file: Path,
    forecast_hours: list[float] | None = None,
) -> Path:
    """Lee la corrida, calcula TPE por nivel y genera mapas, PDF y estadística."""

    # Leer la configuración meteorológica y la cartografía disponible en Conda.
    configuration = yaml.safe_load(configuration_file.read_text(encoding="utf-8"))
    scene = yaml.safe_load((project_root / configuration["scene"]).read_text(encoding="utf-8"))
    variables = configuration["variables"]
    analysis = configuration["analysis"]
    plot = configuration["plot"]
    area = scene["area"]
    threshold = float(analysis["equivalent_potential_temperature_threshold_k"])
    pressure_levels = [float(value) for value in analysis["pressure_levels_hpa"]]
    cartography = configuration["cartography"]
    cartography_directory = Path(sys.prefix) / cartography["directory_in_environment"]
    map_geometries = {}
    for name in ("coastlines", "country_boundaries"):
        shapefile = cartography_directory / cartography[name]
        if not shapefile.exists():
            raise RuntimeError(f"No existe la cartografía de {name}: {shapefile}.")
        shapes = Reader(shapefile)
        map_geometries[name] = list(shapes.geometries())
        shapes.close()

    projection = ccrs.PlateCarree()
    colours = [plot["warmer_air_colour"], plot["cold_air_colour"],
               plot["missing_colour"], plot["below_surface_colour"]]
    colourmap = ListedColormap(colours)
    colour_bounds = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], colourmap.N)
    legend = [
        Patch(facecolor=colours[1], label=f"TPE < {threshold:g} K"),
        Patch(facecolor=colours[0], edgecolor="0.6", label=f"TPE ≥ {threshold:g} K"),
        Patch(facecolor=colours[2], label="Sin datos de TPE o presión superficial"),
        Patch(facecolor=colours[3], label="Nivel bajo superficie"),
        Line2D([], [], color=plot["threshold_line_colour"], label=f"Contorno {threshold:g} K"),
    ]

    # Revisar las entradas, los niveles nativos y la selección temporal.
    with Dataset(netcdf_file, "r") as dataset:
        identity = f"{dataset.center}-{dataset.model}"
        description = f"{identity}, {netcdf_file.name}"
        forecast_date = datetime.fromisoformat(str(dataset.forecast_date))
        for name in ["time", "lev", "latitude", "longitude", *variables.values()]:
            if name not in dataset.variables:
                raise RuntimeError(f"{description}: falta la variable requerida {name}.")
        for role, units in (("air_temperature", "K"), ("specific_humidity", "kg/kg"),
                            ("wind_u", "m/s"), ("wind_v", "m/s"), ("surface_pressure", "Pa")):
            name = variables[role]
            expected_dimensions = (("time", "latitude", "longitude") if role == "surface_pressure"
                                   else ("time", "lev", "latitude", "longitude"))
            if dataset[name].dimensions != expected_dimensions or getattr(dataset[name], "units", "") != units:
                raise RuntimeError(f"{description}: {name} requiere dimensiones {expected_dimensions} y unidades {units}.")
        if getattr(dataset["lev"], "units", "") != "millibars":
            raise RuntimeError(f"{description}: lev requiere unidades millibars.")
        native_levels = np.asarray(dataset["lev"][:])
        for pressure in pressure_levels:
            if pressure not in native_levels:
                raise RuntimeError(f"{description}: no existe el nivel nativo {pressure:g} hPa.")
        if not pressure_levels or len(set(pressure_levels)) != len(pressure_levels):
            raise RuntimeError(f"{description}: se requiere una lista de niveles no vacía y sin duplicados.")
        latitude = np.asarray(dataset["latitude"][:])
        longitude = np.asarray(dataset["longitude"][:])
        if not (longitude.min() <= area["west"] < area["east"] <= longitude.max()
                and latitude.min() <= area["south"] < area["north"] <= latitude.max()):
            raise RuntimeError(f"{description}: el dominio de {scene['name']} debe estar contenido en el NetCDF.")
        latitude_indexes = np.flatnonzero((latitude >= area["south"]) & (latitude <= area["north"]))
        longitude_indexes = np.flatnonzero((longitude >= area["west"]) & (longitude <= area["east"]))
        latitude_slice = slice(int(latitude_indexes[0]), int(latitude_indexes[-1]) + 1)
        longitude_slice = slice(int(longitude_indexes[0]), int(longitude_indexes[-1]) + 1)
        latitude = latitude[latitude_slice]
        longitude = longitude[longitude_slice]
        time = dataset["time"]
        valid_times = num2date(time[:], time.units, only_use_cftime_datetimes=False)
        available_hours = np.array([(value - forecast_date).total_seconds() / 3600 for value in valid_times])
        requested_hours = forecast_hours if forecast_hours is not None else analysis["forecast_hours"]
        if requested_hours == "all_available":
            time_indexes = list(range(len(valid_times)))
        else:
            time_indexes = []
            for hour in requested_hours:
                matches = np.flatnonzero(available_hours == float(hour))
                if not matches.size:
                    raise RuntimeError(f"{description}: no existe el plazo nativo F+{hour:g} h.")
                time_indexes.append(int(matches[0]))
        if not time_indexes or len(set(time_indexes)) != len(time_indexes):
            raise RuntimeError(f"{description}: se requiere una selección temporal no vacía y sin duplicados.")

        # Submuestrear sólo las flechas; los colores conservan todas las celdas nativas.
        latitude_stride = max(1, round(float(plot["wind_spacing_degrees"]) / abs(float(np.median(np.diff(latitude))))))
        longitude_stride = max(1, round(float(plot["wind_spacing_degrees"]) / abs(float(np.median(np.diff(longitude))))))
        output_directory = (project_root / configuration["output"]["directory"] / identity
                            / forecast_date.strftime("%Y%m%d_%HZ"))
        output_directory.mkdir(parents=True, exist_ok=True)
        statistics = []
        pdf_file = output_directory / f"friaje_tpe_{identity}_{forecast_date:%Y%m%d_%HZ}.pdf"

        # Calcular cada plano sobre la superficie y conservar todos los tiempos solicitados.
        with PdfPages(pdf_file) as pdf:
            for time_index in time_indexes:
                valid_time = valid_times[time_index]
                hour = float(available_hours[time_index])
                surface = np.ma.masked_invalid(dataset[variables["surface_pressure"]][time_index, latitude_slice, longitude_slice])
                figure, axes = plt.subplots(
                    1, len(pressure_levels), figsize=plot["figure_size_inches"],
                    subplot_kw={"projection": projection}, squeeze=False,
                )
                for axis, pressure in zip(axes.flat, pressure_levels):
                    level_index = int(np.flatnonzero(native_levels == pressure)[0])
                    context = f"{description}, {valid_time:%Y-%m-%d %H:%M UTC}, F+{hour:g} h, {pressure:g} hPa"
                    below_surface = (pressure * 100 > surface.filled(np.nan)) & ~np.ma.getmaskarray(surface)
                    excluded = below_surface | np.ma.getmaskarray(surface)
                    temperature = np.ma.masked_where(excluded, np.ma.masked_invalid(
                        dataset[variables["air_temperature"]][time_index, level_index, latitude_slice, longitude_slice]))
                    humidity = np.ma.masked_where(excluded, np.ma.masked_invalid(
                        dataset[variables["specific_humidity"]][time_index, level_index, latitude_slice, longitude_slice]))
                    tpe = equivalent_potential_temperature_bolton(temperature, humidity, pressure, context)
                    missing = np.ma.getmaskarray(tpe)
                    cold_air = np.ma.filled(tpe < threshold, False)
                    categories = np.zeros(tpe.shape, dtype=np.uint8)
                    categories[cold_air] = 1
                    categories[missing] = 2
                    categories[below_surface] = 3

                    # El sombreado clasifica celdas; el contorno ubica gráficamente la frontera.
                    axis.set_extent([area["west"], area["east"], area["south"], area["north"]], crs=projection)
                    axis.pcolormesh(longitude, latitude, categories, cmap=colourmap, norm=colour_bounds,
                                    shading="nearest", transform=projection, rasterized=True)
                    if tpe.count() and float(tpe.min()) < threshold < float(tpe.max()):
                        axis.contour(longitude, latitude, tpe, levels=[threshold], corner_mask=False,
                                     colors=[plot["threshold_line_colour"]], linewidths=0.8, transform=projection)
                    for name in ("coastlines", "country_boundaries"):
                        axis.add_geometries(map_geometries[name], crs=projection, facecolor="none",
                                            edgecolor="0.2", linewidth=0.5, zorder=4)
                    gridlines = axis.gridlines(draw_labels=True, linewidth=0.35, color="0.6", alpha=0.6,
                                               xlocs=np.arange(-180, 181, plot["graticule_spacing_degrees"]),
                                               ylocs=np.arange(-90, 91, plot["graticule_spacing_degrees"]))
                    gridlines.top_labels = False
                    gridlines.right_labels = False
                    gridlines.xlabel_style = {"size": 8}
                    gridlines.ylabel_style = {"size": 8}
                    wind_u = np.ma.masked_where(excluded, np.ma.masked_invalid(
                        dataset[variables["wind_u"]][time_index, level_index, latitude_slice, longitude_slice]))
                    wind_v = np.ma.masked_where(excluded, np.ma.masked_invalid(
                        dataset[variables["wind_v"]][time_index, level_index, latitude_slice, longitude_slice]))
                    wind = axis.quiver(
                        longitude[::longitude_stride], latitude[::latitude_stride],
                        wind_u[::latitude_stride, ::longitude_stride], wind_v[::latitude_stride, ::longitude_stride],
                        transform=projection, color=plot["wind_colour"], scale=plot["wind_scale_m_s"],
                        scale_units="width", width=0.002, zorder=5,
                    )
                    axis.quiverkey(wind, 0.82, 1.035, plot["wind_reference_m_s"],
                                   f"{plot['wind_reference_m_s']:g} m/s", labelpos="E", fontproperties={"size": 8})
                    axis.set_title(f"{pressure:g} hPa", loc="left", fontsize=12)
                    statistics.append({
                        "valid_time_utc": valid_time.isoformat(), "forecast_hour": hour,
                        "pressure_hpa": pressure, "valid_cells": int(tpe.count()),
                        "cold_cells": int(cold_air.sum()), "below_surface_cells": int(below_surface.sum()),
                        "missing_cells": int((missing & ~below_surface).sum()),
                        "minimum_tpe_k": float(tpe.min()) if tpe.count() else "",
                        "maximum_tpe_k": float(tpe.max()) if tpe.count() else "",
                    })

                # Escribir una lámina por plazo y una colección PDF con los mismos mapas.
                figure.suptitle(
                    f"{identity.upper()} — TPE < {threshold:g} K y viento en niveles bajos\n"
                    f"Válido: {valid_time:%Y-%m-%d %H:%M UTC} | F+{hour:g} h | Corrida: {forecast_date:%Y-%m-%d %H:%M UTC}",
                    fontsize=13,
                )
                figure.legend(handles=legend, loc="lower center", ncol=3, fontsize=9, frameon=False)
                figure.subplots_adjust(left=0.035, right=0.985, top=0.84, bottom=0.16, wspace=0.14)
                png_file = output_directory / f"tpe_{valid_time:%Y%m%d_%H%MZ}.png"
                figure.savefig(png_file, dpi=configuration["output"]["dpi"])
                pdf.savefig(figure, dpi=configuration["output"]["dpi"])
                plt.close(figure)
                print(f"Mapa F+{hour:g} h generado: {png_file}", flush=True)

    with (output_directory / "statistics.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(statistics[0]))
        writer.writeheader()
        writer.writerows(statistics)
    print(f"Colección PDF: {pdf_file}")
    return output_directory
