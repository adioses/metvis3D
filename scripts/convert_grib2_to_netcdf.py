"""Convierte una corrida GRIB2 homogénea en un NetCDF estandarizado.

Uso:
    python scripts/convert_grib2_to_netcdf.py "data/raw/GFS/*.grib2" \
        --model-configuration config/models/gfs.yaml \
        --center ncep --area -130 -56 -10 30
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from standardize.grib2_to_netcdf import Grib2ToNetCDF


def parse_arguments() -> argparse.Namespace:
    """Define los insumos de una conversión completa y reproducible."""

    parser = argparse.ArgumentParser(description="Convierte una corrida GRIB2 homogénea a NetCDF.")
    parser.add_argument("grib_patterns", nargs="+", help="Rutas o patrones de los GRIB2 de una sola corrida.")
    parser.add_argument(
        "--model-configuration",
        type=Path,
        required=True,
        help="YAML del modelo con selección de variables y convención longitudinal.",
    )
    parser.add_argument("--center", required=True, help="Centro productor usado por los remapeos GRIB2.")
    parser.add_argument(
        "--definitions-configuration",
        type=Path,
        default=PROJECT_ROOT / "config" / "grib2-definitions.yaml",
        help="YAML con definiciones y remapeos GRIB2.",
    )
    parser.add_argument(
        "--area",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Recorte geográfico en -180..180; omítalo para conservar el dominio completo.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=PROJECT_ROOT / "data" / "standardized",
        help="Directorio donde se escribirá el NetCDF final.",
    )
    return parser.parse_args()


def read_model_configuration(configuration_file: Path) -> dict:
    """Lee modelo, convención longitudinal y variables finales del YAML."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración del modelo: {configuration_file}")
    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)
    if not isinstance(configuration, dict):
        raise RuntimeError(f"La configuración del modelo debe ser un mapa YAML: {configuration_file}")

    try:
        model = configuration["model"]["id"]
        longitude_convention = configuration["standardization"]["longitude_range"]
        variables = configuration["selected_variables"]
    except KeyError as error:
        raise RuntimeError(
            f"Falta '{error.args[0]}' en la configuración del modelo: {configuration_file}"
        ) from error
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError(f"model.id debe ser texto en la configuración: {configuration_file}")
    if not isinstance(longitude_convention, str):
        raise RuntimeError(f"standardization.longitude_range debe ser texto en: {configuration_file}")
    if not isinstance(variables, list) or not all(isinstance(variable, str) for variable in variables):
        raise RuntimeError(f"selected_variables debe ser una lista de nombres en: {configuration_file}")
    return {
        "model": model,
        "longitude_convention": longitude_convention,
        "variables": variables,
    }


def run_conversion(arguments: argparse.Namespace) -> Path:
    """Muestra linealmente la lectura, validación y escritura de una corrida."""

    # Leer las configuraciones versionadas del modelo y los remapeos GRIB2.
    model_configuration = read_model_configuration(arguments.model_configuration)
    if not arguments.definitions_configuration.exists():
        raise RuntimeError(f"No existe la configuración GRIB2: {arguments.definitions_configuration}")

    # Revisar los GRIB2 que integran la única corrida a convertir.
    grib_files = sorted(
        {Path(grib_file) for pattern in arguments.grib_patterns for grib_file in glob.glob(pattern)}
    )
    if not grib_files:
        raise RuntimeError("No se encontraron GRIB2 con los patrones indicados.")
    if len(grib_files) < 3:
        raise RuntimeError("La corrida requiere al menos tres GRIB2 con tiempos válidos distintos.")

    # Convertir las variables y coordenadas declaradas, sin interpolar la grilla.
    converter = Grib2ToNetCDF(
        grib_files,
        model=model_configuration["model"],
        center=arguments.center,
        configuration_yml=arguments.definitions_configuration,
        area=tuple(arguments.area) if arguments.area is not None else None,
        longitude_convention=model_configuration["longitude_convention"],
        variables=model_configuration["variables"],
    )
    print(f"Convirtiendo {len(grib_files)} GRIB2 de {model_configuration['model']}...", flush=True)
    netcdf_output = converter.run_conversion(arguments.output_directory)

    # Informar el único producto NetCDF final de la corrida.
    print(f"NetCDF generado: {netcdf_output}")
    return netcdf_output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_conversion(parse_arguments())
