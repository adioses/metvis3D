"""Prepara el relieve estático de una escena meteorológica para ParaView."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.static_scene import prepare_static_scene


def run_preparation(configuration_file: Path, overwrite: bool) -> None:
    """Prepara el DEM proyectado, la malla VTS y los metadatos de la escena."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración de escena: {configuration_file}")

    outputs = prepare_static_scene(PROJECT_ROOT, configuration_file, overwrite=overwrite)
    print(f"DEM proyectado: {outputs['projected_dem']}")
    print(f"Malla VTS: {outputs['terrain_vts']}")
    print(f"Metadatos: {outputs['metadata']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara una escena topográfica estática para ParaView.")
    parser.add_argument(
        "--scene",
        type=Path,
        default=PROJECT_ROOT / "config" / "scenes" / "south_america.yaml",
        help="Archivo YAML de la escena.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reemplaza los productos estáticos existentes de la escena.",
    )
    arguments = parser.parse_args()
    run_preparation(arguments.scene, arguments.overwrite)
