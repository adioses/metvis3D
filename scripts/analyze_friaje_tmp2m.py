"""Analiza temperatura a 2 m y su descenso en 24 horas sobre mapas regionales."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.temperature_drop_maps import run_analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF estandarizado, abierto sólo para lectura.")
    parser.add_argument(
        "--configuration", type=Path,
        default=PROJECT_ROOT / "config" / "analysis" / "friaje_tmp2m.yaml",
        help="YAML de dominio, comparación temporal, referencias y estilo.",
    )
    arguments = parser.parse_args()
    run_analysis(PROJECT_ROOT, arguments.configuration, arguments.netcdf)
