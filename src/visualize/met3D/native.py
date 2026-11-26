"""Genera sesiones, cámaras y valores Qt nativos de Met.3D."""

from __future__ import annotations

import math
import re
import struct
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from jinja2 import Environment

from visualize.met3D.configuration import require_value


def encode_qrectf_variant(west: float, south: float, width: float, height: float) -> str:
    """Serializa un QRectF para QSettings sin exponer su codificación en YAML."""

    encoded_rectangle = struct.pack(">I4d", 20, float(west), float(south), float(width), float(height))
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_rectangle)
    return f"@Variant({escaped_bytes})"


def encode_text_position_variant(x: float, y: float) -> str:
    """Serializa la posición de una etiqueta fija en pantalla como QPointF."""

    encoded_position = struct.pack(">I2d", 26, x, y)
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_position)
    return f"@Variant({escaped_bytes})"


def encode_text_colour_variant(rgba: list[int], description: str) -> str:
    """Serializa color y transparencia de objetos y etiquetas como QColor."""

    if not isinstance(rgba, list) or len(rgba) != 4 or any(type(value) is not int or not 0 <= value <= 255 for value in rgba):
        raise RuntimeError(f"{description}: el color requiere cuatro enteros RGBA entre 0 y 255.")
    red, green, blue, alpha = (value * 257 for value in rgba)
    encoded_colour = struct.pack(">IB5H", 67, 1, alpha, red, green, blue, 0)
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_colour)
    return f"@Variant({escaped_bytes})"


def prepare_scene_appearance(scene: dict) -> dict:
    """Convierte los colores de la escena a los valores nativos de sesión y actores."""

    description = f"de apariencia de la escena {scene['name']}"
    appearance = require_value(scene, ("appearance",), description)
    if not isinstance(appearance, dict):
        raise RuntimeError(f"La apariencia de {scene['name']} debe ser un mapa YAML.")
    for key in ("background_colour", "text_colour", "frame_colour"):
        colour = require_value(appearance, (key,), description)
        if not isinstance(colour, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", colour) is None:
            raise RuntimeError(f"La escena {scene['name']} requiere appearance.{key} como HEX #RRGGBB.")
        rgb = [int(colour[index:index + 2], 16) for index in (1, 3, 5)]
        appearance[f"{key}_variant"] = encode_text_colour_variant([*rgb, 255], description)
    appearance["label_background_colour_variant"] = encode_text_colour_variant(
        require_value(appearance, ("label_background_colour",), description), description,
    )
    colour = require_value(scene, ("basemap", "line_colour"), description)
    if not isinstance(colour, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", colour) is None:
        raise RuntimeError(f"La escena {scene['name']} requiere basemap.line_colour como HEX #RRGGBB.")
    rgb = [int(colour[index:index + 2], 16) for index in (1, 3, 5)]
    scene["basemap"]["line_colour_variant"] = encode_text_colour_variant([*rgb, 255], description)
    return appearance


def encode_saved_views_variant(number_of_views: int) -> str:
    """Serializa los índices de vistas que Met.3D debe capturar en batch."""

    if number_of_views < 1:
        raise RuntimeError("La sesión base no contiene vistas para capturar.")
    encoded_views = struct.pack(">II", 9, number_of_views)
    encoded_views += b"".join(struct.pack(">II", 2, view_index) for view_index in range(number_of_views))
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_views)
    return f"@Variant({escaped_bytes})"


def encode_uuid_variant(identifier: uuid.UUID) -> str:
    """Serializa un identificador estable de variable para las plantillas nativas de Qt."""

    encoded_uuid = struct.pack(">II", 127, 6) + b"QUuid\0" + identifier.bytes
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_uuid)
    return f"@Variant({escaped_bytes})"


def encode_utc_time_variant(valid_time: datetime) -> str:
    """Serializa el tiempo válido UTC para la sesión nativa de Met.3D."""

    julian_day = valid_time.toordinal() + 1721425
    milliseconds = ((valid_time.hour * 60 + valid_time.minute) * 60 + valid_time.second) * 1000 + valid_time.microsecond // 1000
    encoded_time = struct.pack(">IQIB", 16, julian_day, milliseconds, 1)
    escaped_bytes = "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in encoded_time)
    return f"@DateTime({escaped_bytes})"


def render_template(template_environment: Environment, template_name: str, output_file: Path, context: dict) -> Path:
    """Genera una configuración nativa de Met.3D desde una plantilla Jinja."""

    rendered = template_environment.get_template(template_name).render(context)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(f"{rendered.rstrip()}\n", encoding="utf-8")
    return output_file


def create_camera_orbit(camera: dict, scene: dict, trajectory: dict, sequence_file: Path, product_name: str) -> Path:
    """Construye una órbita de cámara alrededor del centro de la escena."""

    orbit = trajectory
    zoom = float(require_value(orbit, ("zoom_factor",), f"de cámara de {product_name}"))
    zoom_fraction = float(require_value(orbit, ("zoom_fraction",), f"de cámara de {product_name}"))
    end_hold_fraction = float(require_value(orbit, ("end_hold_fraction",), f"de cámara de {product_name}"))
    tension = float(require_value(orbit, ("tension",), f"de cámara de {product_name}"))
    target_z = float(require_value(orbit, ("target_world_z",), f"de cámara de {product_name}"))
    if not 0 < zoom <= 1 or not 0 < zoom_fraction < 1 or not 0 < end_hold_fraction < 1 or not -1 <= tension <= 1:
        raise RuntimeError(f"La órbita de {product_name} requiere zoom_factor en (0, 1], zoom_fraction y end_hold_fraction en (0, 1), y tension entre -1 y 1.")
    origin = camera["origin"]
    y_axis = camera["y_axis"]
    z_axis = camera["z_axis"]
    center_lon = (float(scene["area"]["west"]) + float(scene["area"]["east"])) / 2
    center_lat = (float(scene["area"]["south"]) + float(scene["area"]["north"])) / 2
    offset_lon = float(origin["longitude"]) - center_lon
    offset_lat = float(origin["latitude"]) - center_lat
    yaw = math.degrees(math.atan2(-float(z_axis["longitude"]), float(z_axis["latitude"])))
    pitch = math.degrees(math.atan2(float(y_axis["world_z"]), -float(z_axis["world_z"])))
    target_yaw = math.degrees(math.atan2(offset_lon, -offset_lat))
    yaw_difference = (target_yaw - yaw + 180) % 360 - 180
    target_pitch = math.degrees(math.atan2(float(origin["world_z"]) - target_z, math.hypot(offset_lon, offset_lat)))
    yaw_radians = math.radians(yaw)
    roll = math.degrees(math.atan2(
        float(y_axis["longitude"]) * math.cos(yaw_radians) + float(y_axis["latitude"]) * math.sin(yaw_radians),
        math.hypot(float(y_axis["world_z"]), float(z_axis["world_z"])),
    ))
    sequence = ET.Element("CameraSequence", name=f"{product_name} orbit", tension=str(tension))
    # Los puntos definen la curva; los plazos y fotogramas se sincronizan aparte.
    intervals = int(require_value(orbit, ("keyframes",), f"de cámara de {product_name}")) - 1
    if intervals < 4:
        raise RuntimeError(f"La órbita de {product_name} requiere al menos cinco posiciones de cámara.")
    for index in range(intervals + 1):
        # Mantener la vista final permite completar el giro antes de que Met.3D detenga la captura.
        progress = min(index / intervals / (1 - end_hold_fraction), 1.0)
        angle = 2 * math.pi * max(0.0, (progress - zoom_fraction) / (1 - zoom_fraction))
        zoom_progress = min(1.0, progress / zoom_fraction)
        scale = 1 - (1 - zoom) * zoom_progress
        lon = center_lon + scale * (offset_lon * math.cos(angle) - offset_lat * math.sin(angle))
        lat = center_lat + scale * (offset_lon * math.sin(angle) + offset_lat * math.cos(angle))
        z = target_z + scale * (float(origin["world_z"]) - target_z)
        ET.SubElement(sequence, "SequenceKey", {
            "label": str(index), "lon": str(lon), "lat": str(lat), "z": str(z),
            "pitch": str(pitch + (target_pitch - pitch) * zoom_progress),
            "yaw": str(yaw + yaw_difference * zoom_progress + math.degrees(angle)),
            "roll": str(roll * (1 - zoom_progress)),
            "advanceTimestep": "0", "isOrthographic": "0", "transition": "1",
        })
    ET.indent(sequence, space="  ")
    sequence_file.write_text('<!DOCTYPE CameraSequence>\n' + ET.tostring(sequence, encoding="unicode") + '\n', encoding="utf-8")
    return sequence_file


def update_session_settings(session_text: str, settings: dict, source: Path) -> str:
    """Actualiza claves nativas y exige que cada ajuste exista en la sesión base."""

    lines = session_text.splitlines()
    found = set()
    for index, line in enumerate(lines):
        key, separator, value = line.partition("=")
        if separator and key in settings:
            lines[index] = f"{key}={settings[key]}"
            found.add(key)
    missing = settings.keys() - found
    if missing:
        raise RuntimeError(f"La sesión base {source.name} no contiene: {', '.join(sorted(missing))}.")
    return "\n".join(lines) + "\n"


def replace_session_array(session_text: str, prefix: str, entries: list[str], source: Path) -> str:
    """Sustituye una colección nativa por sus claves, independientemente de su tamaño previo."""

    lines = session_text.splitlines()
    size_key = prefix + "size="
    if not any(line.startswith(size_key) for line in lines):
        raise RuntimeError(f"La sesión base {source.name} no contiene {prefix}size.")
    result = []
    inserted = False
    for line in lines:
        if line.startswith(prefix):
            if not inserted:
                result.extend(entries)
                inserted = True
        else:
            result.append(line)
    return "\n".join(result) + "\n"


def prepare_runtime_session(
    session_source_file: Path, runtime_directory: Path, frames_directory: Path,
    animation: dict, for_render: bool, timeline: dict, bounding_boxes_text: str, scene: dict,
) -> Path:
    """Aplica cámara, tiempos y las mismas cajas utilizadas por las preferencias."""

    if not session_source_file.is_file():
        raise RuntimeError(f"No existe la sesión base: {session_source_file}.")

    animation_name = str(require_value(animation, ("name",), "de animación Met.3D"))
    runtime_session_file = runtime_directory / f"{animation_name}.session.config"

    camera = require_value(animation, ("camera",), f"de animación {animation_name}")
    output = require_value(animation, ("output",), f"de animación {animation_name}")
    if not isinstance(camera, dict) or not isinstance(output, dict):
        raise RuntimeError(f"La cámara y la salida de {animation_name} deben ser mapas YAML.")

    session_settings = {
        "MSceneViews\\MSceneView_0\\background_colour": scene["appearance"]["background_colour_variant"],
        "MSceneViews\\MSceneView_0\\MCamera\\origin_lon": require_value(camera, ("origin", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\origin_lat": require_value(camera, ("origin", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\origin_worldZ": require_value(camera, ("origin", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_lon": require_value(camera, ("y_axis", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_lat": require_value(camera, ("y_axis", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\yAxis_worldZ": require_value(camera, ("y_axis", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_lon": require_value(camera, ("z_axis", "longitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_lat": require_value(camera, ("z_axis", "latitude"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\MCamera\\zAxis_worldZ": require_value(camera, ("z_axis", "world_z"), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\custom_resolution_width": require_value(output, ("width_px",), f"de animación {animation_name}"),
        "MSceneViews\\MSceneView_0\\custom_resolution_height": require_value(output, ("height_px",), f"de animación {animation_name}"),
        "Animation\\save_directory": frames_directory.resolve(),
        "Animation\\enable_camera_animation": "false",
        "Animation\\enable_time_animation": "true",
        "TimeControls\\2\\TimeControl\\time": encode_utc_time_variant(timeline["valid_times"][0]),
        "TimeControls\\2\\TimeControl\\time_dimensions\\size": 1,
        "Animation\\from_time": encode_utc_time_variant(timeline["valid_times"][0]),
        "Animation\\to_time": encode_utc_time_variant(timeline["valid_times"][-1]),
    }
    trajectory = camera.get("trajectory")
    if timeline["step_seconds"] is not None:
        session_settings["Animation\\time_step"] = timeline["step_seconds"]
        session_settings["Animation\\time_step_unit"] = 0
    if trajectory and trajectory.get("enabled"):
        session_settings["Animation\\enable_camera_animation"] = "true"
        session_settings["Animation\\cam_runtime_seconds"] = timeline["camera_runtime_seconds"]
        session_settings["Animation\\delay_ms"] = 1000
        session_settings["Animation\\advance_type"] = 0
        session_settings["Animation\\advance_interval"] = timeline["frames_per_interval"]

    session_text = session_source_file.read_text(encoding="utf-8")
    session_settings["Animation\\save_images"] = str(for_render).lower()
    if for_render:
        views = [line.partition("=")[2] for line in session_text.splitlines()
                 if line.startswith("MSceneViews\\numSceneViews=")]
        if len(views) != 1:
            raise RuntimeError(f"La sesión base {session_source_file.name} no declara sus vistas de escena.")
        session_settings["Animation\\saved_views"] = encode_saved_views_variant(int(views[0]))
    session_text = update_session_settings(session_text, session_settings, session_source_file)
    # La plantilla de cajas es la única fuente tanto para la sesión como para las preferencias.
    box_lines = ["BoundingBoxes\\" + line for line in bounding_boxes_text.splitlines()
                 if line.startswith("boundingBox\\")]
    session_text = replace_session_array(session_text, "BoundingBoxes\\boundingBox\\", box_lines, session_source_file)
    runtime_session_file.write_text(session_text, encoding="utf-8")
    return runtime_session_file
