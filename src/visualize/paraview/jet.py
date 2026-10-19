"""Escribe la geometría VTS de una corriente de chorro."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from osgeo import osr

from visualize.paraview.terrain import create_coordinate_system


osr.UseExceptions()
def projected_horizontal_coordinates(
    latitude: np.ndarray,
    longitude: np.ndarray,
    target_coordinate_system: osr.SpatialReference,
) -> tuple[np.ndarray, np.ndarray]:
    """Proyecta la grilla geográfica al sistema métrico de la escena."""

    geographic_coordinate_system = osr.SpatialReference()
    geographic_coordinate_system.ImportFromEPSG(4326)
    geographic_coordinate_system.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transformer = osr.CoordinateTransformation(geographic_coordinate_system, target_coordinate_system)

    longitude_grid, latitude_grid = np.meshgrid(longitude, latitude)
    geographic_points = np.column_stack((longitude_grid.ravel(), latitude_grid.ravel()))
    projected_points = np.asarray(transformer.TransformPoints(geographic_points.tolist()), dtype=np.float64)
    return (
        projected_points[:, 0].reshape(latitude_grid.shape),
        projected_points[:, 1].reshape(latitude_grid.shape),
    )


def write_jet_vts(
    output_file: Path,
    x_coordinate_m: np.ndarray,
    y_coordinate_m: np.ndarray,
    geopotential_height_m: np.ndarray,
    wind_speed_m_s: np.ndarray,
    pressure_hpa: np.ndarray,
    vertical_exaggeration: float,
    geopotential_height_completed: np.ndarray | None = None,
) -> None:
    """Escribe la grilla estructurada VTS del volumen atmosférico seleccionado."""

    level_count, latitude_count, longitude_count = wind_speed_m_s.shape
    shape = (level_count, latitude_count, longitude_count)
    pressure_grid_hpa = np.broadcast_to(pressure_hpa[:, None, None], shape).astype("<f4")
    if geopotential_height_completed is None:
        geopotential_height_completed = np.zeros(shape, dtype=np.uint8)
    if geopotential_height_completed.shape != shape:
        raise RuntimeError("La máscara de altura geopotencial completada no coincide con el volumen de chorro.")
    points = np.empty((wind_speed_m_s.size, 3), dtype="<f4")
    points[:, 0] = np.broadcast_to(x_coordinate_m[None, :, :], shape).ravel()
    points[:, 1] = np.broadcast_to(y_coordinate_m[None, :, :], shape).ravel()
    points[:, 2] = geopotential_height_m.astype("<f4", copy=False).ravel() * vertical_exaggeration

    arrays = [
        ("wind_speed", wind_speed_m_s.astype("<f4", copy=False).ravel()),
        ("pressure_hpa", pressure_grid_hpa.ravel()),
        ("geopotential_height_m", geopotential_height_m.astype("<f4", copy=False).ravel()),
        ("geopotential_height_completed", geopotential_height_completed.astype("u1", copy=False).ravel()),
        ("Points", points.ravel()),
    ]
    offsets = []
    offset = 0
    for _, values in arrays:
        offsets.append(offset)
        offset += 8 + values.nbytes

    extent = f"0 {longitude_count - 1} 0 {latitude_count - 1} 0 {level_count - 1}"
    header = f'''<?xml version="1.0"?>
<VTKFile type="StructuredGrid" version="1.0" byte_order="LittleEndian" header_type="UInt64">
  <StructuredGrid WholeExtent="{extent}">
    <Piece Extent="{extent}">
      <PointData Scalars="wind_speed">
        <DataArray type="Float32" Name="wind_speed" format="appended" offset="{offsets[0]}" />
        <DataArray type="Float32" Name="pressure_hpa" format="appended" offset="{offsets[1]}" />
        <DataArray type="Float32" Name="geopotential_height_m" format="appended" offset="{offsets[2]}" />
        <DataArray type="UInt8" Name="geopotential_height_completed" format="appended" offset="{offsets[3]}" />
      </PointData>
      <CellData />
      <Points>
        <DataArray type="Float32" NumberOfComponents="3" Name="Points" format="appended" offset="{offsets[4]}" />
      </Points>
    </Piece>
  </StructuredGrid>
  <AppendedData encoding="raw">_'''.encode("utf-8")

    with output_file.open("wb") as destination:
        destination.write(header)
        for _, values in arrays:
            raw_values = np.ascontiguousarray(values).tobytes()
            destination.write(struct.pack("<Q", len(raw_values)))
            destination.write(raw_values)
        destination.write(b"</AppendedData>\n</VTKFile>\n")
