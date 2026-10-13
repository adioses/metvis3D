"""Abre la topografía estática de Sudamérica dentro de ParaView.

Ejecutar desde ParaView: View > Python Shell > Run Script.
Antes debe ejecutarse scripts/prepare_static_scene.py.
"""

import json
from pathlib import Path

from paraview.simple import (
    ColorBy,
    GetActiveViewOrCreate,
    GetColorTransferFunction,
    ResetSession,
    Show,
    XMLStructuredGridReader,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCENE_DIRECTORY = PROJECT_ROOT / "paraview" / "render_data" / "static" / "south_america"
VTS_FILE = SCENE_DIRECTORY / "terrain.vts"
METADATA_FILE = SCENE_DIRECTORY / "terrain_metadata.json"


def color_values(color: str) -> list[float]:
    """Convierte un color hexadecimal de la configuración a RGB de ParaView."""

    return [int(color[position : position + 2], 16) / 255.0 for position in (1, 3, 5)]


if not VTS_FILE.exists() or not METADATA_FILE.exists():
    raise RuntimeError(
        "No existe la topografía preparada. Ejecute primero scripts/prepare_static_scene.py."
    )

with METADATA_FILE.open(encoding="utf-8") as source:
    metadata = json.load(source)

ResetSession()
terrain = XMLStructuredGridReader(registrationName="South America terrain", FileName=[str(VTS_FILE)])
view = GetActiveViewOrCreate("RenderView")
view.Background = [0.08, 0.10, 0.14]

terrain_display = Show(terrain, view)
terrain_display.Representation = "Surface"
ColorBy(terrain_display, ("POINTS", "terrain_elevation_m"))

terrain_colors = GetColorTransferFunction("terrain_elevation_m")
terrain_colors.RGBPoints = [
    component
    for elevation, color in metadata["palette"]
    for component in [float(elevation), *color_values(color)]
]
terrain_colors.ColorSpace = "RGB"
terrain_colors.NanColor = [0.15, 0.20, 0.24]
terrain_display.SetScalarBarVisibility(view, True)

terrain.UpdatePipeline()
bounds = terrain.GetDataInformation().GetBounds()
center_x = (bounds[0] + bounds[1]) / 2.0
center_y = (bounds[2] + bounds[3]) / 2.0
center_z = (bounds[4] + bounds[5]) / 2.0
horizontal_span = max(bounds[1] - bounds[0], bounds[3] - bounds[2])
view.CameraFocalPoint = [center_x, center_y, center_z]
view.CameraPosition = [
    center_x + 0.65 * horizontal_span,
    center_y - 1.10 * horizontal_span,
    center_z + 0.72 * horizontal_span,
]
view.CameraViewUp = [0.0, 0.0, 1.0]
view.CameraParallelProjection = 0
view.OrientationAxesVisibility = 1
view.StillRender()

print(f"Topografía mostrada: {VTS_FILE}")
print(f"Proyección: {metadata['projection']['name']}")
print(f"Exageración vertical: {metadata['vertical_exaggeration']}x")
