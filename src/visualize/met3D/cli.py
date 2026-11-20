"""Comparte las opciones operativas de los productos Met.3D."""

from __future__ import annotations

import argparse
from pathlib import Path

from visualize.met3d_animation import prepare_animation
from visualize.met3D.render import open_animation, render_animation, render_frame


def run_animation(project_root: Path, configuration_name: str, description: str) -> None:
    """Lee los parámetros, prepara la escena y ejecuta la salida solicitada."""

    # Seleccionar una corrida y una operación sin duplicar opciones entre productos.
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--animation", type=Path, default=project_root / "config/met3d/animations" / configuration_name, help="YAML de la animación Met.3D.")
    parser.add_argument("--netcdf", type=Path, required=True, help="NetCDF estandarizado de una corrida completa; se aceptan sus NoData.")
    parser.add_argument("--reuse-temporal", action="store_true", help="Reutiliza el NetCDF de visualización si coinciden origen, selección y receta de máscaras; no recorre sus volúmenes.")
    parser.add_argument("--conda", default="conda", help="Comando Conda que contiene Met.3D.")
    parser.add_argument("--met3d-environment", default="metvis3d", help="Nombre del ambiente Conda que contiene Met.3D.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--open", action="store_true", help="Abre Met.3D para revisar la escena y ajustar la cámara.")
    action.add_argument("--render", action="store_true", help="Renderiza los fotogramas y codifica y verifica el MP4.")
    action.add_argument("--frame-hour", type=float, metavar="HOURS", help="Exporta un PNG de un plazo nativo con cámara fija. El batch captura internamente desde el primer plazo para conservar la historia del viento.")
    arguments = parser.parse_args()

    # Preparar campos y escena, conservando los valores ausentes del modelo.
    preparation = prepare_animation(
        project_root, arguments.animation, arguments.netcdf,
        for_render=arguments.render or arguments.frame_hour is not None,
        reuse_netcdf=arguments.reuse_temporal, forecast_hour=arguments.frame_hour,
    )
    valid_times = preparation["timeline"]["valid_times"]
    print(f"{preparation['animation']['name']}: {len(valid_times)} tiempos de captura, de {valid_times[0]} a {valid_times[-1]} UTC.")
    print(f"Configuraciones y registro de comprobaciones: {preparation['runtime_directory']}")
    if arguments.frame_hour is not None:
        print(f"Se exportará únicamente el PNG del plazo +{arguments.frame_hour:g} h.", flush=True)
        result = render_frame(preparation, arguments.conda, arguments.met3d_environment)
    elif arguments.render:
        result = render_animation(preparation, arguments.conda, arguments.met3d_environment)
    else:
        open_animation(preparation, arguments.conda, arguments.met3d_environment)
        return
    print(f"Producto generado y verificado: {result}")
