"""Mide la conversión GRIB2 a NetCDF para una corrida meteorológica.

Registra tres etapas del conversor: validación de dominio y tiempos,
preparación de variables NetCDF y escritura por archivo GRIB. El tiempo total
se mide de forma independiente alrededor de toda la conversión.

Uso:
    python scripts/benchmark_grib2_to_netcdf.py \
        --input-dir data/raw/GFS27 \
        --input-pattern "gfs*.f[0-9][0-9][0-9]" \
        --model gfs --center ncep \
        --configuration-yml config/grib2-definitions.yaml \
        --variables-yml config/models/gfs.yaml \
        --area -130 -57 -10 30 \
        --file-count 3 \
        --output-dir data/standardized/benchmark
"""

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from standardize.grib2_to_netcdf import Grib2ToNetCDF


class TimedGrib2ToNetCDF(Grib2ToNetCDF):
    """Cronometra etapas del conversor sin alterar su lógica científica."""

    def __init__(self, *args, benchmark_log: Path, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.benchmark_log = benchmark_log
        self.file_positions: dict[str, int] = {}
        self.validation_seconds = 0.0
        self.netcdf_variables_seconds = 0.0
        self.write_seconds = 0.0
        self._writing_messages = False
        self._current_grib_file: Path | None = None
        self._current_file_started_at: float | None = None
        self._current_message_count = 0

    def _write_log(self, message: str) -> None:
        """Muestra y conserva una línea del benchmark."""

        print(message, flush=True)
        with self.benchmark_log.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{message}\n")

    def _log_progress(self, grib_file: Path, started_at: float, message_count: int) -> None:
        """Registra duración, acumulado, promedio y ETA de la escritura por archivo."""

        elapsed_seconds = time.perf_counter() - started_at
        self.write_seconds += elapsed_seconds
        file_position = self.file_positions[str(grib_file)]
        average_seconds = self.write_seconds / file_position
        remaining_seconds = average_seconds * (len(self.grib_files) - file_position)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"[{timestamp}] {'WRITE':<9} {file_position:>3}/{len(self.grib_files):<3}  "
            f"{grib_file.name}  {elapsed_seconds / 60:.2f} min  "
            f"accumulated: {self.write_seconds / 60:.2f} min  "
            f"average: {average_seconds / 60:.2f} min/file  "
            f"ETA: {remaining_seconds / 60:.2f} min  messages: {message_count}"
        )
        self._write_log(message)

    def _finish_current_file(self) -> None:
        """Cierra la medición de escritura del archivo GRIB activo."""

        if self._current_grib_file is None or self._current_file_started_at is None:
            return
        self._log_progress(
            self._current_grib_file,
            self._current_file_started_at,
            self._current_message_count,
        )
        self._current_grib_file = None
        self._current_file_started_at = None
        self._current_message_count = 0

    def _validate_domain_times(self) -> None:
        """Mide la validación de metadatos comunes de la corrida."""

        started_at = time.perf_counter()
        try:
            super()._validate_domain_times()
        finally:
            self.validation_seconds = time.perf_counter() - started_at
        self.file_positions = {
            str(grib_file): position
            for position, grib_file in enumerate(self.grib_files, start=1)
        }

    def _build_netcdf_variables(self):
        """Mide el agrupamiento, remapeo y selección de variables NetCDF."""

        started_at = time.perf_counter()
        try:
            return super()._build_netcdf_variables()
        finally:
            self.netcdf_variables_seconds = time.perf_counter() - started_at

    def _run_wgrib2_command(self, grib_file: Path, args: list[str]) -> str:
        """Delimita cada archivo durante la etapa de escritura sin duplicar su bucle."""

        if self._writing_messages:
            self._finish_current_file()
            self._current_grib_file = grib_file
            self._current_file_started_at = time.perf_counter()

        output = super()._run_wgrib2_command(grib_file, args)
        if self._writing_messages:
            self._current_message_count = len(output.splitlines())
        return output

    def _write_grib_messages(self, dataset) -> None:
        """Mide cada archivo escrito por el método original del conversor."""

        self._writing_messages = True
        try:
            super()._write_grib_messages(dataset)
        finally:
            self._finish_current_file()
            self._writing_messages = False


def parse_arguments() -> argparse.Namespace:
    """Obtiene los parámetros de una corrida de benchmark reproducible."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/GFS27"),
        help="Directorio con los GRIB de la corrida.",
    )
    parser.add_argument(
        "--input-pattern",
        default="gfs*.f[0-9][0-9][0-9]",
        help="Patrón de archivos GRIB dentro del directorio de entrada.",
    )
    parser.add_argument("--model", default="gfs", help="Identificador del modelo meteorológico.")
    parser.add_argument("--center", default="ncep", help="Centro productor de los GRIB.")
    parser.add_argument(
        "--configuration-yml",
        type=Path,
        default=Path("config/grib2-definitions.yaml"),
        help="Configuración de definiciones y remapeos GRIB2.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/standardized/benchmark"),
        help="Directorio del resultado del benchmark.",
    )
    parser.add_argument(
        "--file-count",
        type=int,
        help="Cantidad inicial de archivos para una muestra controlada.",
    )
    parser.add_argument(
        "--variables-yml",
        type=Path,
        help="YAML con la lista selected_variables para el NetCDF.",
    )
    parser.add_argument(
        "--area",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=(-130.0, -57.0, -10.0, 30.0),
        help="Área de recorte west south east north; por defecto: -130 -57 -10 30.",
    )
    return parser.parse_args()


def read_selected_variables(variables_yml: Path | None) -> list[str] | None:
    """Lee la selección opcional de variables finales del modelo."""

    if variables_yml is None:
        return None
    with variables_yml.open(encoding="utf-8") as configuration_file:
        return yaml.safe_load(configuration_file)["selected_variables"]


def main() -> None:
    """Ejecuta el benchmark conservando el flujo completo del conversor."""

    arguments = parse_arguments()
    grib_files = sorted(arguments.input_dir.glob(arguments.input_pattern))
    if arguments.file_count is not None:
        grib_files = grib_files[:arguments.file_count]
    if not grib_files:
        raise RuntimeError("No se encontraron archivos GRIB para el benchmark.")

    variables = read_selected_variables(arguments.variables_yml)
    area = tuple(arguments.area)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_log = arguments.output_dir / f"{arguments.center.lower()}-{arguments.model.lower()}_benchmark.log"
    if benchmark_log.exists():
        raise RuntimeError(f"Ya existe el log de benchmark {benchmark_log.name}.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with benchmark_log.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Inicio UTC: {datetime.now(timezone.utc).isoformat()}\n")
        log_file.write(f"Archivos: {len(grib_files)}\n")
        log_file.write(f"Área: {area}\n")
        log_file.write("Convención longitudinal: 0_360\n")
        log_file.write(f"Configuración GRIB2: {arguments.configuration_yml}\n")
        log_file.write(f"Variables: {'todas' if variables is None else ', '.join(variables)}\n")
        log_file.write("Cuantización: least_significant_digit=2\n")

    converter = TimedGrib2ToNetCDF(
        grib_files,
        model=arguments.model,
        center=arguments.center,
        configuration_yml=arguments.configuration_yml,
        area=area,
        longitude_convention="0_360",
        variables=variables,
        benchmark_log=benchmark_log,
    )
    started_at = time.perf_counter()
    netcdf_output = converter.run_conversion(arguments.output_dir)
    total_seconds = time.perf_counter() - started_at

    summary = (
        f"Tiempo total: {total_seconds / 60:.2f} min\n"
        f"Validación de dominio y tiempos: {converter.validation_seconds:.2f} seg\n"
        f"Preparación de variables NetCDF: {converter.netcdf_variables_seconds:.2f} seg\n"
        f"Escritura por archivos GRIB: {converter.write_seconds / 60:.2f} min\n"
        f"NetCDF: {netcdf_output.name}\n"
        f"Tamaño NetCDF: {netcdf_output.stat().st_size / 1024 ** 2:.2f} MiB"
    )
    converter._write_log(summary)


if __name__ == "__main__":
    main()
