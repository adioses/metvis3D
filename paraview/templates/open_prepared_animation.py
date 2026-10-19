"""Carga en la vista activa una animación ParaView previamente preparada."""

import os
import sys
from pathlib import Path

from paraview.simple import GetActiveViewOrCreate, Render


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
    view = GetActiveViewOrCreate("RenderView")
    create_scene(view, configuration)
    Render(view)


open_prepared_animation()
