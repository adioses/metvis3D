"""Prepara o renderiza una animación meteorológica con ParaView."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.paraview.animation import prepare_animation, render_animation


def run_animation(arguments: argparse.Namespace) -> None:
    """Muestra el flujo lineal de preparación o renderizado."""

    # Leer YAML y NetCDF; reemplazar sólo los datos transitorios de esta corrida.
    print("Preparando render_data de ParaView...", flush=True)
    preparation = prepare_animation(PROJECT_ROOT, arguments.animation, arguments.netcdf)
    files = preparation["files"]
    print("render_data de ParaView preparada.", flush=True)

    # Informar los artefactos materializados para su revisión reproducible.
    print("Configuraciones ParaView preparadas:")
    for name, filename in files.items():
        print(f"- {name}: {filename}")

    if arguments.prepare_only:
        return
    if arguments.render:
        print("Generando fotogramas PNG con ParaView...", flush=True)
        video_file = render_animation(preparation, arguments.pvpython)
        print(f"Video generado: {video_file}")
        return
    print("Abra ParaView con METVIS3D_PARAVIEW_CONFIGURATION y ejecute paraview/templates/open_prepared_animation.py.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara o renderiza una animación meteorológica con ParaView.")
    parser.add_argument(
        "--animation",
        type=Path,
        default=PROJECT_ROOT / "config" / "paraview" / "animations" / "south_america_jet.yaml",
        help="YAML de la animación ParaView.",
    )
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF estandarizado de una corrida completa.")
    parser.add_argument("--pvpython", default="pvpython", help="Comando pvpython para renderizar sin interfaz.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare-only", action="store_true", help="Genera los datos y el script para el Python Shell de ParaView.")
    action.add_argument("--render", action="store_true", help="Renderiza los fotogramas y codifica el MP4.")
    run_animation(parser.parse_args())
