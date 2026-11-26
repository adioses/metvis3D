"""Prepara, abre y renderiza animaciones meteorológicas con Met.3D."""

from __future__ import annotations

import copy
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import yaml

from visualize.met3D.configuration import load_yaml_configuration, require_value
from visualize.met3D.products import prepare_product_objects, select_product_data, prepare_scene_geometry
from visualize.met3D.netcdf import prepare_visualization_data
from visualize.met3D.native import prepare_scene_appearance
from visualize.met3D.scene import write_animation_configuration
from visualize.met3D.render import open_animation, render_animation, render_frame


def prepare_animation(
    project_root: Path, animation_file: Path, netcdf_file: Path,
    for_render: bool = False, reuse_netcdf: bool = False,
    forecast_hour: float | None = None,
) -> dict:
    """Prepara una escena aislada y conserva los NoData del NetCDF estandarizado."""

    # Leer las decisiones del producto sin mezclar el YAML original con valores derivados.
    source_animation = load_yaml_configuration(animation_file, "de animación Met.3D")
    animation = copy.deepcopy(source_animation)
    product_name = str(require_value(animation, ("name",), "de animación Met.3D"))
    scene_file = project_root / str(require_value(animation, ("scene",), f"de animación {product_name}"))
    scene = load_yaml_configuration(scene_file, "de escena Met.3D")
    scene["appearance"] = prepare_scene_appearance(scene)
    product = prepare_product_objects(project_root, animation, scene, reuse_netcdf)

    # Resolver tiempos, niveles y geometría; no recorrer los valores de los campos.
    metadata, data_timeline = select_product_data(animation, scene, product, netcdf_file)
    object_bounding_boxes = prepare_scene_geometry(scene, product, product_name)
    timeline = copy.deepcopy(data_timeline)
    requested_time = None
    if forecast_hour is not None:
        trajectory = animation["camera"].get("trajectory")
        if trajectory and trajectory.get("enabled"):
            raise RuntimeError("La captura por plazo requiere una cámara fija; la órbita se verifica mediante --render.")
        matches = [time for time in timeline["valid_times"]
                   if (time - metadata["forecast_date"]).total_seconds() == forecast_hour * 3600]
        if len(matches) != 1:
            raise RuntimeError(f"{metadata['center']}-{metadata['model']}, corrida {metadata['forecast_date']}: el plazo +{forecast_hour:g} h no está en la selección nativa.")
        requested_time = matches[0]
        # El batch nativo avanza desde el primer plazo; se conserva la historia del rastro.
        timeline["valid_times"] = [time for time in timeline["valid_times"] if time <= requested_time]
        timeline["range_seconds"] = int((requested_time - timeline["valid_times"][0]).total_seconds())

    # Aislar modelos, corridas, productos y ejecuciones sin borrar escenas anteriores.
    model_identifier = f"{metadata['center']}-{metadata['model']}"
    identifiers = (model_identifier, product_name)
    if any(not re.fullmatch(r"[a-zA-Z0-9_-]+", value) for value in identifiers):
        raise RuntimeError("Los nombres de modelo y producto Met.3D sólo admiten letras, números, guion y guion bajo.")
    product_directory = (project_root / "met3D" / ".runtime" / model_identifier
                         / metadata["forecast_date"].strftime("%Y%m%d_%HZ") / product_name)
    product_directory.mkdir(parents=True, exist_ok=True)
    runtime_directory = Path(tempfile.mkdtemp(prefix="scene-", dir=product_directory))
    visualization_file = product_directory / "above_surface.nc" if animation.get("data_preparation") is not None else netcdf_file
    native_files = write_animation_configuration(
        project_root, runtime_directory, visualization_file, animation, scene, product,
        metadata, timeline, object_bounding_boxes, for_render or forecast_hour is not None,
    )

    # Generar o reutilizar los datos sólo después de validar las configuraciones nativas.
    if animation.get("data_preparation") is not None:
        if reuse_netcdf:
            prepare_visualization_data(netcdf_file, visualization_file, product["preparation_variables"],
                                       data_timeline["valid_times"], product["surface_pressure_name"], True)
        else:
            next_file = product_directory / f"preparing-{uuid.uuid4().hex}.nc"
            prepare_visualization_data(netcdf_file, next_file, product["preparation_variables"],
                                       data_timeline["valid_times"], product["surface_pressure_name"])
            next_file.replace(visualization_file)

    # Conservar las entradas exactas junto a cada escena para poder reproducirla.
    shutil.copy2(animation_file, runtime_directory / "configuration.yaml")
    shutil.copy2(scene_file, runtime_directory / "scene.yaml")
    pressure = product["objects"]["mean_sea_level_pressure"]
    if pressure is not None:
        shutil.copy2(project_root / pressure["colourmap_file"], runtime_directory / "pressure_palette.yaml")
    source_stat = netcdf_file.stat()
    evidence = {
        "status": "prepared", "source": str(netcdf_file.resolve()),
        "source_size_bytes": source_stat.st_size, "source_mtime_ns": source_stat.st_mtime_ns,
        "model": model_identifier, "forecast_date": metadata["forecast_date"].isoformat(),
        "product": product_name, "nodata_policy": "preserve",
        "appearance": {key: value for key, value in scene["appearance"].items() if not key.endswith("_variant")},
        "variables": list(dict.fromkeys(product["required_variables"])),
        "horizontal_sections": [
            {"name": section["name"], "requested_pressure_hpa": section["pressure_hpa"],
             "effective_pressure_hpa": section["effective_pressure_hpa"],
             "level_selection": section["level_selection"],
             "layers": [{"name": name, "type": layer["type"]}
                        for name, layer in section["layers"].items() if layer["enabled"] is True]}
            for section in product["objects"]["horizontal_sections"]
        ],
        "data_preparation": {
            "variables": product["preparation_variables"],
            "surface_pressure_variable": product["surface_pressure_name"],
        },
        "data_valid_times": [time.isoformat() for time in data_timeline["valid_times"]],
        "capture_valid_times": [time.isoformat() for time in timeline["valid_times"]],
        "requested_forecast_hour": forecast_hour,
        "visualization_file": str(visualization_file.resolve()), "reused_netcdf": reuse_netcdf,
    }
    (runtime_directory / "verification.yaml").write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), encoding="utf-8")
    output_directory = project_root / "outputs" / "met3d" / product_name / model_identifier
    video_file = output_directory / f"{product_name}_{model_identifier}_{metadata['forecast_date']:%Y%m%d_%HZ}.mp4"
    return {
        "animation": animation, "metadata": metadata, "timeline": timeline,
        "runtime_directory": runtime_directory, "visualization_file": visualization_file,
        "video_file": video_file, "requested_time": requested_time, "evidence": evidence,
        **native_files,
    }
