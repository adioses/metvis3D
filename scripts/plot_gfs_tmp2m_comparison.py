"""Compara TMP a 2 m del GRIB completo y de su NetCDF recortado."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pygrib
from netCDF4 import Dataset
from matplotlib.patches import Rectangle


matplotlib.use("Agg")
import matplotlib.pyplot as plt


AREA = (-130.0, -57.0, -10.0, 30.0)


def parse_arguments() -> argparse.Namespace:
    """Obtiene las rutas de los dos formatos que se compararán."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grib_file", type=Path)
    parser.add_argument("netcdf_file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Nombre del modelo para los títulos.")
    return parser.parse_args()


def read_tmp2m(grib_file: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Lee TMP a 2 m sobre la extensión completa y ordena su longitud."""

    with pygrib.open(str(grib_file)) as source_grib:
        for grib_message in source_grib:
            if grib_message.shortName == "2t":
                values = grib_message.values
                latitude, longitude = grib_message.latlons()
                break
        else:
            raise RuntimeError(f"No se encontró TMP a 2 m en {grib_file.name}.")

    latitude = latitude[:, 0]
    longitude = np.mod(longitude[0, :], 360)
    longitude_indices = np.argsort(longitude)
    return values[:, longitude_indices], latitude, longitude[longitude_indices]


def select_output_area(
    values: np.ndarray, latitude: np.ndarray, longitude: np.ndarray
) -> np.ndarray:
    """Selecciona los valores que deben coincidir con el NetCDF final."""

    west, south, east, north = AREA
    latitude_indices = np.flatnonzero((latitude >= south) & (latitude <= north))
    longitude_indices = np.flatnonzero(
        (longitude >= west % 360) & (longitude <= east % 360)
    )
    return values[np.ix_(latitude_indices, longitude_indices)]


def main() -> None:
    """Genera una figura de comparación con escala térmica compartida."""

    arguments = parse_arguments()
    grib_values, latitude, longitude = read_tmp2m(arguments.grib_file)
    grib_subset = select_output_area(grib_values, latitude, longitude)
    with Dataset(arguments.netcdf_file) as dataset:
        netcdf_values = dataset.variables["tmp2m"][0, :, :]
        netcdf_latitude = dataset.variables["latitude"][:]
        netcdf_longitude = dataset.variables["longitude"][:]

    if grib_subset.shape != netcdf_values.shape:
        raise RuntimeError("TMP a 2 m tiene dimensiones diferentes entre GRIB y NetCDF.")

    value_minimum = min(grib_values.min(), netcdf_values.min())
    value_maximum = max(grib_values.max(), netcdf_values.max())
    figure, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    source_image = axes[0].pcolormesh(
        longitude,
        latitude,
        grib_values,
        shading="auto",
        vmin=value_minimum,
        vmax=value_maximum,
        cmap="turbo",
    )
    west, south, east, north = AREA
    axes[0].add_patch(
        Rectangle(
            (west % 360, south),
            east % 360 - west % 360,
            north - south,
            fill=False,
            linewidth=1.5,
            edgecolor="white",
        )
    )
    axes[0].set_title(f"{arguments.model} — GRIB original completo")
    output_image = axes[1].pcolormesh(
        netcdf_longitude,
        netcdf_latitude,
        netcdf_values,
        shading="auto",
        vmin=value_minimum,
        vmax=value_maximum,
        cmap="turbo",
    )
    axes[1].set_title(f"{arguments.model} — NetCDF convertido")
    for axis in axes:
        axis.set_xlabel("Longitud (°E)")
        axis.set_ylabel("Latitud (°N)")
    figure.colorbar(output_image, ax=axes, label="Temperatura (K)")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output, dpi=160)
    plt.close(figure)

    difference = np.asarray(netcdf_values) - grib_subset
    print(f"Diferencia máxima absoluta: {np.abs(difference).max():.6f} K")
    print(f"Figura: {arguments.output}")


if __name__ == "__main__":
    main()
