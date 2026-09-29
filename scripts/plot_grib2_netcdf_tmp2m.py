"""Compara visualmente TMP a 2 m del GRIB original y un NetCDF convertido.

Uso:
    python scripts/plot_grib2_netcdf_tmp2m.py \
        --grib "data/raw/ECMWF/*.grib2" \
        --netcdf data/standardized/ecmwf-ifs_20260903_00Z.nc \
        --valid-time 2026090300 \
        --output outputs/grib2-analysis/ecmwf-tmp2m.png
"""

import argparse
import glob
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
import pygrib
from matplotlib.patches import Rectangle
from netCDF4 import Dataset, num2date


matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_arguments() -> argparse.Namespace:
    """Obtiene los archivos y el tiempo válido que se representará."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grib", action="append", required=True, help="Ruta o patrón GRIB2; se puede repetir.")
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF ya convertido.")
    parser.add_argument("--output", type=Path, required=True, help="Figura PNG de salida.")
    parser.add_argument(
        "--valid-time",
        type=lambda value: datetime.strptime(value, "%Y%m%d%H"),
        help="Tiempo válido YYYYmmddHH; sin este argumento se usa el primer archivo.",
    )
    return parser.parse_args()


def resolve_grib_files(grib_patterns: list[str]) -> list[Path]:
    """Expande y ordena las rutas GRIB indicadas para la comparación visual."""

    grib_files = sorted(
        Path(grib_file)
        for grib_pattern in grib_patterns
        for grib_file in glob.glob(grib_pattern)
    )
    if not grib_files:
        raise RuntimeError("No se encontraron archivos GRIB2 para la comparación.")
    return grib_files


def read_tmp2m(grib_files: list[Path], requested_time: datetime | None):
    """Lee TMP a 2 m del primer GRIB o del tiempo válido solicitado."""

    for grib_file in grib_files:
        with pygrib.open(str(grib_file)) as source_grib:
            for grib_message in source_grib:
                if grib_message.shortName != "2t":
                    continue
                if requested_time is not None and grib_message.validDate != requested_time:
                    continue
                values = grib_message.values
                latitude, longitude = grib_message.latlons()
                return grib_file, grib_message.validDate, values, latitude[:, 0], longitude[0, :]
    if requested_time is None:
        raise RuntimeError("No se encontró TMP a 2 m en los archivos GRIB2.")
    raise RuntimeError(f"No se encontró TMP a 2 m para el tiempo válido {requested_time:%Y%m%d%H}.")


def netcdf_longitudes_in_source_convention(
    netcdf_longitude: np.ndarray, source_longitude: np.ndarray
) -> np.ndarray:
    """Convierte sólo el contorno NetCDF a la convención nativa del GRIB."""

    if np.any(source_longitude < 0):
        return (netcdf_longitude + 180) % 360 - 180
    return np.mod(netcdf_longitude, 360)


def read_netcdf_tmp2m(netcdf_file: Path, valid_time: datetime):
    """Lee TMP a 2 m y sus coordenadas en el mismo tiempo válido del GRIB."""

    with Dataset(netcdf_file) as dataset:
        time_coordinate = dataset.variables["time"]
        netcdf_times = num2date(
            time_coordinate[:],
            time_coordinate.units,
            only_use_cftime_datetimes=False,
            only_use_python_datetimes=True,
        )
        time_index = next(
            (
                index
                for index, netcdf_time in enumerate(netcdf_times)
                if netcdf_time == valid_time
            ),
            None,
        )
        if time_index is None:
            raise RuntimeError(f"El NetCDF no contiene el tiempo válido {valid_time:%Y%m%d%H}.")
        if "tmp2m" not in dataset.variables:
            raise RuntimeError("El NetCDF no contiene la variable tmp2m.")
        values = dataset.variables["tmp2m"][time_index, :, :]
        latitude = dataset.variables["latitude"][:]
        longitude = dataset.variables["longitude"][:]
        model = dataset.model
        units = getattr(dataset.variables["tmp2m"], "units", "")
    return values, latitude, longitude, model, units


def main() -> None:
    """Genera una figura comparativa sin calcular diferencias numéricas."""

    arguments = parse_arguments()
    grib_files = resolve_grib_files(arguments.grib)
    grib_file, valid_time, grib_values, grib_latitude, grib_longitude = read_tmp2m(
        grib_files, arguments.valid_time
    )
    netcdf_values, netcdf_latitude, netcdf_longitude, model, units = read_netcdf_tmp2m(
        arguments.netcdf, valid_time
    )

    # El GRIB se representa con sus coordenadas y columnas en el orden nativo.
    source_area_longitude = netcdf_longitudes_in_source_convention(
        netcdf_longitude, grib_longitude
    )

    value_minimum = min(float(np.ma.min(grib_values)), float(np.ma.min(netcdf_values)))
    value_maximum = max(float(np.ma.max(grib_values)), float(np.ma.max(netcdf_values)))
    figure, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    source_image = axes[0].pcolormesh(
        grib_longitude,
        grib_latitude,
        grib_values,
        shading="auto",
        vmin=value_minimum,
        vmax=value_maximum,
        cmap="turbo",
    )
    axes[0].add_patch(
        Rectangle(
            (float(source_area_longitude.min()), float(netcdf_latitude.min())),
            float(source_area_longitude.max() - source_area_longitude.min()),
            float(netcdf_latitude.max() - netcdf_latitude.min()),
            fill=False,
            linewidth=1.5,
            edgecolor="white",
        )
    )
    axes[0].set_title(f"{model} — GRIB original completo")
    output_image = axes[1].pcolormesh(
        netcdf_longitude,
        netcdf_latitude,
        netcdf_values,
        shading="auto",
        vmin=value_minimum,
        vmax=value_maximum,
        cmap="turbo",
    )
    axes[1].set_title(f"{model} — NetCDF convertido")
    for axis in axes:
        axis.set_xlabel("Longitud")
        axis.set_ylabel("Latitud")
    figure.colorbar(output_image, ax=axes, label=f"TMP a 2 m ({units})")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output, dpi=160)
    plt.close(figure)
    print(f"GRIB usado: {grib_file}")
    print(f"Tiempo válido: {valid_time.isoformat()}")
    print(f"Figura: {arguments.output}")


if __name__ == "__main__":
    main()
