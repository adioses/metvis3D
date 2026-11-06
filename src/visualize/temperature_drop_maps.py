"""Diagnóstico horizontal del enfriamiento a 2 m en una corrida meteorológica."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cartopy.crs as ccrs
from cartopy.io.shapereader import Reader
import matplotlib
import numpy as np
import yaml
from netCDF4 import Dataset, num2date
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import BoundaryNorm

from visualize.friaje_maps import equivalent_potential_temperature_bolton


def calculate_temperature_drop(
    temperature: np.ma.MaskedArray,
    valid_times: list[datetime],
    lag_hours: float,
    description: str,
) -> tuple[np.ma.MaskedArray, list[int | None]]:
    """Compara tiempos nativos separados exactamente por el intervalo indicado."""

    if lag_hours <= 0 or not valid_times:
        raise RuntimeError(f"{description}: se requiere un intervalo positivo y al menos un tiempo válido.")
    if any(later <= earlier for earlier, later in zip(valid_times, valid_times[1:])):
        raise RuntimeError(f"{description}: tiempos duplicados o desordenados.")
    temperature = np.ma.masked_invalid(np.ma.asarray(temperature, dtype=np.float64))
    earlier_indexes: list[int | None] = []
    temperature_drop = np.ma.masked_all(temperature.shape, dtype=np.float64)
    time_indexes = {value: index for index, value in enumerate(valid_times)}
    for index, valid_time in enumerate(valid_times):
        earlier_time = valid_time - timedelta(hours=lag_hours)
        if earlier_time < valid_times[0]:
            earlier_indexes.append(None)
            continue
        if earlier_time not in time_indexes:
            raise RuntimeError(
                f"{description}: falta el tiempo {earlier_time:%Y-%m-%d %H:%M UTC} "
                f"para comparar {valid_time:%Y-%m-%d %H:%M UTC} a {lag_hours:g} h."
            )
        earlier_index = time_indexes[earlier_time]
        earlier_indexes.append(earlier_index)
        # Una diferencia en kelvin tiene la misma magnitud que en grados Celsius.
        temperature_drop[index] = temperature[earlier_index] - temperature[index]
    if all(value is None for value in earlier_indexes):
        raise RuntimeError(f"{description}: la corrida no permite ninguna comparación a {lag_hours:g} h.")
    return temperature_drop, earlier_indexes


def draw_reference_map(axis, domain: dict, geometries: list, references: list[dict], spacing: float) -> None:
    """Sitúa costas, fronteras, coordenadas y celdas de referencia sobre el mapa."""

    projection = ccrs.PlateCarree()
    axis.set_extent([domain["west"], domain["east"], domain["south"], domain["north"]], crs=projection)
    axis.add_geometries(geometries, crs=projection, facecolor="none", edgecolor="0.2", linewidth=0.6, zorder=4)
    gridlines = axis.gridlines(
        draw_labels=True, linewidth=0.35, color="0.45", alpha=0.5,
        xlocs=np.arange(-180, 181, spacing), ylocs=np.arange(-90, 91, spacing),
    )
    gridlines.top_labels = False
    gridlines.right_labels = False
    gridlines.xlabel_style = {"size": 8}
    gridlines.ylabel_style = {"size": 8}
    for point in references:
        axis.plot(point["grid_longitude"], point["grid_latitude"], marker="o", markersize=3,
                  markeredgecolor="white", markeredgewidth=0.5, color="black", transform=projection, zorder=6)
        axis.text(point["grid_longitude"] + 0.35, point["grid_latitude"] + 0.2, point["name"],
                  fontsize=7, transform=projection, zorder=6,
                  bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1})


def analyze_nighttime_temperature(
    temperature_c, temperature_drop, valid_times, earlier_indexes, latitude, longitude,
    references, domain, geometries, configuration, description, output_directory, pdf,
) -> list[str]:
    """Compara una hora nocturna fija para conservar el muestreo entre días."""

    analysis = configuration["analysis"]
    nighttime = analysis["nighttime"]
    plot = configuration["plot"]
    lag_hours = float(analysis["lag_hours"])
    offset = timedelta(hours=float(nighttime["local_utc_offset_hours"]))
    local_hour = int(nighttime["local_hour"])
    if not 0 <= local_hour < 24 or lag_hours % 24:
        raise RuntimeError(f"{description}: el diagnóstico nocturno requiere hora local 0–23 e intervalo de días completos.")
    local_times = [value + offset for value in valid_times]
    selected = np.array([index for index, value in enumerate(local_times)
                         if value.hour == local_hour and value.minute == 0 and value.second == 0], dtype=int)
    paired = np.array([index for index in selected if earlier_indexes[index] is not None], dtype=int)
    if not paired.size:
        raise RuntimeError(f"{description}: no hay comparaciones nocturnas a las {local_hour:02d}:00 locales.")
    # Exigir la misma hora en todos los días cubiertos; nunca sustituirla por otra cercana.
    expected = local_times[selected[0]]
    selected_times = {local_times[index] for index in selected}
    while expected <= local_times[selected[-1]]:
        if expected not in selected_times:
            raise RuntimeError(f"{description}: falta la muestra nocturna del {expected:%Y-%m-%d %H:%M} local.")
        expected += timedelta(days=1)

    maximum = temperature_drop[paired].max(axis=0)
    minimum = temperature_c[selected].min(axis=0)
    counts = temperature_drop[paired].count(axis=0)
    maximum_indexes = paired[temperature_drop[paired].argmax(axis=0)]
    label = f"{local_hour:02d}:00 Perú (UTC{nighttime['local_utc_offset_hours']:+g})"
    rows, summary = [], []
    for point in references:
        j, i = point["latitude_index"], point["longitude_index"]
        if not temperature_c[selected, j, i].count() or not counts[j, i]:
            raise RuntimeError(f"{description}: T2m nocturna sin datos suficientes en {point['name']}.")
        maximum_index = int(maximum_indexes[j, i])
        earlier_index = earlier_indexes[maximum_index]
        minimum_index = int(selected[temperature_c[selected, j, i].argmin()])
        summary.append({
            "name": point["name"], "grid_latitude": point["grid_latitude"], "grid_longitude": point["grid_longitude"],
            "local_hour": local_hour, "utc_offset_hours": nighttime["local_utc_offset_hours"],
            "valid_temperatures": int(temperature_c[selected, j, i].count()), "valid_pairs": int(counts[j, i]),
            "maximum_drop_c": float(maximum[j, i]),
            "window_start_local": local_times[earlier_index].isoformat(), "window_end_local": local_times[maximum_index].isoformat(),
            "temperature_before_c": float(temperature_c[earlier_index, j, i]),
            "temperature_after_c": float(temperature_c[maximum_index, j, i]),
            "minimum_temperature_c": float(minimum[j, i]), "minimum_temperature_time_local": local_times[minimum_index].isoformat(),
        })
        for index in selected:
            rows.append({
                "name": point["name"], "grid_latitude": point["grid_latitude"], "grid_longitude": point["grid_longitude"],
                "valid_time_utc": valid_times[index].isoformat(), "valid_time_local": local_times[index].isoformat(),
                "utc_offset_hours": nighttime["local_utc_offset_hours"],
                "temperature_c": float(temperature_c[index, j, i]) if not np.ma.is_masked(temperature_c[index, j, i]) else "",
                "drop_c": float(temperature_drop[index, j, i]) if not np.ma.is_masked(temperature_drop[index, j, i]) else "",
            })

    figure, axes = plt.subplots(len(references), 2, figsize=plot["series_size_inches"], squeeze=False, sharex=True, sharey="col")
    dates = [local_times[index] for index in selected]
    for row, point in enumerate(references):
        j, i = point["latitude_index"], point["longitude_index"]
        axes[row, 0].plot(dates, temperature_c[selected, j, i], "o-", color="#b34d17")
        axes[row, 0].set_title(f"{point['name']} — temperatura a hora fija", loc="left", fontsize=10)
        axes[row, 0].set_ylabel("Temperatura a 2 m [°C]")
        axes[row, 1].plot(dates, temperature_drop[selected, j, i], "o-", color="#17629b")
        axes[row, 1].axhline(0, color="0.3", linewidth=0.8)
        axes[row, 1].set_title(f"{point['name']} — descenso a {lag_hours:g} h", loc="left", fontsize=10)
        axes[row, 1].set_ylabel("Descenso [°C]; positivo = enfría")
        for axis in axes[row]:
            axis.grid(alpha=0.3)
            axis.xaxis.set_major_locator(mdates.DayLocator())
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            axis.set_xlabel("Fecha local de Perú")
    figure.suptitle(f"{description} — muestras nocturnas a las {label}\n"
                   "Celdas de modelo; no son mínimas diarias ni observaciones")
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(output_directory / "nighttime_reference_series.png", dpi=configuration["output"]["dpi"])
    pdf.savefig(figure, dpi=configuration["output"]["dpi"])
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=plot["map_size_inches"], subplot_kw={"projection": ccrs.PlateCarree()})
    for axis, values, levels, colourmap, title, colour_label in zip(
        axes, (maximum, minimum), (plot["drop_levels_c"], plot["temperature_levels_c"]),
        (plot["drop_colourmap"], plot["temperature_colourmap"]),
        (f"Máximo descenso a {lag_hours:g} h", "Menor temperatura muestreada a esta hora"),
        ("Descenso [°C]; positivo = enfriamiento", "Temperatura a 2 m [°C]"),
    ):
        draw_reference_map(axis, domain, geometries, references, plot["graticule_spacing_degrees"])
        cmap = plt.get_cmap(colourmap).copy()
        cmap.set_bad(plot["missing_colour"])
        image = axis.pcolormesh(longitude, latitude, values, cmap=cmap, norm=BoundaryNorm(levels, cmap.N),
                               shading="nearest", transform=ccrs.PlateCarree(), rasterized=True)
        figure.colorbar(image, ax=axis, orientation="horizontal", pad=0.07, label=colour_label, extend="both")
        axis.set_title(title)
    figure.suptitle(f"{description} — {label}\n"
                   f"{dates[0]:%d/%m}–{dates[-1]:%d/%m}: resúmenes por celda; pueden corresponder a fechas distintas")
    figure.subplots_adjust(left=0.055, right=0.98, top=0.85, bottom=0.04, wspace=0.16)
    figure.savefig(output_directory / f"nighttime_maximum_cooling_{lag_hours:g}h.png", dpi=configuration["output"]["dpi"])
    pdf.savefig(figure, dpi=configuration["output"]["dpi"])
    plt.close(figure)

    for filename, records in (("nighttime_reference_series.csv", rows), ("nighttime_reference_summary.csv", summary)):
        with (output_directory / filename).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    with (output_directory / "nighttime_cooling_by_cell.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["latitude", "longitude", "maximum_drop_c", "window_end_utc", "minimum_temperature_c", "valid_pairs"])
        for j, lat in enumerate(latitude):
            for i, lon in enumerate(longitude):
                writer.writerow([float(lat), float(lon), float(maximum[j, i]) if counts[j, i] else "",
                                 valid_times[int(maximum_indexes[j, i])].isoformat() if counts[j, i] else "",
                                 float(minimum[j, i]) if not np.ma.is_masked(minimum[j, i]) else "", int(counts[j, i])])
    report = ["", "## Comparación nocturna a hora fija", "",
              f"Muestras a las {label}; {len(selected)} tiempos y {len(paired)} ventanas temporales disponibles.",
              "Se mantiene la misma hora en todos los días, sin interpolación. No representa la mínima de toda la noche.", "",
              "| Referencia | Mayor descenso nocturno [°C] | Inicio local | Final local | T anterior → final [°C] | Menor T a esta hora [°C] | Fecha local del mínimo |",
              "|---|---:|---|---|---|---:|---|"]
    for row in summary:
        report.append(f"| {row['name']} | {row['maximum_drop_c']:.2f} | {row['window_start_local']} | {row['window_end_local']} | "
                      f"{row['temperature_before_c']:.2f} → {row['temperature_after_c']:.2f} | {row['minimum_temperature_c']:.2f} | "
                      f"{row['minimum_temperature_time_local']} |")
    print(f"Resumen nocturno: {output_directory / 'nighttime_reference_series.png'}", flush=True)
    return report


def run_analysis(project_root: Path, configuration_file: Path, netcdf_file: Path) -> Path:
    """Muestra el flujo de lectura, comparación temporal, mapas y resultados."""

    # Leer parámetros meteorológicos y cartografía local, sin descargas.
    configuration = yaml.safe_load(configuration_file.read_text(encoding="utf-8"))
    variables = configuration["variables"]
    analysis = configuration["analysis"]
    domain = configuration["domain"]
    plot = configuration["plot"]
    lag_hours = float(analysis["lag_hours"])
    cartography = configuration["cartography"]
    cartography_directory = Path(sys.prefix) / cartography["directory_in_environment"]
    region = box(domain["west"], domain["south"], domain["east"], domain["north"])
    geometries = []
    for name in ("coastlines", "country_boundaries"):
        shapefile = cartography_directory / cartography[name]
        if not shapefile.exists():
            raise RuntimeError(f"No existe la cartografía de {name}: {shapefile}.")
        shapes = Reader(shapefile)
        # Se recorta sólo el dibujo cartográfico, nunca la malla meteorológica.
        geometries.extend(geometry.intersection(region) for geometry in shapes.geometries() if geometry.intersects(region))
        shapes.close()

    # Revisar variables de superficie y seleccionar las celdas nativas del dominio.
    with Dataset(netcdf_file, "r") as dataset:
        identity = f"{dataset.center}-{dataset.model}"
        description = f"{identity}, {netcdf_file.name}"
        forecast_date = datetime.fromisoformat(str(dataset.forecast_date))
        for name in ["time", "latitude", "longitude", *variables.values()]:
            if name not in dataset.variables:
                raise RuntimeError(f"{description}: falta la variable requerida {name}.")
        for role, units in (("temperature", "K"), ("wind_u", "m/s"), ("wind_v", "m/s")):
            field = dataset[variables[role]]
            if field.dimensions != ("time", "latitude", "longitude") or getattr(field, "units", "") != units:
                raise RuntimeError(f"{description}: {variables[role]} requiere dimensiones de superficie y unidades {units}.")
        latitude = np.asarray(dataset["latitude"][:])
        longitude = np.asarray(dataset["longitude"][:])
        if not (longitude.min() <= domain["west"] < domain["east"] <= longitude.max()
                and latitude.min() <= domain["south"] < domain["north"] <= latitude.max()):
            raise RuntimeError(f"{description}: el dominio configurado debe estar contenido en el NetCDF.")
        lat_indexes = np.flatnonzero((latitude >= domain["south"]) & (latitude <= domain["north"]))
        lon_indexes = np.flatnonzero((longitude >= domain["west"]) & (longitude <= domain["east"]))
        lat_slice = slice(int(lat_indexes[0]), int(lat_indexes[-1]) + 1)
        lon_slice = slice(int(lon_indexes[0]), int(lon_indexes[-1]) + 1)
        latitude = latitude[lat_slice]
        longitude = longitude[lon_slice]
        time = dataset["time"]
        valid_times = list(num2date(time[:], time.units, only_use_cftime_datetimes=False))
        temperature_k = np.ma.masked_invalid(np.ma.asarray(dataset[variables["temperature"]][:, lat_slice, lon_slice], dtype=float))
        wind_u = np.ma.masked_invalid(dataset[variables["wind_u"]][:, lat_slice, lon_slice])
        wind_v = np.ma.masked_invalid(dataset[variables["wind_v"]][:, lat_slice, lon_slice])

    # Comparar a la misma hora; conservar ausentes cuando falta una de las dos temperaturas.
    temperature_c = temperature_k - 273.15
    temperature_drop, earlier_indexes = calculate_temperature_drop(temperature_k, valid_times, lag_hours, description)
    paired_indexes = np.array([index for index, earlier in enumerate(earlier_indexes) if earlier is not None])
    forecast_hours = np.array([(value - forecast_date).total_seconds() / 3600 for value in valid_times])
    valid_pair_counts = temperature_drop.count(axis=0)
    maximum_drop = temperature_drop.max(axis=0)
    # Los empates se resuelven con la primera ventana válida en orden temporal.
    maximum_indexes = temperature_drop.argmax(axis=0)
    maximum_hour = np.ma.array(forecast_hours[maximum_indexes], mask=(valid_pair_counts == 0) | (maximum_drop <= 0))
    references = []
    reference_summary = []
    for point in analysis["reference_points"]:
        if not (domain["west"] <= point["longitude"] <= domain["east"]
                and domain["south"] <= point["latitude"] <= domain["north"]):
            raise RuntimeError(f"{description}: la referencia {point['name']} queda fuera del dominio.")
        j = int(np.argmin(abs(latitude - point["latitude"])))
        i = int(np.argmin(abs(longitude - point["longitude"])))
        if temperature_c[:, j, i].count() == 0 or temperature_drop[:, j, i].count() == 0:
            raise RuntimeError(f"{description}: {variables['temperature']} sin datos suficientes en {point['name']}.")
        maximum_index = int(temperature_drop[:, j, i].argmax())
        earlier_index = earlier_indexes[maximum_index]
        minimum_index = int(temperature_c[:, j, i].argmin())
        reference = {**point, "latitude_index": j, "longitude_index": i,
                     "grid_latitude": float(latitude[j]), "grid_longitude": float(longitude[i])}
        references.append(reference)
        reference_summary.append({
            "name": point["name"], "requested_latitude": point["latitude"], "requested_longitude": point["longitude"],
            "grid_latitude": float(latitude[j]), "grid_longitude": float(longitude[i]),
            "maximum_drop_c": float(temperature_drop[maximum_index, j, i]),
            "window_start_utc": valid_times[earlier_index].isoformat(), "window_end_utc": valid_times[maximum_index].isoformat(),
            "temperature_before_c": float(temperature_c[earlier_index, j, i]),
            "temperature_after_c": float(temperature_c[maximum_index, j, i]),
            "minimum_temperature_c": float(temperature_c[minimum_index, j, i]),
            "minimum_temperature_time_utc": valid_times[minimum_index].isoformat(),
        })

    # Contrastar, cuando se solicita, T2m con el umbral de TPE del diagnóstico anterior.
    tpe_comparison = []
    tpe_configuration_file = analysis["tpe_comparison_configuration"]
    if tpe_configuration_file is not None:
        tpe_configuration = yaml.safe_load((project_root / tpe_configuration_file).read_text(encoding="utf-8"))
        tpe_variables = tpe_configuration["variables"]
        tpe_levels = tpe_configuration["analysis"]["pressure_levels_hpa"]
        tpe_threshold = float(tpe_configuration["analysis"]["equivalent_potential_temperature_threshold_k"])
        with Dataset(netcdf_file, "r") as dataset:
            for name in ("lev", tpe_variables["air_temperature"], tpe_variables["specific_humidity"], tpe_variables["surface_pressure"]):
                if name not in dataset.variables:
                    raise RuntimeError(f"{description}: falta {name} para la comparación complementaria de TPE.")
            for role, units in (("air_temperature", "K"), ("specific_humidity", "kg/kg"), ("surface_pressure", "Pa")):
                name = tpe_variables[role]
                expected = (("time", "latitude", "longitude") if role == "surface_pressure"
                            else ("time", "lev", "latitude", "longitude"))
                if dataset[name].dimensions != expected or getattr(dataset[name], "units", "") != units:
                    raise RuntimeError(f"{description}: {name} requiere dimensiones {expected} y unidades {units} para TPE.")
            if getattr(dataset["lev"], "units", "") != "millibars":
                raise RuntimeError(f"{description}: lev requiere millibars para la comparación de TPE.")
            for point in references:
                j, i = point["latitude_index"], point["longitude_index"]
                global_j, global_i = int(lat_indexes[j]), int(lon_indexes[i])
                maximum_index = int(temperature_drop[:, j, i].argmax())
                surface = np.ma.masked_invalid(dataset[tpe_variables["surface_pressure"]][:, global_j, global_i])
                for level in tpe_levels:
                    matches = np.flatnonzero(dataset["lev"][:] == level)
                    if not matches.size:
                        raise RuntimeError(f"{description}: falta el nivel nativo {level:g} hPa para TPE.")
                    excluded = (level * 100 > surface.filled(np.nan)) | np.ma.getmaskarray(surface)
                    temperature = np.ma.masked_where(excluded, dataset[tpe_variables["air_temperature"]][:, int(matches[0]), global_j, global_i])
                    humidity = np.ma.masked_where(excluded, dataset[tpe_variables["specific_humidity"]][:, int(matches[0]), global_j, global_i])
                    tpe = equivalent_potential_temperature_bolton(temperature, humidity, float(level), f"{description}, {point['name']}, {level:g} hPa")
                    tpe_comparison.append({
                        "name": point["name"], "grid_latitude": float(latitude[j]), "grid_longitude": float(longitude[i]),
                        "pressure_hpa": float(level), "threshold_k": tpe_threshold, "valid_times": int(tpe.count()),
                        "times_below_threshold": int(np.ma.filled(tpe < tpe_threshold, False).sum()),
                        "minimum_tpe_k": float(tpe.min()) if tpe.count() else "",
                        "maximum_t2m_drop_end_utc": valid_times[maximum_index].isoformat(),
                        "tpe_at_maximum_t2m_drop_k": float(tpe[maximum_index]) if not np.ma.is_masked(tpe[maximum_index]) else "",
                    })

    # Configurar escalas fijas entre plazos y preparar las salidas de esta corrida.
    projection = ccrs.PlateCarree()
    temperature_cmap = plt.get_cmap(plot["temperature_colourmap"]).copy()
    drop_cmap = plt.get_cmap(plot["drop_colourmap"]).copy()
    time_cmap = plt.get_cmap(plot["maximum_time_colourmap"]).copy()
    for colourmap in (temperature_cmap, drop_cmap, time_cmap):
        colourmap.set_bad(plot["missing_colour"])
    temperature_norm = BoundaryNorm(plot["temperature_levels_c"], temperature_cmap.N)
    drop_norm = BoundaryNorm(plot["drop_levels_c"], drop_cmap.N)
    lat_stride = max(1, round(plot["wind_spacing_degrees"] / abs(float(np.median(np.diff(latitude))))))
    lon_stride = max(1, round(plot["wind_spacing_degrees"] / abs(float(np.median(np.diff(longitude))))))
    output_directory = project_root / configuration["output"]["directory"] / identity / forecast_date.strftime("%Y%m%d_%HZ")
    output_directory.mkdir(parents=True, exist_ok=True)
    pdf_file = output_directory / f"temperature_analysis_{identity}_{forecast_date:%Y%m%d_%HZ}.pdf"
    statistics = []
    nighttime_report = []

    # Generar las temperaturas absolutas y sus diferencias, con los tiempos visibles.
    with PdfPages(pdf_file) as pdf:
        for index, valid_time in enumerate(valid_times):
            figure, axes = plt.subplots(1, 2, figsize=plot["map_size_inches"], subplot_kw={"projection": projection})
            for axis in axes:
                draw_reference_map(axis, domain, geometries, references, plot["graticule_spacing_degrees"])
            image = axes[0].pcolormesh(longitude, latitude, temperature_c[index], cmap=temperature_cmap,
                                       norm=temperature_norm, shading="nearest", transform=projection, rasterized=True)
            figure.colorbar(image, ax=axes[0], orientation="horizontal", pad=0.07, shrink=0.95,
                            label="Temperatura a 2 m [°C]", extend="both")
            axes[0].set_title("Temperatura a 2 m")
            image = axes[1].pcolormesh(longitude, latitude, temperature_drop[index], cmap=drop_cmap,
                                       norm=drop_norm, shading="nearest", transform=projection, rasterized=True)
            figure.colorbar(image, ax=axes[1], orientation="horizontal", pad=0.07, shrink=0.95,
                            label=f"T(t − {lag_hours:g} h) − T(t) [°C]; positivo = enfriamiento", extend="both")
            earlier = earlier_indexes[index]
            if earlier is None:
                axes[1].set_title(f"Descenso a {lag_hours:g} h: sin referencia anterior")
                axes[1].text(0.5, 0.5, "No disponible:\nfalta el tiempo anterior en esta corrida",
                             ha="center", va="center", transform=axes[1].transAxes,
                             bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none"})
            else:
                axes[1].set_title(f"Descenso en {lag_hours:g} h\nDesde {valid_times[earlier]:%d/%m %H:%M UTC}")
                if temperature_drop[index].count():
                    extreme = int(temperature_drop[index].argmax())
                    j, i = np.unravel_index(extreme, temperature_drop[index].shape)
                    statistics.append({
                        "valid_time_utc": valid_time.isoformat(), "reference_time_utc": valid_times[earlier].isoformat(),
                        "maximum_drop_c": float(temperature_drop[index].max()), "minimum_drop_c": float(temperature_drop[index].min()),
                        "maximum_drop_latitude": float(latitude[j]), "maximum_drop_longitude": float(longitude[i]),
                        "valid_pairs": int(temperature_drop[index].count()),
                    })
                else:
                    statistics.append({"valid_time_utc": valid_time.isoformat(), "reference_time_utc": valid_times[earlier].isoformat(),
                                       "maximum_drop_c": "", "minimum_drop_c": "", "maximum_drop_latitude": "",
                                       "maximum_drop_longitude": "", "valid_pairs": 0})
            wind = axes[1].quiver(longitude[::lon_stride], latitude[::lat_stride],
                                  wind_u[index, ::lat_stride, ::lon_stride], wind_v[index, ::lat_stride, ::lon_stride],
                                  transform=projection, color="0.2", scale=plot["wind_scale_m_s"], scale_units="width", width=0.0025, zorder=5)
            axes[1].quiverkey(wind, 0.7, 1.12, plot["wind_reference_m_s"], f"{plot['wind_reference_m_s']:g} m/s (10 m)", labelpos="E")
            figure.suptitle(f"{identity.upper()} | Corrida {forecast_date:%Y-%m-%d %H UTC}\n"
                           f"Válido {valid_time:%Y-%m-%d %H:%M UTC} — F+{forecast_hours[index]:g} h")
            figure.subplots_adjust(left=0.055, right=0.98, top=0.83, bottom=0.04, wspace=0.16)
            png_file = output_directory / f"temperature_{valid_time:%Y%m%d_%H%MZ}.png"
            figure.savefig(png_file, dpi=configuration["output"]["dpi"])
            pdf.savefig(figure, dpi=configuration["output"]["dpi"])
            plt.close(figure)
            print(f"Mapa F+{forecast_hours[index]:g} h: {png_file}", flush=True)

        # Mostrar la mayor diferencia y el final de la ventana donde ocurrió.
        figure, axes = plt.subplots(1, 2, figsize=plot["map_size_inches"], subplot_kw={"projection": projection})
        for axis in axes:
            draw_reference_map(axis, domain, geometries, references, plot["graticule_spacing_degrees"])
        image = axes[0].pcolormesh(longitude, latitude, maximum_drop, cmap=drop_cmap, norm=drop_norm,
                                   shading="nearest", transform=projection, rasterized=True)
        figure.colorbar(image, ax=axes[0], orientation="horizontal", pad=0.07, label=f"Máximo de T(t − {lag_hours:g} h) − T(t) [°C]", extend="both")
        axes[0].set_title(f"Máximo descenso en {lag_hours:g} h por celda")
        image = axes[1].pcolormesh(longitude, latitude, maximum_hour, cmap=time_cmap,
                                   vmin=forecast_hours[paired_indexes[0]] - 0.5, vmax=forecast_hours[paired_indexes[-1]] + 0.5,
                                   shading="nearest", transform=projection, rasterized=True)
        ticks = np.linspace(forecast_hours[paired_indexes[0]], forecast_hours[paired_indexes[-1]], 5)
        colourbar = figure.colorbar(image, ax=axes[1], orientation="horizontal", pad=0.07, ticks=ticks,
                                    label="Final de la ventana UTC; gris = sin enfriamiento o sin datos")
        colourbar.ax.set_xticklabels([(forecast_date + timedelta(hours=float(hour))).strftime("%d/%m %Hh") for hour in ticks], fontsize=8)
        axes[1].set_title("Momento del máximo enfriamiento positivo")
        figure.suptitle(f"{identity.upper()} — Corrida {forecast_date:%Y-%m-%d %H UTC}\n"
                       f"Ventanas evaluadas: {valid_times[paired_indexes[0]]:%d/%m %H UTC} a {valid_times[-1]:%d/%m %H UTC}")
        figure.subplots_adjust(left=0.055, right=0.98, top=0.85, bottom=0.04, wspace=0.16)
        figure.savefig(output_directory / f"maximum_cooling_{lag_hours:g}h.png", dpi=configuration["output"]["dpi"])
        pdf.savefig(figure, dpi=configuration["output"]["dpi"])
        plt.close(figure)

        # Comparar las mismas celdas de referencia durante toda la corrida.
        figure, axes = plt.subplots(len(references), 2, figsize=plot["series_size_inches"], squeeze=False, sharex=True, sharey="col")
        for row, point in enumerate(references):
            j, i = point["latitude_index"], point["longitude_index"]
            axes[row, 0].plot(valid_times, temperature_c[:, j, i], "o-", markersize=3, color="#b34d17")
            axes[row, 0].set_title(f"{point['name']} — celda {latitude[j]:g}°, {longitude[i]:g}°", loc="left", fontsize=10)
            axes[row, 0].set_ylabel("Temperatura a 2 m [°C]")
            axes[row, 1].plot(valid_times, temperature_drop[:, j, i], "o-", markersize=3, color="#17629b")
            axes[row, 1].axhline(0, color="0.3", linewidth=0.8)
            axes[row, 1].set_title(f"{point['name']} — descenso en {lag_hours:g} h", loc="left", fontsize=10)
            axes[row, 1].set_ylabel("Descenso [°C]; positivo = enfría")
            for axis in axes[row]:
                axis.grid(alpha=0.3)
                axis.set_xlim(valid_times[0], valid_times[-1])
                axis.xaxis.set_major_locator(mdates.HourLocator(interval=plot["series_tick_interval_hours"]))
                axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H UTC"))
                axis.tick_params(axis="x", labelsize=8)
        figure.suptitle(f"{identity.upper()} — Temperatura a 2 m y descenso a la misma hora\n"
                       f"Corrida {forecast_date:%Y-%m-%d %H UTC}; referencias de grilla, no estaciones observadas")
        figure.tight_layout(rect=(0, 0, 1, 0.94))
        figure.savefig(output_directory / "reference_series.png", dpi=configuration["output"]["dpi"])
        pdf.savefig(figure, dpi=configuration["output"]["dpi"])
        plt.close(figure)

        if analysis.get("nighttime") is not None:
            nighttime_report = analyze_nighttime_temperature(
                temperature_c, temperature_drop, valid_times, earlier_indexes, latitude, longitude,
                references, domain, geometries, configuration, description, output_directory, pdf,
            )

    # Registrar valores y ventanas sin atribuir automáticamente un evento de friaje.
    reference_rows = []
    for point in references:
        j, i = point["latitude_index"], point["longitude_index"]
        for index, valid_time in enumerate(valid_times):
            reference_rows.append({
                "name": point["name"], "grid_latitude": point["grid_latitude"], "grid_longitude": point["grid_longitude"],
                "valid_time_utc": valid_time.isoformat(),
                "temperature_c": float(temperature_c[index, j, i]) if not np.ma.is_masked(temperature_c[index, j, i]) else "",
                "drop_c": float(temperature_drop[index, j, i]) if not np.ma.is_masked(temperature_drop[index, j, i]) else "",
                "wind_u_10m_m_s": float(wind_u[index, j, i]) if not np.ma.is_masked(wind_u[index, j, i]) else "",
                "wind_v_10m_m_s": float(wind_v[index, j, i]) if not np.ma.is_masked(wind_v[index, j, i]) else "",
            })
    for filename, rows in (("reference_summary.csv", reference_summary), ("reference_series.csv", reference_rows), ("regional_statistics.csv", statistics)):
        with (output_directory / filename).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    if tpe_comparison:
        with (output_directory / "reference_tpe_comparison.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(tpe_comparison[0]))
            writer.writeheader()
            writer.writerows(tpe_comparison)
    with (output_directory / "maximum_cooling_by_cell.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["latitude", "longitude", "maximum_drop_c", "window_end_utc", "valid_pairs"])
        for j, lat in enumerate(latitude):
            for i, lon in enumerate(longitude):
                valid = valid_pair_counts[j, i] > 0
                writer.writerow([float(lat), float(lon), float(maximum_drop[j, i]) if valid else "",
                                 valid_times[int(maximum_indexes[j, i])].isoformat() if valid else "", int(valid_pair_counts[j, i])])
    report = [f"# Temperatura a 2 m — {identity}, corrida {forecast_date:%Y-%m-%d %H UTC}", "",
              f"Fuente: `{netcdf_file.name}`. Dominio: {domain}. Comparación: T(t − {lag_hours:g} h) − T(t).",
              f"Se generaron {len(valid_times)} mapas y {len(paired_indexes)} ventanas comparables; positivo significa enfriamiento.", "",
              "| Referencia | Celda lat/lon | Descenso máximo [°C] | Inicio UTC | Final UTC | T anterior → final [°C] | Mínimo de la serie [°C] |",
              "|---|---|---:|---|---|---|---:|"]
    for point in reference_summary:
        report.append(f"| {point['name']} | {point['grid_latitude']:g}, {point['grid_longitude']:g} | {point['maximum_drop_c']:.2f} | "
                      f"{point['window_start_utc']} | {point['window_end_utc']} | {point['temperature_before_c']:.2f} → "
                      f"{point['temperature_after_c']:.2f} | {point['minimum_temperature_c']:.2f} |")
    report.extend(["", "Las referencias son celdas de modelo próximas a coordenadas aproximadas, no estaciones observadas.",
                   "El máximo por celda puede corresponder a ventanas distintas y no representa un campo simultáneo.",
                   "Una diferencia a igual hora reduce la contribución del ciclo diurno, pero también responde a nubosidad, lluvia y otros cambios locales.",
                   "Estos productos cuantifican el enfriamiento simulado; la identificación de un friaje requiere revisar coherencia espacial, persistencia y viento."])
    report.extend(nighttime_report)
    if tpe_comparison:
        report.extend(["", "## Comparación complementaria con TPE", "",
                       f"Umbral del diagnóstico anterior: TPE < {tpe_threshold:g} K. Valores sobre la superficie, en las mismas celdas.", "",
                       "| Referencia | Nivel [hPa] | TPE mínima [K] | Tiempos válidos | Tiempos bajo el umbral | TPE al máximo descenso de T2m [K] |",
                       "|---|---:|---:|---:|---:|---:|"])
        for row in tpe_comparison:
            minimum = f"{row['minimum_tpe_k']:.2f}" if row["minimum_tpe_k"] != "" else "sin datos"
            at_maximum = f"{row['tpe_at_maximum_t2m_drop_k']:.2f}" if row["tpe_at_maximum_t2m_drop_k"] != "" else "sin datos"
            report.append(f"| {row['name']} | {row['pressure_hpa']:g} | {minimum} | {row['valid_times']} | {row['times_below_threshold']} | {at_maximum} |")
        report.extend(["", "El descenso de temperatura a 2 m y el cruce de un umbral de TPE isobárica son criterios distintos.",
                       "La ausencia de una isosuperficie de TPE sobre estas referencias no implica, por sí sola, ausencia de enfriamiento superficial."])
    (output_directory / "analysis_summary.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"PDF del diagnóstico: {pdf_file}")
    print(f"Resumen numérico: {output_directory / 'analysis_summary.md'}")
    return output_directory
