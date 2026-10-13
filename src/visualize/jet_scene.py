"""Prepara una escena VTS estática para explorar una corriente de chorro."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, num2date
from osgeo import osr
import yaml

from visualize.static_scene import create_coordinate_system, load_scene_configuration


osr.UseExceptions()


def load_product_configuration(configuration_file: Path) -> dict:
    """Lee la configuración YAML de un producto de visualización."""

    with configuration_file.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


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
) -> None:
    """Escribe la grilla estructurada VTS del volumen atmosférico seleccionado."""

    level_count, latitude_count, longitude_count = wind_speed_m_s.shape
    shape = (level_count, latitude_count, longitude_count)
    pressure_grid_hpa = np.broadcast_to(pressure_hpa[:, None, None], shape).astype("<f4")
    points = np.empty((wind_speed_m_s.size, 3), dtype="<f4")
    points[:, 0] = np.broadcast_to(x_coordinate_m[None, :, :], shape).ravel()
    points[:, 1] = np.broadcast_to(y_coordinate_m[None, :, :], shape).ravel()
    points[:, 2] = geopotential_height_m.astype("<f4", copy=False).ravel() * vertical_exaggeration

    arrays = [
        ("wind_speed", wind_speed_m_s.astype("<f4", copy=False).ravel()),
        ("pressure_hpa", pressure_grid_hpa.ravel()),
        ("geopotential_height_m", geopotential_height_m.astype("<f4", copy=False).ravel()),
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
      </PointData>
      <CellData />
      <Points>
        <DataArray type="Float32" NumberOfComponents="3" Name="Points" format="appended" offset="{offsets[3]}" />
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


def prepare_jet_scene(project_root: Path, product_configuration_file: Path, overwrite: bool = False) -> dict[str, Path]:
    """Prepara una sola hora de chorro para combinarla con el terreno estático."""

    product = load_product_configuration(product_configuration_file)
    scene_configuration_file = project_root / product["scene_configuration"]
    scene = load_scene_configuration(scene_configuration_file)
    output_directory = project_root / "paraview" / "render_data" / "atmosphere" / product["name"]
    vts_file = output_directory / "jet.vts"
    metadata_file = output_directory / "jet_metadata.json"
    existing_outputs = [output_file for output_file in (vts_file, metadata_file) if output_file.exists()]
    if existing_outputs and not overwrite:
        existing_names = ", ".join(output_file.name for output_file in existing_outputs)
        raise RuntimeError(
            f"Ya existe el producto de chorro ({existing_names}). Use --overwrite tras revisar los cambios."
        )

    source = product["source"]
    geometry = product["geometry"]
    source_file = project_root / source["standardized_netcdf"]
    if not source_file.exists():
        raise RuntimeError(f"No existe el NetCDF estandarizado: {source_file}")

    with Dataset(source_file) as dataset:
        required_variables = [
            source["wind_u"],
            source["wind_v"],
            source["geopotential_height"],
            "lev",
            "latitude",
            "longitude",
            "time",
        ]
        missing_variables = [name for name in required_variables if name not in dataset.variables]
        if missing_variables:
            raise RuntimeError(f"Faltan variables requeridas para el chorro: {', '.join(missing_variables)}")

        time_index = source["time_index"]
        time_coordinate = dataset.variables["time"]
        if not 0 <= time_index < len(time_coordinate):
            raise RuntimeError(f"time_index debe estar entre 0 y {len(time_coordinate) - 1}.")

        pressure_hpa = np.asarray(dataset.variables["lev"][:], dtype=np.float64)
        selected_levels = np.flatnonzero(
            (pressure_hpa >= geometry["pressure_min_hpa"])
            & (pressure_hpa <= geometry["pressure_max_hpa"])
        )
        if selected_levels.size < 2:
            raise RuntimeError("El intervalo de presión seleccionado no contiene suficientes niveles.")

        sample_rate = geometry["horizontal_sample_rate"]
        latitude = np.asarray(dataset.variables["latitude"][::sample_rate], dtype=np.float64)
        longitude = np.asarray(dataset.variables["longitude"][::sample_rate], dtype=np.float64)
        selection = (time_index, selected_levels, slice(None, None, sample_rate), slice(None, None, sample_rate))
        wind_u = np.asarray(dataset.variables[source["wind_u"]][selection], dtype=np.float32)
        wind_v = np.asarray(dataset.variables[source["wind_v"]][selection], dtype=np.float32)
        geopotential_height_m = np.asarray(
            dataset.variables[source["geopotential_height"]][selection], dtype=np.float32
        )
        valid_time = num2date(
            time_coordinate[time_index],
            time_coordinate.units,
            calendar=getattr(time_coordinate, "calendar", "standard"),
        ).isoformat()

    wind_speed_m_s = np.hypot(wind_u, wind_v).astype(np.float32)
    threshold_m_s = product["visualization"]["wind_speed_isosurface_m_s"]
    if float(wind_speed_m_s.max()) < threshold_m_s:
        raise RuntimeError(
            f"No hay rapidez de viento de al menos {threshold_m_s} m/s en el intervalo de presión seleccionado."
        )

    target_coordinate_system = create_coordinate_system(scene["projection"]["proj4"])
    x_coordinate_m, y_coordinate_m = projected_horizontal_coordinates(
        latitude, longitude, target_coordinate_system
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    selected_pressure_hpa = pressure_hpa[selected_levels]
    write_jet_vts(
        vts_file,
        x_coordinate_m,
        y_coordinate_m,
        geopotential_height_m,
        wind_speed_m_s,
        selected_pressure_hpa,
        scene["topography"]["vertical_exaggeration"],
    )

    metadata = {
        "product": product["name"],
        "valid_time_utc": valid_time,
        "source_netcdf": source["standardized_netcdf"],
        "pressure_range_hpa": [geometry["pressure_min_hpa"], geometry["pressure_max_hpa"]],
        "selected_pressure_levels_hpa": selected_pressure_hpa.tolist(),
        "horizontal_sample_rate": sample_rate,
        "grid_dimensions": [int(len(longitude)), int(len(latitude)), int(selected_levels.size)],
        "wind_speed_range_m_s": [float(wind_speed_m_s.min()), float(wind_speed_m_s.max())],
        "wind_speed_isosurface_m_s": threshold_m_s,
        "projection": scene["projection"],
        "vertical_exaggeration": scene["topography"]["vertical_exaggeration"],
        "vertical_coordinate": "geopotential height at isobaric levels (gpm)",
    }
    with metadata_file.open("w", encoding="utf-8") as destination:
        json.dump(metadata, destination, ensure_ascii=False, indent=2)
        destination.write("\n")

    return {"jet_vts": vts_file, "metadata": metadata_file}
