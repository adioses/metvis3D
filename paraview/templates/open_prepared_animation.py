"""Carga en la vista activa una animación ParaView previamente preparada."""

import os
import sys
from pathlib import Path

from paraview.simple import (
    GetActiveViewOrCreate,
    GetAnimationScene,
    Render,
    ResetSession,
    _DisableFirstRenderCameraReset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIRECTORY = PROJECT_ROOT / "paraview" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from scene_setup import create_scene, load_configuration


def open_prepared_animation() -> None:
    """Carga las capas del JSON transitorio indicado al iniciar ParaView."""

    configuration_name = os.environ.get("METVIS3D_PARAVIEW_CONFIGURATION")
    if configuration_name is None:
        raise RuntimeError(
            "Defina METVIS3D_PARAVIEW_CONFIGURATION con el render_configuration.json "
            "generado por scripts/run_paraview_animation.py."
        )
    configuration = load_configuration(Path(configuration_name))
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
