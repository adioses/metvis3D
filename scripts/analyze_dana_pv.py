"""Diagnostica una DANA austral con PV calculada desde un NetCDF en presión.

Uso:
    conda run -n metvis3d python scripts/analyze_dana_pv.py

El análisis es exploratorio. No modifica el NetCDF ni las configuraciones de
Met.3D y sólo escribe figuras y una tabla de estadísticas bajo ``outputs/``.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import metpy.calc as mpcalc
import numpy as np
import yaml
from metpy.units import units
from netCDF4 import Dataset, num2date


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_arguments() -> argparse.Namespace:
    """Obtiene la configuración y el directorio de resultados del diagnóstico."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configuration",
        type=Path,
        default=PROJECT_ROOT / "config" / "analysis" / "dana_pv_diagnostic.yaml",
        help="Archivo YAML que define el dominio, plazos, niveles y figuras.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="Directorio que reemplaza output.directory de la configuración.",
    )
    return parser.parse_args()


def load_configuration(configuration_file: Path) -> dict:
    """Lee y comprueba los parámetros meteorológicos requeridos para el diagnóstico."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración del diagnóstico DANA: {configuration_file}")

    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)

    required_paths = [
        ("source", "standardized_netcdf"),
        ("source", "air_temperature"),
        ("source", "wind_u"),
        ("source", "wind_v"),
        ("source", "geopotential_height"),
        ("domain", "west"),
        ("domain", "south"),
        ("domain", "east"),
        ("domain", "north"),
        ("analysis", "horizontal_stride"),
        ("analysis", "forecast_hours"),
        ("analysis", "overview_pressure_levels_hpa"),
        ("analysis", "vertical_pressure_levels_hpa"),
        ("analysis", "vertical_panel_forecast_hours"),
        ("analysis", "wind_pressure_level_hpa"),
        ("analysis", "geopotential_pressure_level_hpa"),
        ("analysis", "pv_thresholds_pvu"),
        ("plot", "pv_filled_levels_pvu"),
        ("plot", "pv_contours_pvu"),
        ("plot", "geopotential_contour_interval_gpm"),
        ("plot", "wind_quiver_step"),
        ("plot", "draw_coastlines"),
        ("output", "directory"),
    ]
    missing = []
    for path in required_paths:
        current = configuration
        for key in path:
            if not isinstance(current, dict) or key not in current:
                missing.append(".".join(path))
                break
            current = current[key]
    if missing:
        raise RuntimeError(f"Faltan parámetros en el diagnóstico DANA: {', '.join(missing)}")

    return configuration


def select_indexes(values: np.ndarray, requested_values: list[float], coordinate_name: str) -> list[int]:
    """Ubica valores solicitados que deben existir exactamente en la coordenada nativa."""

    indexes = []
    for requested_value in requested_values:
        matches = np.flatnonzero(np.isclose(values, requested_value))
        if matches.size != 1:
            raise RuntimeError(
                f"El NetCDF no contiene el {coordinate_name} solicitado: {requested_value}. "
                f"Disponibles: {', '.join(str(value) for value in values)}"
            )
        indexes.append(int(matches[0]))
    return indexes


def read_pv_diagnostic(configuration: dict) -> tuple[dict[int, dict], list[dict]]:
    """Calcula PV baroclínica y reúne el contexto de altura y viento para cada plazo."""

    source = configuration["source"]
    analysis = configuration["analysis"]
    domain = configuration["domain"]
    netcdf_file = PROJECT_ROOT / source["standardized_netcdf"]
    if not netcdf_file.exists():
        raise RuntimeError(f"No existe el NetCDF estandarizado para el diagnóstico: {netcdf_file}")

    requested_levels = sorted(
        set(analysis["overview_pressure_levels_hpa"] + analysis["vertical_pressure_levels_hpa"])
    )
    statistics = []
    diagnostic = {}
    with Dataset(netcdf_file) as dataset:
        required_variables = [
            source["air_temperature"],
            source["wind_u"],
            source["wind_v"],
            source["geopotential_height"],
            "lev",
            "latitude",
            "longitude",
            "time",
        ]
        unavailable = [name for name in required_variables if name not in dataset.variables]
        if unavailable:
            raise RuntimeError(f"El NetCDF no contiene las variables requeridas: {', '.join(unavailable)}")

        pressure_levels = np.asarray(dataset.variables["lev"][:], dtype=float)
        latitude = np.asarray(dataset.variables["latitude"][:], dtype=float)
        longitude = np.asarray(dataset.variables["longitude"][:], dtype=float)
        time_coordinate = dataset.variables["time"]
        time_values = np.asarray(time_coordinate[:], dtype=float)
        valid_times = num2date(
            time_values,
            time_coordinate.units,
            only_use_cftime_datetimes=False,
            only_use_python_datetimes=True,
        )
        forecast_hours = time_values - time_values[0]

        all_levels = requested_levels + [
            analysis["wind_pressure_level_hpa"],
            analysis["geopotential_pressure_level_hpa"],
        ]
        select_indexes(pressure_levels, all_levels, "nivel de presión (hPa)")
        forecast_indexes = select_indexes(forecast_hours, analysis["forecast_hours"], "plazo (h)")

        stride = int(analysis["horizontal_stride"])
        if stride < 1:
            raise RuntimeError("analysis.horizontal_stride debe ser un entero positivo.")
        latitude = latitude[::stride]
        longitude = longitude[::stride]
        display_longitude = np.where(longitude > 180.0, longitude - 360.0, longitude)
        latitude_selection = (latitude >= domain["south"]) & (latitude <= domain["north"])
        longitude_selection = (display_longitude >= domain["west"]) & (display_longitude <= domain["east"])
        if not latitude_selection.any() or not longitude_selection.any():
            raise RuntimeError("El dominio DANA no contiene puntos de la malla nativa del NetCDF.")

        dx, dy = mpcalc.lat_lon_grid_deltas(
            units.Quantity(longitude, "degree"), units.Quantity(latitude, "degree")
        )
        pressure = units.Quantity(pressure_levels[:, np.newaxis, np.newaxis], "hPa")
        selected_level_indexes = select_indexes(pressure_levels, requested_levels, "nivel de presión (hPa)")
        wind_level_index = select_indexes(
            pressure_levels, [analysis["wind_pressure_level_hpa"]], "nivel de viento (hPa)"
        )[0]
        height_level_index = select_indexes(
            pressure_levels,
            [analysis["geopotential_pressure_level_hpa"]],
            "nivel de geopotencial (hPa)",
        )[0]

        for forecast_hour, time_index in zip(analysis["forecast_hours"], forecast_indexes, strict=True):
            temperature = units.Quantity(
                np.asarray(dataset.variables[source["air_temperature"]][time_index, :, ::stride, ::stride]),
                "kelvin",
            )
            wind_u = units.Quantity(
                np.asarray(dataset.variables[source["wind_u"]][time_index, :, ::stride, ::stride]),
                "m/s",
            )
            wind_v = units.Quantity(
                np.asarray(dataset.variables[source["wind_v"]][time_index, :, ::stride, ::stride]),
                "m/s",
            )
            theta = mpcalc.potential_temperature(pressure, temperature)
            pv = mpcalc.potential_vorticity_baroclinic(
                theta,
                pressure,
                wind_u,
                wind_v,
                dx=dx[np.newaxis, :, :],
                dy=dy[np.newaxis, :, :],
                latitude=units.Quantity(latitude[np.newaxis, :, np.newaxis], "degree"),
            )
            pv_pvu = np.asarray(pv.to("kelvin * meter**2 / kilogram / second").magnitude) * 1_000_000.0
            height = np.asarray(
                dataset.variables[source["geopotential_height"]][time_index, height_level_index, ::stride, ::stride]
            )

            fields = {
                "valid_time": valid_times[time_index],
                "longitude": display_longitude[longitude_selection],
                "latitude": latitude[latitude_selection],
                "pv": {
                    level: pv_pvu[level_index][np.ix_(latitude_selection, longitude_selection)]
                    for level, level_index in zip(requested_levels, selected_level_indexes, strict=True)
                },
                "height": height[np.ix_(latitude_selection, longitude_selection)],
                "wind_u": wind_u.magnitude[wind_level_index][np.ix_(latitude_selection, longitude_selection)],
                "wind_v": wind_v.magnitude[wind_level_index][np.ix_(latitude_selection, longitude_selection)],
            }
            diagnostic[int(forecast_hour)] = fields

            for level in requested_levels:
                values = fields["pv"][level]
                row = {
                    "forecast_hour": int(forecast_hour),
                    "valid_time_utc": fields["valid_time"].strftime("%Y-%m-%d %H:%M UTC"),
                    "pressure_hpa": level,
                    "minimum_pvu": f"{np.nanmin(values):.3f}",
                    "p05_pvu": f"{np.nanpercentile(values, 5):.3f}",
                    "median_pvu": f"{np.nanmedian(values):.3f}",
                    "p95_pvu": f"{np.nanpercentile(values, 95):.3f}",
                    "maximum_pvu": f"{np.nanmax(values):.3f}",
                }
                for threshold in analysis["pv_thresholds_pvu"]:
                    row[f"samples_pv_le_{threshold:g}"] = int(np.count_nonzero(values <= threshold))
                statistics.append(row)

    return diagnostic, statistics


def decorate_map(axis, configuration: dict) -> None:
    """Aplica el marco geográfico común sin cambiar la proyección del diagnóstico."""

    import cartopy.crs as ccrs

    domain = configuration["domain"]
    axis.set_extent([domain["west"], domain["east"], domain["south"], domain["north"]], crs=ccrs.PlateCarree())
    gridlines = axis.gridlines(draw_labels=True, linewidth=0.4, color="0.35", alpha=0.55, linestyle="--")
    gridlines.top_labels = False
    gridlines.right_labels = False
    if configuration["plot"]["draw_coastlines"]:
        axis.coastlines(resolution="110m", linewidth=0.5)


def add_pv_context(axis, fields: dict, level: float, configuration: dict):
    """Dibuja PV, altura geopotencial y viento para reconocer una intrusión cerrada."""

    import cartopy.crs as ccrs
    import matplotlib.colors as colors

    plot = configuration["plot"]
    transform = ccrs.PlateCarree()
    longitude, latitude = np.meshgrid(fields["longitude"], fields["latitude"])
    filled_levels = plot["pv_filled_levels_pvu"]
    image = axis.contourf(
        longitude,
        latitude,
        fields["pv"][level],
        levels=filled_levels,
        norm=colors.BoundaryNorm(filled_levels, ncolors=256, extend="both"),
        cmap="RdBu_r",
        extend="both",
        transform=transform,
    )
    threshold_lines = axis.contour(
        longitude,
        latitude,
        fields["pv"][level],
        levels=plot["pv_contours_pvu"],
        colors="black",
        linewidths=0.9,
        transform=transform,
    )
    height_interval = float(plot["geopotential_contour_interval_gpm"])
    height_minimum = np.floor(np.nanmin(fields["height"]) / height_interval) * height_interval
    height_maximum = np.ceil(np.nanmax(fields["height"]) / height_interval) * height_interval
    height_lines = axis.contour(
        longitude,
        latitude,
        fields["height"],
        levels=np.arange(height_minimum, height_maximum + height_interval, height_interval),
        colors="dimgray",
        linewidths=0.55,
        transform=transform,
    )
    axis.clabel(height_lines, levels=height_lines.levels[::2], fmt="%.0f", fontsize=5)
    wind_step = int(plot["wind_quiver_step"])
    axis.quiver(
        longitude[::wind_step, ::wind_step],
        latitude[::wind_step, ::wind_step],
        fields["wind_u"][::wind_step, ::wind_step],
        fields["wind_v"][::wind_step, ::wind_step],
        transform=transform,
        color="0.15",
        width=0.002,
        scale=800,
    )
    decorate_map(axis, configuration)
    axis.text(
        0.01,
        0.02,
        "PV: contornos −5 y −2 PVU",
        transform=axis.transAxes,
        fontsize=5.5,
        va="bottom",
        bbox={"facecolor": "white", "alpha": 0.68, "edgecolor": "none", "pad": 1.2},
    )
    return image


def plot_time_overviews(diagnostic: dict[int, dict], configuration: dict, output_directory: Path) -> list[Path]:
    """Genera una matriz temporal para cada nivel que revela la evolución de la anomalía."""

    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt

    output_files = []
    forecast_hours = configuration["analysis"]["forecast_hours"]
    columns = 3
    rows = int(np.ceil(len(forecast_hours) / columns))
    for level in configuration["analysis"]["overview_pressure_levels_hpa"]:
        figure, axes = plt.subplots(
            rows,
            columns,
            figsize=(14, 4.4 * rows),
            subplot_kw={"projection": ccrs.PlateCarree()},
            layout="constrained",
        )
        axes = np.asarray(axes).ravel()
        image = None
        for axis, forecast_hour in zip(axes, forecast_hours, strict=False):
            fields = diagnostic[int(forecast_hour)]
            image = add_pv_context(axis, fields, level, configuration)
            axis.set_title(f"f{forecast_hour:03d} — {fields['valid_time']:%d %b %H UTC}", fontsize=9)
        for axis in axes[len(forecast_hours) :]:
            axis.remove()
        colorbar = figure.colorbar(image, ax=axes[: len(forecast_hours)], shrink=0.76, pad=0.02)
        colorbar.set_label("PV (PVU); contornos grises: Z500 (gpm); flechas: viento 300 hPa")
        figure.suptitle(f"PV baroclínica a {level:g} hPa — diagnóstico DANA austral", fontsize=13)
        output_file = output_directory / f"pv_{level:g}hpa_all_times.png"
        figure.savefig(output_file, dpi=180)
        plt.close(figure)
        output_files.append(output_file)
    return output_files


def plot_vertical_panels(diagnostic: dict[int, dict], configuration: dict, output_directory: Path) -> list[Path]:
    """Compara niveles en plazos elegidos para confirmar el descenso vertical de la intrusión."""

    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt

    output_files = []
    levels = configuration["analysis"]["vertical_pressure_levels_hpa"]
    if len(levels) != 6:
        raise RuntimeError(
            "La figura vertical usa seis paneles; defina exactamente seis niveles en "
            "analysis.vertical_pressure_levels_hpa."
        )
    projection = ccrs.PlateCarree()
    for forecast_hour in configuration["analysis"]["vertical_panel_forecast_hours"]:
        fields = diagnostic[int(forecast_hour)]
        figure, axes = plt.subplots(
            2,
            3,
            figsize=(15, 8),
            subplot_kw={"projection": projection},
            layout="constrained",
        )
        image = None
        for axis, level in zip(axes.ravel(), levels, strict=True):
            image = add_pv_context(axis, fields, level, configuration)
            axis.set_title(f"PV a {level:g} hPa", fontsize=10)
        colorbar = figure.colorbar(image, ax=axes.ravel(), shrink=0.75, pad=0.02)
        colorbar.set_label("PV (PVU)")
        figure.suptitle(
            f"Estructura vertical de PV — f{forecast_hour:03d}, {fields['valid_time']:%Y-%m-%d %H UTC}",
            fontsize=13,
        )
        output_file = output_directory / f"pv_vertical_f{forecast_hour:03d}.png"
        figure.savefig(output_file, dpi=180)
        plt.close(figure)
        output_files.append(output_file)
    return output_files


def write_statistics(statistics: list[dict], output_directory: Path) -> Path:
    """Escribe valores de PV por plazo y nivel para fundamentar la selección de escena 3D."""

    output_file = output_directory / "pv_statistics.csv"
    with output_file.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(statistics[0]))
        writer.writeheader()
        writer.writerows(statistics)
    return output_file


def run_analysis(arguments: argparse.Namespace) -> list[Path]:
    """Ejecuta linealmente la lectura, cálculo de PV, figuras exploratorias y tabla final."""

    configuration = load_configuration(arguments.configuration)
    configured_directory = Path(configuration["output"]["directory"])
    output_directory = arguments.output_directory or configured_directory
    if not output_directory.is_absolute():
        output_directory = PROJECT_ROOT / output_directory
    output_directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output_directory / ".matplotlib"))

    # La PV se mantiene con signo: la anomalía ciclónica austral es negativa.
    diagnostic, statistics = read_pv_diagnostic(configuration)
    output_files = [write_statistics(statistics, output_directory)]
    output_files.extend(plot_time_overviews(diagnostic, configuration, output_directory))
    output_files.extend(plot_vertical_panels(diagnostic, configuration, output_directory))
    return output_files


if __name__ == "__main__":
    outputs = run_analysis(parse_arguments())
    print("Diagnóstico DANA completado:")
    for output in outputs:
        print(f"- {output}")
