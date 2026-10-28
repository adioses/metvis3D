"""Renderiza una animación ParaView desde una configuración transitoria generada."""

from __future__ import annotations

import argparse
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
    time_sequences = {name: layer["time_values"] for name, layer in temporal_layers.items()}
    first_layer, time_values = next(iter(time_sequences.items()))
    if not time_values:
        raise RuntimeError(f"La capa temporal {first_layer} no contiene plazos.")
    inconsistent_layers = [name for name, values in time_sequences.items() if values != time_values]
    if inconsistent_layers:
        names = ", ".join([first_layer, *inconsistent_layers])
        raise RuntimeError(f"Las capas temporales no comparten los mismos plazos: {names}.")
    frame_count = len(time_values)
    print(f"ParaView renderizará {frame_count} fotogramas PNG.", flush=True)
    for frame_number, time_value in enumerate(time_values):
        view.ViewTime = time_value
        for layer in temporal_layers.values():
            layer["reader"].UpdatePipeline(time_value)
            if layer["outline"] is not None:
                layer["outline"].UpdatePipeline(time_value)
            layer["filter"].UpdatePipeline(time_value)
        Render(view)
        SaveScreenshot(
            str(frames_directory / f"frame-{frame_number:04d}.png"),
            view,
            ImageResolution=[width_px, height_px],
        )
        print(f"Fotograma {frame_number + 1}/{frame_count} generado.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renderiza una animación desde una configuración transitoria de ParaView.")
    parser.add_argument("--configuration", type=Path, required=True, help="JSON transitorio de la animación.")
    arguments = parser.parse_args()
    configuration = load_configuration(arguments.configuration)
    ResetSession()
    _DisableFirstRenderCameraReset()
    view = CreateRenderView()
    view.ViewSize = [
        int(configuration["output"]["width_px"]),
        int(configuration["output"]["height_px"]),
    ]
    temporal_layers = create_scene(view, configuration)
    render_frames(view, temporal_layers, configuration)
