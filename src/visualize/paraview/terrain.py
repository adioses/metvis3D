"""Prepara la geometría estática de una escena meteorológica en ParaView."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from osgeo import gdal, osr
import yaml


gdal.UseExceptions()
osr.UseExceptions()


def load_scene_configuration(configuration_file: Path) -> dict:
    """Lee la configuración YAML versionada de una escena."""

    with configuration_file.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


def create_coordinate_system(proj4: str) -> osr.SpatialReference:
    """Construye una referencia espacial con orden convencional longitud/latitud."""

    coordinate_system = osr.SpatialReference()
    coordinate_system.ImportFromProj4(proj4)
    coordinate_system.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return coordinate_system


def projected_bounds(bounds: dict, target_coordinate_system: osr.SpatialReference) -> tuple[float, float, float, float]:
    """Proyecta los bordes del dominio para no recortar esquinas de la escena."""

    geographic_coordinate_system = osr.SpatialReference()
    geographic_coordinate_system.ImportFromEPSG(4326)
    geographic_coordinate_system.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transformer = osr.CoordinateTransformation(geographic_coordinate_system, target_coordinate_system)

    west, south = bounds["west"], bounds["south"]
    east, north = bounds["east"], bounds["north"]
    edge_fraction = np.linspace(0.0, 1.0, 65)
    coordinates = []
    for fraction in edge_fraction:
        longitude = west + (east - west) * fraction
        latitude = south + (north - south) * fraction
        coordinates.extend(((longitude, south), (longitude, north), (west, latitude), (east, latitude)))

    projected = np.asarray([transformer.TransformPoint(longitude, latitude)[:2] for longitude, latitude in coordinates])
    return (
        float(projected[:, 0].min()),
        float(projected[:, 1].min()),
        float(projected[:, 0].max()),
        float(projected[:, 1].max()),
    )


def prepare_projected_dem(project_root: Path, scene: dict, output_file: Path) -> None:
    """Recorta y proyecta el GeoTIFF fuente a la resolución de renderizado."""

    topography = scene["topography"]
    source_file = project_root / topography["source_geotiff"]
    if not source_file.exists():
        raise RuntimeError(f"No existe el GeoTIFF de topografía: {source_file}")

    bounds = scene["bounds"]
    target_coordinate_system = create_coordinate_system(scene["projection"]["proj4"])
    output_bounds = projected_bounds(bounds, target_coordinate_system)
    source_vrt = f"/vsimem/{scene['name']}_topography.vrt"

    try:
        clipped_source = gdal.Translate(
            source_vrt,
            str(source_file),
            options=gdal.TranslateOptions(
                format="VRT",
                projWin=[bounds["west"], bounds["north"], bounds["east"], bounds["south"]],
            ),
        )
        if clipped_source is None:
            raise RuntimeError("No se pudo recortar el GeoTIFF de topografía.")
        clipped_source = None

        output_file.parent.mkdir(parents=True, exist_ok=True)
        warped = gdal.Warp(
            str(output_file),
            source_vrt,
            options=gdal.WarpOptions(
                format="GTiff",
                dstSRS=scene["projection"]["proj4"],
                outputBounds=output_bounds,
                xRes=topography["render_resolution_m"],
                yRes=topography["render_resolution_m"],
                targetAlignedPixels=True,
                resampleAlg=gdal.GRA_Average,
                srcNodata=-32768,
                dstNodata=-32768,
                multithread=True,
                creationOptions=[
                    "TILED=YES",
                    "COMPRESS=DEFLATE",
                    "PREDICTOR=2",
                    "ZLEVEL=6",
                    "BIGTIFF=IF_SAFER",
                ],
            ),
        )
        if warped is None:
            raise RuntimeError("No se pudo proyectar el DEM para la escena.")
        warped = None
    finally:
        gdal.Unlink(source_vrt)


def write_vts(output_file: Path, elevation_m: np.ndarray, geotransform: tuple[float, ...], sea_level_m: float, vertical_exaggeration: float) -> None:
    """Escribe una malla estructurada VTS con el relieve y el océano plano."""

    height, width = elevation_m.shape
    nodata = elevation_m == -32768
    terrain_elevation_m = elevation_m.astype("<f4", copy=True)
    terrain_elevation_m[nodata] = sea_level_m
    surface_height_m = np.maximum(terrain_elevation_m, sea_level_m).astype("<f4", copy=False)

    x_coordinate = geotransform[0] + (np.arange(width, dtype=np.float64) + 0.5) * geotransform[1]
    y_coordinate = geotransform[3] + (np.arange(height, dtype=np.float64) + 0.5) * geotransform[5]
    point_count = width * height
    points = np.empty((point_count, 3), dtype="<f4")
    points[:, 0] = np.tile(x_coordinate, height)
    points[:, 1] = np.repeat(y_coordinate, width)
    points[:, 2] = surface_height_m.ravel() * vertical_exaggeration

    arrays = [
        ("terrain_elevation_m", terrain_elevation_m.ravel()),
        ("surface_height_m", surface_height_m.ravel()),
        ("Points", points.ravel()),
    ]
    offsets = []
    offset = 0
    for _, values in arrays:
        offsets.append(offset)
        offset += 8 + values.nbytes

    extent = f"0 {width - 1} 0 {height - 1} 0 0"
    header = f'''<?xml version="1.0"?>
<VTKFile type="StructuredGrid" version="1.0" byte_order="LittleEndian" header_type="UInt64">
  <StructuredGrid WholeExtent="{extent}">
    <Piece Extent="{extent}">
      <PointData Scalars="terrain_elevation_m">
        <DataArray type="Float32" Name="terrain_elevation_m" format="appended" offset="{offsets[0]}" />
        <DataArray type="Float32" Name="surface_height_m" format="appended" offset="{offsets[1]}" />
      </PointData>
      <CellData />
      <Points>
        <DataArray type="Float32" NumberOfComponents="3" Name="Points" format="appended" offset="{offsets[2]}" />
      </Points>
    </Piece>
  </StructuredGrid>
  <AppendedData encoding="raw">_'''.encode("utf-8")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as destination:
        destination.write(header)
        for _, values in arrays:
            raw_values = np.ascontiguousarray(values).tobytes()
            destination.write(struct.pack("<Q", len(raw_values)))
            destination.write(raw_values)
        destination.write(b"</AppendedData>\n</VTKFile>\n")


def terrain_matches_scene(metadata_file: Path, scene: dict, vertical_exaggeration: float) -> bool:
    """Comprueba si el terreno preparado corresponde exactamente a la escena solicitada."""

    if not metadata_file.exists():
        return False

    with metadata_file.open(encoding="utf-8") as source:
        metadata = json.load(source)

    topography = scene["topography"]
    return (
        metadata.get("scene") == scene["name"]
        and metadata.get("bounds_wgs84") == scene["bounds"]
        and metadata.get("projection") == scene["projection"]
        and metadata.get("source_geotiff") == topography["source_geotiff"]
        and metadata.get("render_resolution_m") == topography["render_resolution_m"]
        and metadata.get("vertical_exaggeration") == vertical_exaggeration
        and metadata.get("sea_level_m") == topography["sea_level_m"]
    )


def prepare_static_scene(
    project_root: Path,
    configuration_file: Path,
    overwrite: bool = False,
    vertical_exaggeration: float | None = None,
    reuse_matching_terrain: bool = False,
) -> dict[str, Path]:
    """Ejecuta la preparación completa del relieve estático de una escena."""

    scene = load_scene_configuration(configuration_file)
    scene_directory = project_root / "paraview" / "render_data" / scene["name"] / "terrain"
    projected_dem_file = scene_directory / "terrain_projected.tif"
    terrain_vts_file = scene_directory / "terrain.vts"
    metadata_file = scene_directory / "terrain_metadata.json"

    if vertical_exaggeration is None:
        vertical_exaggeration = scene["topography"]["vertical_exaggeration"]

    existing_outputs = [
        output_file
        for output_file in (projected_dem_file, terrain_vts_file, metadata_file)
        if output_file.exists()
    ]
    if reuse_matching_terrain and all(
        output_file.exists() for output_file in (projected_dem_file, terrain_vts_file, metadata_file)
    ) and terrain_matches_scene(metadata_file, scene, vertical_exaggeration):
        return {
            "projected_dem": projected_dem_file,
            "terrain_vts": terrain_vts_file,
            "metadata": metadata_file,
        }
    if existing_outputs and not overwrite:
        existing_names = ", ".join(output_file.name for output_file in existing_outputs)
        raise RuntimeError(
            "Ya existe una escena estática preparada "
            f"({existing_names}). Use --overwrite tras revisar los cambios."
        )

    if existing_outputs:
        for output_file in existing_outputs:
            output_file.unlink()

    prepare_projected_dem(project_root, scene, projected_dem_file)
    projected_dem = gdal.Open(str(projected_dem_file), gdal.GA_ReadOnly)
    if projected_dem is None:
        raise RuntimeError(f"No se pudo abrir el DEM proyectado: {projected_dem_file}")

    elevation_m = projected_dem.GetRasterBand(1).ReadAsArray()
    write_vts(
        terrain_vts_file,
        elevation_m,
        projected_dem.GetGeoTransform(),
        scene["topography"]["sea_level_m"],
        vertical_exaggeration,
    )
    metadata = {
        "scene": scene["name"],
        "bounds_wgs84": scene["bounds"],
        "projection": scene["projection"],
        "source_geotiff": scene["topography"]["source_geotiff"],
        "render_resolution_m": scene["topography"]["render_resolution_m"],
        "vertical_exaggeration": vertical_exaggeration,
        "sea_level_m": scene["topography"]["sea_level_m"],
        "grid_dimensions": [int(projected_dem.RasterXSize), int(projected_dem.RasterYSize)],
        "palette": scene["style"]["palette"],
    }
    projected_dem = None
    with metadata_file.open("w", encoding="utf-8") as destination:
        json.dump(metadata, destination, ensure_ascii=False, indent=2)
        destination.write("\n")

    return {
        "projected_dem": projected_dem_file,
        "terrain_vts": terrain_vts_file,
        "metadata": metadata_file,
    }
