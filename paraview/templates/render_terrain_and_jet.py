"""Muestra el terreno y una isosuperficie de 30 m/s de corriente de chorro.

Ejecutar desde ParaView: View > Python Shell > Run Script.
Antes deben ejecutarse prepare_static_scene.py y prepare_jet_scene.py.
"""

import json
from pathlib import Path

from paraview.simple import (
    ColorBy,
    Contour,
    GetActiveViewOrCreate,
    GetColorTransferFunction,
    ResetSession,
    Show,
    XMLStructuredGridReader,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TERRAIN_DIRECTORY = PROJECT_ROOT / "paraview" / "render_data" / "static" / "south_america"
JET_DIRECTORY = PROJECT_ROOT / "paraview" / "render_data" / "atmosphere" / "south_america_jet_30mps"
TERRAIN_VTS_FILE = TERRAIN_DIRECTORY / "terrain.vts"
TERRAIN_METADATA_FILE = TERRAIN_DIRECTORY / "terrain_metadata.json"
JET_VTS_FILE = JET_DIRECTORY / "jet.vts"
JET_METADATA_FILE = JET_DIRECTORY / "jet_metadata.json"


def color_values(color: str) -> list[float]:
    """Convierte un color hexadecimal a RGB para una paleta de ParaView."""

    return [int(color[position : position + 2], 16) / 255.0 for position in (1, 3, 5)]


for required_file in (TERRAIN_VTS_FILE, TERRAIN_METADATA_FILE, JET_VTS_FILE, JET_METADATA_FILE):
    if not required_file.exists():
        raise RuntimeError(f"No existe el insumo preparado: {required_file}")

with TERRAIN_METADATA_FILE.open(encoding="utf-8") as source:
    terrain_metadata = json.load(source)
with JET_METADATA_FILE.open(encoding="utf-8") as source:
    jet_metadata = json.load(source)

if terrain_metadata["projection"]["proj4"] != jet_metadata["projection"]["proj4"]:
    raise RuntimeError("El terreno y el chorro usan proyecciones distintas.")
if terrain_metadata["vertical_exaggeration"] != jet_metadata["vertical_exaggeration"]:
    raise RuntimeError("El terreno y el chorro usan exageraciones verticales distintas.")

ResetSession()
terrain = XMLStructuredGridReader(registrationName="South America terrain", FileName=[str(TERRAIN_VTS_FILE)])
jet = XMLStructuredGridReader(registrationName="Jet volume", FileName=[str(JET_VTS_FILE)])
jet_surface = Contour(registrationName="Jet speed 30 m/s", Input=jet)
jet_surface.ContourBy = ["POINTS", "wind_speed"]
jet_surface.Isosurfaces = [jet_metadata["wind_speed_isosurface_m_s"]]

view = GetActiveViewOrCreate("RenderView")
view.Background = [0.08, 0.10, 0.14]

terrain_display = Show(terrain, view)
terrain_display.Representation = "Surface"
ColorBy(terrain_display, ("POINTS", "terrain_elevation_m"))
terrain_colors = GetColorTransferFunction("terrain_elevation_m")
terrain_colors.RGBPoints = [
    component
    for elevation, color in terrain_metadata["palette"]
    for component in [float(elevation), *color_values(color)]
]
terrain_colors.ColorSpace = "RGB"

jet_display = Show(jet_surface, view)
jet_display.Representation = "Surface"
jet_display.DiffuseColor = [0.98, 0.53, 0.12]
jet_display.Opacity = 0.88

terrain.UpdatePipeline()
jet_surface.UpdatePipeline()
terrain_bounds = terrain.GetDataInformation().GetBounds()
jet_bounds = jet_surface.GetDataInformation().GetBounds()
bounds = [
    min(terrain_bounds[0], jet_bounds[0]),
    max(terrain_bounds[1], jet_bounds[1]),
    min(terrain_bounds[2], jet_bounds[2]),
    max(terrain_bounds[3], jet_bounds[3]),
    min(terrain_bounds[4], jet_bounds[4]),
    max(terrain_bounds[5], jet_bounds[5]),
]
center_x = (bounds[0] + bounds[1]) / 2.0
center_y = (bounds[2] + bounds[3]) / 2.0
center_z = (bounds[4] + bounds[5]) / 2.0
horizontal_span = max(bounds[1] - bounds[0], bounds[3] - bounds[2])
view.CameraFocalPoint = [center_x, center_y, center_z]
view.CameraPosition = [
    center_x + 0.68 * horizontal_span,
    center_y - 1.15 * horizontal_span,
    center_z + 0.75 * horizontal_span,
]
view.CameraViewUp = [0.0, 0.0, 1.0]
view.CameraParallelProjection = 0
view.OrientationAxesVisibility = 1
view.StillRender()

print(f"Terreno: {TERRAIN_VTS_FILE}")
print(f"Chorro: {JET_VTS_FILE}")
print(f"Tiempo válido: {jet_metadata['valid_time_utc']}")
print(f"Isosuperficie: {jet_metadata['wind_speed_isosurface_m_s']} m/s")
