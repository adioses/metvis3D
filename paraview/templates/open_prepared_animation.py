"""Carga una animación ParaView desde el directorio transitorio preparado."""

import sys
from pathlib import Path

from paraview.simple import (
    GetActiveViewOrCreate,
    GetAnimationScene,
    Render,
    ResetSession,
    _DisableFirstRenderCameraReset,
)


RENDER_DIRECTORY = Path(__file__).resolve().parent
SCRIPTS_DIRECTORY = RENDER_DIRECTORY.parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from scene_setup import create_scene, load_configuration


def open_prepared_animation() -> None:
    """Carga las capas del JSON transitorio que acompaña a este script."""

    configuration_file = RENDER_DIRECTORY / "render_configuration.json"
    if not configuration_file.exists():
        raise RuntimeError(
            "No existe render_configuration.json junto al script de apertura. "
            "Prepare la animación y ejecute el script generado en paraview/render_cache/."
        )
    configuration = load_configuration(configuration_file)
    ResetSession()
    _DisableFirstRenderCameraReset()
    view = GetActiveViewOrCreate("RenderView")
    view.ViewSize = [
        int(configuration["output"]["width_px"]),
        int(configuration["output"]["height_px"]),
    ]
    temporal_layers = create_scene(view, configuration)
    time_values = next(iter(temporal_layers.values()))["time_values"]
    animation_scene = GetAnimationScene()
    animation_scene.UpdateAnimationUsingDataTimeSteps()
    animation_scene.AnimationTime = time_values[0]
    view.ViewTime = time_values[0]
    Render(view)


open_prepared_animation()
