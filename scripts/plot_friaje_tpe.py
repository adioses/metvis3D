"""Genera mapas de TPE y viento con límites de países para revisar friajes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.friaje_maps import run_maps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF estandarizado; se abre sólo para lectura.")
    parser.add_argument(
        "--configuration", type=Path,
        default=PROJECT_ROOT / "config" / "analysis" / "friaje_tpe.yaml",
        help="YAML de niveles, umbral, dominio y estilo de los mapas.",
    )
    parser.add_argument("--forecast-hours", type=float, nargs="+", help="Plazos nativos que sustituyen la selección YAML.")
    arguments = parser.parse_args()
    run_maps(PROJECT_ROOT, arguments.configuration, arguments.netcdf, arguments.forecast_hours)
