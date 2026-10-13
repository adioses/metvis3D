"""Prepara una isosuperficie de corriente de chorro para la escena sudamericana."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.jet_scene import prepare_jet_scene


def run_preparation(configuration_file: Path, overwrite: bool) -> None:
    """Prepara el VTS atmosférico estático y conserva sus metadatos."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración del producto: {configuration_file}")

    outputs = prepare_jet_scene(PROJECT_ROOT, configuration_file, overwrite=overwrite)
    print(f"VTS de chorro: {outputs['jet_vts']}")
    print(f"Metadatos: {outputs['metadata']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara un chorro estático para ParaView.")
    parser.add_argument(
        "--product",
        type=Path,
        default=PROJECT_ROOT / "config" / "products" / "south_america_jet_30mps.yaml",
        help="Archivo YAML del producto de chorro.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reemplaza los productos atmosféricos existentes.",
    )
    arguments = parser.parse_args()
    run_preparation(arguments.product, arguments.overwrite)
