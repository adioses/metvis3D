"""Renderiza una animación ParaView desde una configuración transitoria generada."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from paraview.simple import (
    CreateRenderView,
    ResetSession,
    Render,
    SaveScreenshot,
    _DisableFirstRenderCameraReset,
)

from scene_setup import create_scene, load_configuration

def render_frames(view, temporal_layers: dict[str, dict], configuration: dict) -> None:
    """Captura un PNG por plazo de pronóstico, preservando una cámara fija."""

    frames_directory = Path(configuration["frames_directory"])
    frames_directory.mkdir(parents=True, exist_ok=True)
    width_px = int(configuration["output"]["width_px"])
    height_px = int(configuration["output"]["height_px"])
    if not temporal_layers:
        raise RuntimeError("La configuración no contiene capas temporales para renderizar.")
    frame_counts = {name: len(layer["frame_files"]) for name, layer in temporal_layers.items()}
    if not all(frame_counts.values()):
        raise RuntimeError("Una capa temporal no contiene VTS para renderizar.")
    if len(set(frame_counts.values())) != 1:
        details = ", ".join(f"{name}: {count}" for name, count in frame_counts.items())
        raise RuntimeError(f"Las capas temporales no tienen la misma cantidad de plazos: {details}.")
    frame_count = next(iter(frame_counts.values()))
    print(f"ParaView renderizará {frame_count} fotogramas PNG.", flush=True)
    for frame_number in range(frame_count):
        for layer in temporal_layers.values():
            layer["reader"].FileName = [layer["frame_files"][frame_number]]
            layer["reader"].UpdatePipeline()
            if layer["outline"] is not None:
                layer["outline"].UpdatePipeline()
            layer["filter"].UpdatePipeline()
        Render(view)
        SaveScreenshot(
            str(frames_directory / f"frame-{frame_number:04d}.png"),
            view,
            ImageResolution=[width_px, height_px],
        )
        print(f"Fotograma {frame_number + 1}/{frame_count} generado.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renderiza una animación desde una configuración transitoria de ParaView.")
    parser.add_argument(
        "--configuration",
        type=Path,
        default=os.environ.get("METVIS3D_PARAVIEW_CONFIGURATION"),
        help="JSON transitorio de la animación.",
    )
    parser.add_argument("--interactive", action="store_true", help="Abre la escena sin capturar fotogramas.")
    arguments = parser.parse_args()
    if arguments.configuration is None:
        parser.error("Debe indicar --configuration o METVIS3D_PARAVIEW_CONFIGURATION.")
    configuration = load_configuration(arguments.configuration)
    ResetSession()
    _DisableFirstRenderCameraReset()
    view = CreateRenderView()
    view.ViewSize = [
        int(configuration["output"]["width_px"]),
        int(configuration["output"]["height_px"]),
    ]
    temporal_layers = create_scene(view, configuration)
    interactive = arguments.interactive or os.environ.get("METVIS3D_PARAVIEW_INTERACTIVE") == "1"
    if not interactive:
        render_frames(view, temporal_layers, configuration)
