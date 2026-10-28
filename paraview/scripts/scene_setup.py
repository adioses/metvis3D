"""Construye una escena ParaView desde las capas preparadas de una animación."""

from __future__ import annotations

import json
from pathlib import Path

from paraview.simple import (
    ColorBy,
    Contour,
    GetColorTransferFunction,
    Outline,
    PVDReader,
    Show,
    XMLStructuredGridReader,
)


def color_values(color: str) -> list[float]:
    """Convierte un color hexadecimal a componentes RGB de ParaView."""

    return [int(color[position : position + 2], 16) / 255.0 for position in (1, 3, 5)]


def load_configuration(configuration_file: Path) -> dict:
    """Lee la configuración transitoria preparada por el flujo científico."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración transitoria de ParaView: {configuration_file}")
    with configuration_file.open(encoding="utf-8") as source:
        return json.load(source)


def configure_camera(view, camera: dict) -> None:
    """Aplica la cámara declarada por la animación, sin recalcular su encuadre."""

    view.CameraPosition = camera["position"]
    view.CameraFocalPoint = camera["focal_point"]
    view.CameraViewUp = camera["view_up"]
    view.CameraParallelProjection = int(camera["parallel_projection"])
    if camera["parallel_projection"]:
        view.CameraParallelScale = camera["parallel_scale"]
    else:
        view.CameraViewAngle = camera["view_angle_degrees"]


def add_terrain(view, layer: dict) -> None:
    """Incorpora la capa estática de relieve y su paleta hipsométrica."""

    metadata_file = Path(layer["metadata_file"])
    with metadata_file.open(encoding="utf-8") as source:
        metadata = json.load(source)
    terrain = XMLStructuredGridReader(registrationName=layer["name"], FileName=[layer["file"]])
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


def add_wind_speed_isosurface(view, layer: dict) -> dict:
    """Incorpora el volumen temporal de viento y sus actores visibles."""

    collection_file = Path(layer["collection_file"])
    if not collection_file.exists():
        raise RuntimeError(f"No existe la colección temporal de la capa {layer['name']}: {collection_file}")
    volume = PVDReader(registrationName=f"{layer['name']} volume", FileName=str(collection_file))
    volume.UpdatePipelineInformation()
    time_values = list(volume.TimestepValues)
    if not time_values:
        raise RuntimeError(f"La colección temporal de la capa {layer['name']} no contiene plazos.")
    volume_outline = layer["volume_outline"]
    outline = None
    if volume_outline is not None:
        outline = Outline(registrationName=f"{layer['name']} outline", Input=volume)
        outline_display = Show(outline, view)
        outline_display.Representation = "Wireframe"
        outline_display.DiffuseColor = volume_outline["color"]
        outline_display.Opacity = volume_outline["opacity"]
        outline_display.LineWidth = volume_outline["line_width_px"]

    isosurface = Contour(registrationName=layer["name"], Input=volume)
    isosurface.ContourBy = ["POINTS", "wind_speed"]
    isosurface.Isosurfaces = [layer["isosurface"]["value_m_s"]]
    isosurface_display = Show(isosurface, view)
    isosurface_display.Representation = "Surface"
    ColorBy(isosurface_display, None)
    isosurface_display.DiffuseColor = layer["isosurface"]["color"]
    isosurface_display.Opacity = layer["isosurface"]["opacity"]
    return {"reader": volume, "outline": outline, "filter": isosurface, "time_values": time_values}


def create_scene(view, configuration: dict) -> dict[str, dict]:
    """Carga las capas declaradas y devuelve únicamente las fuentes temporales."""

    view.Background = configuration["scene"]["style"]["background"]
    temporal_layers: dict[str, dict] = {}
    for layer in configuration["layers"]:
        layer_type = layer["type"]
        if layer_type == "terrain":
            add_terrain(view, layer)
        elif layer_type == "wind_speed_isosurface":
            temporal_layers[layer["name"]] = add_wind_speed_isosurface(view, layer)
        else:
            raise RuntimeError(f"El renderizador ParaView no reconoce el tipo de capa '{layer_type}'.")
    configure_camera(view, configuration["camera"])
    return temporal_layers
