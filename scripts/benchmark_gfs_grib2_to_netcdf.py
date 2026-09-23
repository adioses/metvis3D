"""Mide la conversión GRIB2 a NetCDF para una corrida meteorológica."""

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pygrib

from standardize.grib2_to_netcdf import Grib2ToNetCDF


class TimedGrib2ToNetCDF(Grib2ToNetCDF):
    """Registra los tiempos por archivo sin alterar el flujo del conversor."""

    def __init__(self, *args, benchmark_log: Path, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.benchmark_log = benchmark_log
        self.file_positions = {
            str(grib_file): position
            for position, grib_file in enumerate(self.grib_files, start=1)
        }
        self.inventory_accumulated_seconds = 0.0
        self.conversion_accumulated_seconds = 0.0

    def _log_progress(
        self,
        stage: str,
        grib_file: Path,
        started_at: float,
        accumulated_seconds: float,
        message_count: int,
    ) -> None:
        """Registra avance, duración acumulada, promedio y tiempo estimado."""

        elapsed_seconds = time.perf_counter() - started_at
        file_position = self.file_positions[str(grib_file)]
        average_seconds = accumulated_seconds / file_position
        remaining_seconds = average_seconds * (len(self.grib_files) - file_position)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"[{timestamp}] {stage:<9} {file_position:>3}/{len(self.grib_files):<3}  "
            f"{grib_file.name}  {elapsed_seconds / 60:.2f} min  "
            f"accumulated: {accumulated_seconds / 60:.2f} min  "
            f"average: {average_seconds / 60:.2f} min/file  "
            f"ETA: {remaining_seconds / 60:.2f} min  messages: {message_count}"
        )
        print(message, flush=True)
        with self.benchmark_log.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{message}\n")

    def _run_wgrib2_command(self, grib_file: Path) -> str:
        started_at = time.perf_counter()
        output = super()._run_wgrib2_command(grib_file)
        elapsed_seconds = time.perf_counter() - started_at
        self.inventory_accumulated_seconds += elapsed_seconds
        self._log_progress(
            "INVENTORY",
            grib_file,
            started_at,
            self.inventory_accumulated_seconds,
            len(output.splitlines()),
        )
        return output

    def _write_grib_messages(self, dataset) -> None:
        """Lee y escribe cada GRIB conservando el tiempo por archivo."""

        for grib_file in self.grib_files:
            started_at = time.perf_counter()
            file_inventory = self.wgrib2_inventory.loc[
                self.wgrib2_inventory["grib_file"] == str(grib_file)
            ]

            # Lectura GRIB y escritura NetCDF.
            with pygrib.open(str(grib_file)) as source_grib:
                for message_index, grib_message in enumerate(source_grib):
                    inventory_row = file_inventory.iloc[message_index]
                    self._write_message(dataset, inventory_row, grib_message)

            elapsed_seconds = time.perf_counter() - started_at
            self.conversion_accumulated_seconds += elapsed_seconds
            self._log_progress(
                "CONVERT",
                grib_file,
                started_at,
                self.conversion_accumulated_seconds,
                len(file_inventory),
            )


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
    parser.add_argument(
        "--model",
        default="gfs",
        help="Identificador del modelo meteorológico.",
    )
    parser.add_argument(
        "--center",
        default="ncep",
        help="Centro productor de los GRIB.",
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
    return parser.parse_args()


def main() -> None:
    """Ejecuta la corrida con el área y convención acordadas."""

    arguments = parse_arguments()
    grib_files = sorted(arguments.input_dir.glob(arguments.input_pattern))
    if arguments.file_count is not None:
        grib_files = grib_files[:arguments.file_count]
    if not grib_files:
        raise RuntimeError("No se encontraron archivos GRIB para el benchmark.")

    model = arguments.model.lower()
    center = arguments.center.lower()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_log = arguments.output_dir / f"{center}-{model}_benchmark.log"
    if benchmark_log.exists():
        raise RuntimeError(f"Ya existe el log de benchmark {benchmark_log.name}.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    started_at = time.perf_counter()
    with benchmark_log.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Inicio UTC: {datetime.now(timezone.utc).isoformat()}\n")
        log_file.write(f"Archivos: {len(grib_files)}\n")
        log_file.write("Área: (-130.0, -57.0, -10.0, 30.0)\n")
        log_file.write("Convención longitudinal: 0_360\n")
        log_file.write("Cuantización: least_significant_digit=2\n")

    converter = TimedGrib2ToNetCDF(
        grib_files,
        model=model,
        center=center,
        area=(-130.0, -57.0, -10.0, 30.0),
        longitude_convention="0_360",
        benchmark_log=benchmark_log,
    )
    netcdf_output = converter.run_conversion(arguments.output_dir)
    elapsed_seconds = time.perf_counter() - started_at
    summary = (
        f"Tiempo total: {elapsed_seconds / 60:.2f} min\n"
        f"Inventario WGRIB2: {converter.inventory_accumulated_seconds / 60:.2f} min\n"
        f"Lectura PyGRIB y escritura NetCDF: {converter.conversion_accumulated_seconds / 60:.2f} min\n"
        f"NetCDF: {netcdf_output.name}"
    )
    print(summary, flush=True)
    with benchmark_log.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{summary}\n")


if __name__ == "__main__":
    main()
