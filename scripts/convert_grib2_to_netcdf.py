"""Convierte una corrida configurada de GRIB2 en un NetCDF estandarizado.

Uso:
    python scripts/convert_grib2_to_netcdf.py \
        --model gfs --date 20260816 --cycle-hour 00 --forecast-hours 120 \
        --area -130 -56 -10 30
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from standardize.grib2_to_netcdf import Grib2ToNetCDF


def parse_arguments() -> argparse.Namespace:
    """Define una corrida configurada y su horizonte de pronóstico."""

    parser = argparse.ArgumentParser(description="Convierte una corrida GRIB2 homogénea a NetCDF.")
    parser.add_argument("--model", required=True, help="Modelo configurado: gfs o ifs.")
    parser.add_argument(
        "--date",
        "--dia",
        dest="forecast_date",
        required=True,
        help="Fecha de inicialización en formato YYYYMMDD.",
    )
    parser.add_argument(
        "--cycle-hour",
        "--hh",
        dest="cycle_hour",
        required=True,
        help="Hora de inicialización UTC en formato HH.",
    )
    parser.add_argument(
        "--forecast-hours",
        "--horas",
        dest="forecast_hours",
        type=int,
        required=True,
        help="Plazo máximo inclusivo que integrará el NetCDF.",
    )
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


def read_model_configuration(model_name: str) -> dict:
    """Lee la configuración versionada de un modelo operativo."""

    configuration_file = PROJECT_ROOT / "config" / "models" / f"{model_name.lower()}.yaml"

    if not configuration_file.exists():
        raise RuntimeError(f"No existe una configuración operativa para el modelo '{model_name}': {configuration_file}")
    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)
    if not isinstance(configuration, dict):
        raise RuntimeError(f"La configuración del modelo debe ser un mapa YAML: {configuration_file}")

    try:
        model = configuration["model"]["id"]
        center = configuration["model"]["center"]
        source = configuration["source"]
        directory_template = source["directory_template"]
        file_template = source["file_template"]
        forecast_schedule = source["forecast_schedule"]
        longitude_convention = configuration["standardization"]["longitude_range"]
        variables = configuration["selected_variables"]
    except KeyError as error:
        raise RuntimeError(
            f"Falta '{error.args[0]}' en la configuración del modelo: {configuration_file}"
        ) from error
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError(f"model.id debe ser texto en la configuración: {configuration_file}")
    if not isinstance(center, str) or not center.strip():
        raise RuntimeError(f"model.center debe ser texto en la configuración: {configuration_file}")
    if not isinstance(directory_template, str) or not directory_template.strip():
        raise RuntimeError(f"source.directory_template debe ser texto en la configuración: {configuration_file}")
    if not isinstance(file_template, str) or not file_template.strip():
        raise RuntimeError(f"source.file_template debe ser texto en la configuración: {configuration_file}")
    if not isinstance(forecast_schedule, list) or not forecast_schedule:
        raise RuntimeError(f"source.forecast_schedule debe ser una lista no vacía en: {configuration_file}")
    if not isinstance(longitude_convention, str):
        raise RuntimeError(f"standardization.longitude_range debe ser texto en: {configuration_file}")
    if not isinstance(variables, list) or not all(isinstance(variable, str) for variable in variables):
        raise RuntimeError(f"selected_variables debe ser una lista de nombres en: {configuration_file}")
    return {
        "model": model,
        "center": center,
        "directory_template": directory_template,
        "file_template": file_template,
        "forecast_schedule": forecast_schedule,
        "longitude_convention": longitude_convention,
        "variables": variables,
    }


def validate_run_arguments(arguments: argparse.Namespace) -> None:
    """Valida la fecha, ciclo y horizonte declarados para la corrida."""

    if len(arguments.forecast_date) != 8 or not arguments.forecast_date.isdigit():
        raise RuntimeError("--date debe usar ocho dígitos con el formato YYYYMMDD.")
    try:
        datetime.strptime(arguments.forecast_date, "%Y%m%d")
    except ValueError as error:
        raise RuntimeError(f"--date no contiene una fecha válida: {arguments.forecast_date}.") from error
    if len(arguments.cycle_hour) != 2 or not arguments.cycle_hour.isdigit() or not 0 <= int(arguments.cycle_hour) <= 23:
        raise RuntimeError("--cycle-hour debe usar dos dígitos entre 00 y 23.")
    if arguments.forecast_hours <= 0:
        raise RuntimeError("--forecast-hours debe ser un plazo positivo en horas.")


def build_forecast_hours(forecast_schedule: list[object], maximum_hour: int, model: str) -> list[int]:
    """Construye los plazos esperados de acuerdo con el calendario del modelo."""

    forecast_hours: list[int] = []
    for segment in forecast_schedule:
        if not isinstance(segment, dict):
            raise RuntimeError(f"El calendario de pronóstico de {model} debe contener mapas YAML.")
        try:
            first_hour = int(segment["first_hour"])
            last_hour = int(segment["last_hour"])
            step_hours = int(segment["step_hours"])
        except KeyError as error:
            raise RuntimeError(f"Falta '{error.args[0]}' en el calendario de pronóstico de {model}.") from error
        if first_hour < 0 or last_hour < first_hour or step_hours <= 0:
            raise RuntimeError(f"El calendario de pronóstico de {model} contiene un intervalo inválido.")
        forecast_hours.extend(range(first_hour, min(last_hour, maximum_hour) + 1, step_hours))

    forecast_hours = sorted(set(forecast_hours))
    if maximum_hour not in forecast_hours:
        raise RuntimeError(
            f"El plazo {maximum_hour:03d} h no está disponible en el calendario de {model}."
        )
    return forecast_hours


def resolve_grib_files(arguments: argparse.Namespace, model_configuration: dict) -> list[Path]:
    """Localiza todos los GRIB2 previstos para una corrida configurada."""

    forecast_hours = build_forecast_hours(
        model_configuration["forecast_schedule"],
        arguments.forecast_hours,
        model_configuration["model"],
    )
    try:
        directory_name = model_configuration["directory_template"].format(
            date=arguments.forecast_date,
            cycle_hour=arguments.cycle_hour,
        )
    except KeyError as error:
        raise RuntimeError(f"La ruta de {model_configuration['model']} usa el marcador desconocido '{error.args[0]}'.") from error
    source_directory = PROJECT_ROOT / directory_name
    if not source_directory.is_dir():
        raise RuntimeError(f"No existe el directorio de la corrida {model_configuration['model']}: {source_directory}")

    grib_files = []
    missing_files = []
    for forecast_hour in forecast_hours:
        try:
            filename = model_configuration["file_template"].format(
                date=arguments.forecast_date,
                cycle_hour=arguments.cycle_hour,
                forecast_hour=forecast_hour,
            )
        except KeyError as error:
            raise RuntimeError(
                f"El patrón de archivos de {model_configuration['model']} usa el marcador desconocido '{error.args[0]}'."
            ) from error
        grib_file = source_directory / filename
        if grib_file.is_file():
            grib_files.append(grib_file)
        else:
            missing_files.append(grib_file.name)

    if missing_files:
        raise RuntimeError(
            f"Faltan GRIB2 de {model_configuration['model']} para la corrida "
            f"{arguments.forecast_date}{arguments.cycle_hour}: {', '.join(missing_files)}."
        )
    if len(grib_files) < 3:
        raise RuntimeError(
            f"La corrida {model_configuration['model']} hasta {arguments.forecast_hours:03d} h "
            "contiene menos de tres GRIB2."
        )
    return grib_files


def run_conversion(arguments: argparse.Namespace) -> Path:
    """Muestra linealmente la lectura, validación y escritura de una corrida."""

    # Leer las configuraciones versionadas del modelo y los remapeos GRIB2.
    validate_run_arguments(arguments)
    model_configuration = read_model_configuration(arguments.model)
    if not arguments.definitions_configuration.exists():
        raise RuntimeError(f"No existe la configuración GRIB2: {arguments.definitions_configuration}")

    # Revisar los GRIB2 esperados para la única corrida solicitada.
    grib_files = resolve_grib_files(arguments, model_configuration)

    # Convertir las variables y coordenadas declaradas, sin interpolar la grilla.
    converter = Grib2ToNetCDF(
        grib_files,
        model=model_configuration["model"],
        center=model_configuration["center"],
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
