"""Ubica valores ausentes de altura geopotencial sobre un mapa físico base.

Uso:
    conda run -n metvis3d python scripts/plot_hgtprs_missing_values.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml
from netCDF4 import Dataset, num2date


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_configuration(configuration_file: Path) -> dict:
    """Lee los parámetros que delimitan la revisión de altura geopotencial."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración de valores ausentes: {configuration_file}")
    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)

    required_paths = [
        ("source", "standardized_netcdf"),
        ("source", "geopotential_height"),
        ("domain", "west"),
        ("domain", "south"),
        ("domain", "east"),
        ("domain", "north"),
        ("output", "png"),
    ]
    missing_paths = []
    for path in required_paths:
        current = configuration
        for key in path:
            if not isinstance(current, dict) or key not in current:
                missing_paths.append(".".join(path))
                break
            current = current[key]
    if missing_paths:
        raise RuntimeError(f"Faltan parámetros para revisar hgtprs: {', '.join(missing_paths)}")
    return configuration


def find_missing_values(configuration: dict) -> tuple[list[dict], str]:
    """Localiza cada valor ausente sin modificar ni completar el NetCDF."""

    source = configuration["source"]
    netcdf_file = PROJECT_ROOT / source["standardized_netcdf"]
    if not netcdf_file.exists():
        raise RuntimeError(f"No existe el NetCDF estandarizado: {netcdf_file}")

    with Dataset(netcdf_file) as dataset:
        variable_name = source["geopotential_height"]
        required_variables = [variable_name, "time", "lev", "latitude", "longitude"]
        unavailable = [name for name in required_variables if name not in dataset.variables]
        if unavailable:
            raise RuntimeError(f"El NetCDF no contiene las variables requeridas: {', '.join(unavailable)}")

        height = dataset.variables[variable_name]
        latitude = np.asarray(dataset.variables["latitude"][:], dtype=np.float64)
        longitude = np.asarray(dataset.variables["longitude"][:], dtype=np.float64)
        pressure_hpa = np.asarray(dataset.variables["lev"][:], dtype=np.float64)
        time_coordinate = dataset.variables["time"]
        valid_times = num2date(
            time_coordinate[:],
            time_coordinate.units,
            only_use_cftime_datetimes=False,
        )

        missing_values = []
        for time_index, valid_time in enumerate(valid_times):
            for level_index, level_hpa in enumerate(pressure_hpa):
                values = np.ma.asarray(height[time_index, level_index])
                invalid = np.ma.getmaskarray(values) | ~np.isfinite(values.filled(np.nan))
                for latitude_index, longitude_index in np.argwhere(invalid):
                    missing_values.append(
                        {
                            "valid_time": valid_time,
                            "pressure_hpa": float(level_hpa),
                            "latitude": float(latitude[latitude_index]),
                            "longitude": float(longitude[longitude_index]),
                        }
                    )

        forecast_date = str(getattr(dataset, "forecast_date", netcdf_file.stem))
    return missing_values, forecast_date


def plot_missing_values(configuration: dict, missing_values: list[dict], forecast_date: str, output_file: Path) -> None:
    """Dibuja los puntos ausentes sobre el mapa físico integrado de Cartopy."""

    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt

    domain = configuration["domain"]
    figure, axis = plt.subplots(figsize=(13, 8), subplot_kw={"projection": ccrs.PlateCarree()}, layout="constrained")
    axis.set_extent([domain["west"], domain["east"], domain["south"], domain["north"]], crs=ccrs.PlateCarree())
    axis.stock_img()
    gridlines = axis.gridlines(draw_labels=True, linewidth=0.45, color="0.2", alpha=0.55, linestyle="--")
    gridlines.top_labels = False
    gridlines.right_labels = False

    visible_values = [
        value
        for value in missing_values
        if domain["west"] <= value["longitude"] <= domain["east"]
        and domain["south"] <= value["latitude"] <= domain["north"]
    ]
    if not visible_values:
        raise RuntimeError("No hay valores ausentes dentro del dominio declarado para el mapa.")

    axis.scatter(
        [value["longitude"] for value in visible_values],
        [value["latitude"] for value in visible_values],
        s=58,
        marker="x",
        linewidths=1.8,
        color="#d7191c",
        transform=ccrs.PlateCarree(),
        label="hgtprs ausente",
        zorder=4,
    )
    for value in visible_values:
        axis.annotate(
            f"{value['pressure_hpa']:g} hPa",
            (value["longitude"], value["latitude"]),
            xytext=(4, 5),
            textcoords="offset points",
            fontsize=7,
            color="black",
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 0.6},
        )

    valid_times = sorted({value["valid_time"].strftime("%Y-%m-%d %H:%M UTC") for value in visible_values})
    pressure_levels = sorted({value["pressure_hpa"] for value in visible_values})
    axis.legend(loc="lower left")
    axis.set_title(
        "Valores ausentes de altura geopotencial isobárica\n"
        f"Corrida {forecast_date} — plazos: {', '.join(valid_times)} — niveles: {', '.join(f'{level:g}' for level in pressure_levels)} hPa",
        fontsize=12,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_file, dpi=180)
    plt.close(figure)


def run_diagnostic(configuration_file: Path, output_file: Path | None) -> Path:
    """Ejecuta la lectura, revisión espacial y escritura del PNG solicitado."""

    configuration = load_configuration(configuration_file)
    missing_values, forecast_date = find_missing_values(configuration)
    if not missing_values:
        raise RuntimeError("La altura geopotencial no contiene valores ausentes en la corrida revisada.")
    destination = output_file or PROJECT_ROOT / configuration["output"]["png"]
    plot_missing_values(configuration, missing_values, forecast_date, destination)
    print(f"Valores ausentes encontrados: {len(missing_values)}")
    print(f"PNG de revisión: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grafica valores ausentes de hgtprs sobre un mapa físico base.")
    parser.add_argument(
        "--configuration",
        type=Path,
        default=PROJECT_ROOT / "config" / "analysis" / "hgtprs_missing_values.yaml",
        help="YAML de la revisión espacial.",
    )
    parser.add_argument("--output", type=Path, help="PNG que reemplaza output.png de la configuración.")
    arguments = parser.parse_args()
    run_diagnostic(arguments.configuration, arguments.output)
