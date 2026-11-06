"""Prepara, abre o renderiza la animación de friaje con Met.3D."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.met3d_animation import open_animation, prepare_animation, render_animation


def run_animation(arguments: argparse.Namespace) -> None:
    """Muestra el flujo lineal de preparación, exploración o render del friaje."""

    # Leer YAML y NetCDF; reutilizar los datos sólo cuando se solicita explícitamente.
    preparation = prepare_animation(
        PROJECT_ROOT,
        arguments.animation,
        arguments.netcdf,
        for_render=arguments.render,
        reuse_netcdf=arguments.reuse_temporal,
    )
    files = preparation["files"]

    # Informar archivos materializados para inspección y reproducción.
    print("Configuraciones Met.3D preparadas:")
    for name, filename in files.items():
        print(f"- {name}: {filename}")

    # Abrir interfaz para validar la escena o ejecutar el batch solicitado.
    if arguments.render:
        video_file = render_animation(preparation, arguments.conda, arguments.met3d_environment)
        print(f"Video friaje generado: {video_file}")
        return

    open_animation(preparation, arguments.conda, arguments.met3d_environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara, abre o renderiza la animación de friaje con Met.3D.")
    parser.add_argument(
        "--animation",
        type=Path,
        default=PROJECT_ROOT / "config" / "met3d" / "animations" / "south_america_friaje.yaml",
        help="YAML de la animación Met.3D.",
    )
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF estandarizado de una corrida completa.")
    parser.add_argument(
        "--reuse-temporal", action="store_true",
        help="Reutiliza el NetCDF temporal de visualización sólo si existe y es compatible; si no, detiene la ejecución.",
    )
    parser.add_argument("--conda", default="conda", help="Comando Conda que contiene Met.3D.")
    parser.add_argument("--met3d-environment", default="metvis3d", help="Nombre del ambiente Conda que contiene Met.3D.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--open", action="store_true", help="Abre Met.3D para revisar la escena y ajustar la cámara.")
    action.add_argument("--render", action="store_true", help="Renderiza los fotogramas y codifica el MP4.")
    run_animation(parser.parse_args())
