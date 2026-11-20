"""Materializa la escena Met.3D desde objetos y cajas ya definidos."""

from pathlib import Path
import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from visualize.met3D.configuration import require_value
from visualize.met3D.native import (
    render_template, prepare_runtime_session, create_camera_orbit, encode_utc_time_variant,
    update_session_settings, replace_session_array,
)


def write_animation_configuration(project_root: Path, runtime_directory: Path,
                                  visualization_file: Path, animation: dict, scene: dict,
                                  product: dict, metadata: dict, timeline: dict,
                                  object_bounding_boxes: list[dict], for_render: bool) -> dict:
    """Genera las configuraciones nativas antes de preparar los volúmenes NetCDF."""

    product_name = str(animation["name"])
    variables = product["variables"]
    derived_variable_mappings = product["derived_variable_mappings"]
    pv_render_mode = product["pv_render_mode"]
    surface_pressure = product["objects"]["surface_pressure"]
    surface_temperature = product["objects"]["surface_temperature"]
    surface_precipitation = product["objects"]["surface_precipitation"]
    surface_shading = None
    if surface_temperature is not None:
        surface_shading = {"variable_name": variables["air_temperature_2m"], "transfer_function": "T2m [K]"}
    elif surface_precipitation is not None:
        surface_shading = {"variable_name": variables["precipitation"], "transfer_function": "Precipitación acumulada [mm]"}
    potential_vorticity = product["objects"]["potential_vorticity"]
    horizontal_section = product["objects"]["horizontal_section"]
    jet = product["objects"]["jet"]
    cold_air = product["objects"]["cold_air"]
    cloud_cover = product["objects"]["cloud_cover"]
    relative_humidity = product["objects"]["relative_humidity"]
    mean_sea_level_pressure = product["objects"]["mean_sea_level_pressure"]
    streamlines = product["objects"]["streamlines"]
    time_label = product["objects"]["time_label"]
    # Renderizar configuraciones de escena, objetos y modo batch.
    template_directory = project_root / "met3D" / "templates"
    template_environment = Environment(
        loader=FileSystemLoader(template_directory),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    dataset_name = str(require_value(animation, ("dataset_name",), f"de animación {product_name}"))
    session_source_file = project_root / str(require_value(animation, ("session_file",), f"de animación {product_name}"))
    frames_directory = runtime_directory / "frames"
    frames_directory.mkdir()
    session_file = runtime_directory / f"{product_name}.session.config"
    context = {
        "dataset_name": dataset_name,
        "netcdf_directory": visualization_file.parent.resolve(),
        "netcdf_filename": visualization_file.name,
        "variables": variables,
        "scene": scene,
        "derived_variable_mappings": derived_variable_mappings,
        "object_bounding_boxes": object_bounding_boxes,
        "potential_vorticity": potential_vorticity,
        "horizontal_section": horizontal_section,
        "jet": jet,
        "cold_air": cold_air,
        "cloud_cover": cloud_cover,
        "relative_humidity": relative_humidity,
        "surface_temperature": surface_temperature,
        "surface_precipitation": surface_precipitation,
        "surface_shading": surface_shading,
        "geographic_lines": product["objects"]["geographic_lines"],
        "mean_sea_level_pressure": mean_sea_level_pressure,
        "streamlines": streamlines,
        "time_label": time_label,
        "model_name": metadata["model"].upper(),
        "initial_valid_time": encode_utc_time_variant(timeline["valid_times"][0]),
        "timeline": timeline,
        "frames_directory": frames_directory.resolve(),
        "session_file": session_file.resolve(),
        "bounding_boxes_file": (runtime_directory / "bounding_boxes.bbox.conf").resolve(),
    }

    bounding_boxes_text = template_environment.get_template("bounding_boxes.bbox.conf.j2").render(context)
    bounding_boxes_file = runtime_directory / "bounding_boxes.bbox.conf"
    bounding_boxes_file.write_text(bounding_boxes_text.rstrip() + "\n", encoding="utf-8")
    prepare_runtime_session(session_source_file, runtime_directory, frames_directory,
                            animation, for_render, timeline, bounding_boxes_text, scene)

    trajectory = animation["camera"].get("trajectory")
    camera_sequence = None
    if trajectory is not None and require_value(trajectory, ("enabled",), f"de cámara de {product_name}"):
        camera_sequence = create_camera_orbit(animation["camera"], scene, trajectory, runtime_directory / "camera_sequence.xml", product_name)
        if not for_render:
            sequence = ET.parse(camera_sequence).getroot()
            sequence_keys = sequence.findall("SequenceKey")
            sequence_lines = [
                f"CameraSequences\\sequences\\1\\name={sequence.attrib['name']}",
                f"CameraSequences\\sequences\\1\\tension={sequence.attrib['tension']}",
                f"CameraSequences\\sequences\\1\\SequenceKeys\\size={len(sequence_keys)}",
            ]
            for index, key in enumerate(sequence_keys, 1):
                for name, value in key.attrib.items():
                    property_name = "advanceTimeStep" if name == "advanceTimestep" else name
                    if name in ("advanceTimestep", "isOrthographic"):
                        value = "true" if value == "1" else "false"
                    sequence_lines.append(f"CameraSequences\\sequences\\1\\SequenceKeys\\{index}\\{property_name}={value}")
            sequence_lines.append("CameraSequences\\sequences\\size=1")
            session_text = session_file.read_text(encoding="utf-8")
            session_text = replace_session_array(session_text, "CameraSequences\\sequences\\", sequence_lines, session_source_file)
            camera_settings = {"Animation\\used_camera_sequence": 0, "Animation\\enable_camera_animation": "true"}
            if len(timeline["valid_times"]) == 1:
                camera_settings["Animation\\enable_time_animation"] = "false"
            session_text = update_session_settings(session_text, camera_settings, session_source_file)
            session_file.write_text(session_text, encoding="utf-8")
    context["camera_sequence"] = camera_sequence

    files = {
        "dataset": render_template(template_environment, "dataset.dataset.conf.j2", runtime_directory / "dataset.dataset.conf", context),
        "bounding_boxes": bounding_boxes_file,
        "basemap": render_template(template_environment, "basemap.actor.conf.j2", runtime_directory / "basemap.actor.conf", context),
        "volume": render_template(template_environment, "volume_bounding_box.actor.conf.j2", runtime_directory / "volume_bounding_box.actor.conf", context),
        "batch": render_template(template_environment, "batch_mode.batch.conf.j2", runtime_directory / "batch_mode.batch.conf", context),
    }
    if camera_sequence is not None:
        files["camera_sequence"] = camera_sequence
    actor_files = [files[name] for name in ("basemap", "volume")]
    if surface_temperature is not None:
        files["surface_temperature_colourbar"] = render_template(template_environment, "surface_temperature_colourbar.actor.conf.j2", runtime_directory / "surface_temperature_colourbar.actor.conf", context)
        files["surface_temperature_labels"] = render_template(template_environment, "surface_temperature_labels.actor.conf.j2", runtime_directory / "surface_temperature_labels.actor.conf", context)
        actor_files.extend((files["surface_temperature_colourbar"], files["surface_temperature_labels"]))
    if surface_precipitation is not None:
        files["precipitation_colourbar"] = render_template(template_environment, "precipitation_colourbar.actor.conf.j2", runtime_directory / "precipitation_colourbar.actor.conf", context)
        files["precipitation_labels"] = render_template(template_environment, "precipitation_labels.actor.conf.j2", runtime_directory / "precipitation_labels.actor.conf", context)
        actor_files.extend((files["precipitation_colourbar"], files["precipitation_labels"]))
    if surface_pressure is not None:
        files["surface_pressure"] = render_template(
            template_environment,
            "surface_pressure.actor.conf.j2",
            runtime_directory / "surface_pressure.actor.conf",
            context,
        )
        actor_files.append(files["surface_pressure"])
    if mean_sea_level_pressure is not None:
        for band in mean_sea_level_pressure["bands"]:
            name = f"mslp_colourbar_{band['index']:02d}"
            files[name] = render_template(template_environment, "mslp_colourbar.actor.conf.j2", runtime_directory / f"{name}.actor.conf", {**context, "band": band})
            actor_files.append(files[name])
        files["mslp_labels"] = render_template(template_environment, "mslp_labels.actor.conf.j2", runtime_directory / "mslp_labels.actor.conf", context)
        files["mean_sea_level_pressure"] = render_template(template_environment, "mean_sea_level_pressure.actor.conf.j2", runtime_directory / "mean_sea_level_pressure.actor.conf", context)
        actor_files.extend((files["mslp_labels"], files["mean_sea_level_pressure"]))
    if streamlines is not None:
        files["streamlines"] = render_template(template_environment, "streamlines.actor.conf.j2", runtime_directory / "streamlines.actor.conf", context)
        actor_files.append(files["streamlines"])
    if potential_vorticity is not None:
        if pv_render_mode == "dvr":
            files["pv_dvr_colourbar"] = render_template(template_environment, "pv_dvr_colourbar.actor.conf.j2", runtime_directory / "pv_dvr_colourbar.actor.conf", context)
            actor_files.append(files["pv_dvr_colourbar"])
            pv_template = "potential_vorticity_dvr.actor.conf.j2"
        else:
            context["pv_isovalue_si"] = f"{float(potential_vorticity['isosurface_pvu']) * 1e-6:.8g}"
            opacity_byte = round(float(potential_vorticity["opacity"]) * 255)
            context["pv_isosurface_colour"] = (
                f"@Variant(\\0\\0\\0\\x43\\x1\\x{opacity_byte:02x}\\x{opacity_byte:02x}"
                "\\x75\\x75\\x5f\\x5f\\xd6\\xd6\\0\\0)"
            )
            pv_template = "potential_vorticity.actor.conf.j2"
        files["potential_vorticity"] = render_template(
            template_environment,
            pv_template,
            runtime_directory / "potential_vorticity.actor.conf",
            context,
        )
        actor_files.append(files["potential_vorticity"])
    if horizontal_section is not None:
        pv = horizontal_section["potential_vorticity"]
        for key in ("minimum_pvu", "maximum_pvu", "colour_steps", "hue", "dark_luminance", "light_luminance", "chroma"):
            require_value(pv, (key,), f"de PV en la sección horizontal de {product_name}")
        if float(pv["minimum_pvu"]) >= float(pv["maximum_pvu"]):
            raise RuntimeError(f"El mínimo de PV debe ser menor que el máximo en {product_name}.")
        wind = horizontal_section["wind"]
        for key in ("spacing_degrees", "min_length_degrees", "max_length_degrees", "line_width"):
            require_value(wind, (key,), f"del viento en la sección horizontal de {product_name}")
        if horizontal_section["geopotential_height"]["enabled"]:
            for key in ("minimum_gpm", "maximum_gpm", "interval_gpm"):
                require_value(horizontal_section["geopotential_height"], (key,), f"de geopotencial en {product_name}")
        files["pv_colourbar"] = render_template(template_environment, "horizontal_pv_colourbar.actor.conf.j2", runtime_directory / "horizontal_pv_colourbar.actor.conf", context)
        files["horizontal_section"] = render_template(template_environment, "horizontal_section.actor.conf.j2", runtime_directory / "horizontal_section.actor.conf", context)
        actor_files.extend((files["pv_colourbar"], files["horizontal_section"]))
    if jet is not None:
        files["jet"] = render_template(
            template_environment,
            "jet.actor.conf.j2",
            runtime_directory / "jet.actor.conf",
            context,
        )
        actor_files.append(files["jet"])
    if cold_air is not None:
        files["cold_air_colourbar"] = render_template(template_environment, "cold_air_colourbar.actor.conf.j2", runtime_directory / "cold_air_colourbar.actor.conf", context)
        actor_files.append(files["cold_air_colourbar"])
        if relative_humidity is None:
            files["cold_air"] = render_template(template_environment, "cold_air.actor.conf.j2", runtime_directory / "cold_air.actor.conf", context)
            actor_files.append(files["cold_air"])
    if cloud_cover is not None:
        files["cloud_colourbar"] = render_template(template_environment, "cloud_colourbar.actor.conf.j2", runtime_directory / "cloud_colourbar.actor.conf", context)
        files["cloud_cover"] = render_template(template_environment, "cloud_cover.actor.conf.j2", runtime_directory / "cloud_cover.actor.conf", context)
        actor_files.extend((files["cloud_colourbar"], files["cloud_cover"]))
    if relative_humidity is not None:
        files["relative_humidity_colourbar"] = render_template(template_environment, "relative_humidity_colourbar.actor.conf.j2", runtime_directory / "relative_humidity_colourbar.actor.conf", context)
        files["relative_humidity"] = render_template(template_environment, "relative_humidity.actor.conf.j2", runtime_directory / "relative_humidity.actor.conf", context)
        actor_files.extend((files["relative_humidity_colourbar"], files["relative_humidity"]))
    if time_label is not None:
        files["time_label"] = render_template(template_environment, "time_label.actor.conf.j2", runtime_directory / "time_label.actor.conf", context)
        actor_files.append(files["time_label"])
    context["session_file"] = session_file.resolve()
    files["preferences"] = render_template(
        template_environment,
        "met3d.ini.j2",
        runtime_directory / "config" / "met3d" / "met3d.ini",
        context,
    )

    return {
        "files": files, "actor_files": actor_files, "frames_directory": frames_directory,
        "session_file": session_file, "session_source_file": session_source_file,
    }


