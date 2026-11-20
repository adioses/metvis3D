"""Ejecuta Met.3D y verifica los productos generados."""

from __future__ import annotations

import json
import math
import os
import shutil
import re
import subprocess
from pathlib import Path
from fractions import Fraction

import yaml
from PIL import Image

XVFB_SERVER_ARGUMENTS = "-screen 0 1920x1080x24 +extension GLX +render -noreset"


def met3d_environment_prefix(conda_executable: str, environment_name: str) -> Path:
    """Obtiene los recursos instalados de Met.3D en el ambiente Conda indicado."""

    try:
        result = subprocess.run(
            [conda_executable, "run", "-n", environment_name, "python", "-c", "import sys; print(sys.prefix)"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró el comando Conda: {conda_executable}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"No se pudo consultar el ambiente Conda '{environment_name}': {error.stderr}") from error

    met3d_base = Path(result.stdout.strip()) / "share" / "met3d"
    if not met3d_base.exists():
        raise RuntimeError(f"El ambiente '{environment_name}' no contiene los recursos de Met.3D: {met3d_base}")
    return met3d_base


def met3d_environment(preparation: dict[str, object], conda_executable: str, environment_name: str) -> dict[str, str]:
    """Aísla preferencias y caché de Met.3D dentro del runtime de la corrida."""

    runtime_directory = preparation["runtime_directory"]
    if not isinstance(runtime_directory, Path):
        raise RuntimeError("No se pudo localizar el runtime Met.3D preparado.")
    return {
        **os.environ,
        "MET3D_BASE": str(met3d_environment_prefix(conda_executable, environment_name)),
        "XDG_CONFIG_HOME": str(runtime_directory / "config"),
    }


def open_animation(preparation: dict[str, object], conda_executable: str, environment_name: str) -> None:
    """Abre una animación Met.3D para revisar sus objetos y cámara."""

    files = preparation["files"]
    actor_files = preparation["actor_files"]
    if not isinstance(files, dict) or not isinstance(actor_files, list):
        raise RuntimeError("No se encontraron las configuraciones de actores preparadas.")
    command = [
        conda_executable,
        "run",
        "--no-capture-output",
        "-n",
        environment_name,
        "Met3D",
        "--datasets",
        str(files["dataset"]),
        "--actors",
        ";".join(str(actor) for actor in actor_files),
    ]
    log_file = preparation["runtime_directory"] / "met3d.log"
    preparation["evidence"].update({"status": "opening", "met3d_command": command})
    save_execution_evidence(preparation)
    print(f"Met.3D: registro de la sesión en {log_file}", flush=True)
    try:
        with log_file.open("w", encoding="utf-8") as log:
            subprocess.run(command, check=True, env=met3d_environment(preparation, conda_executable, environment_name), stdout=log, stderr=subprocess.STDOUT)
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró el comando Conda: {conda_executable}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Met.3D no pudo abrir la escena de animación. Revise {log_file}.") from error
    preparation["evidence"]["status"] = "session_closed"
    save_execution_evidence(preparation)


def capture_animation_frames(preparation: dict[str, object], conda_executable: str, environment_name: str) -> list[Path]:
    """Captura PNG y comprueba plazos, orden y dimensiones de la escena."""

    session_file = preparation["session_file"]
    session_source_file = preparation["session_source_file"]
    if not isinstance(session_file, Path) or not session_file.exists():
        expected_session = session_source_file if isinstance(session_source_file, Path) else session_file
        raise RuntimeError(
            "No existe la sesión base requerida para renderizar: "
            f"{expected_session}."
        )
    files = preparation["files"]
    actor_files = preparation["actor_files"]
    animation = preparation["animation"]
    frames_directory = preparation["frames_directory"]
    video_file = preparation["video_file"]
    if not isinstance(files, dict) or not isinstance(actor_files, list) or not isinstance(animation, dict) or not isinstance(frames_directory, Path) or not isinstance(video_file, Path):
        raise RuntimeError("La preparación no contiene los archivos necesarios para renderizar.")

    met3d_command = [
        conda_executable,
        "run",
        "--no-capture-output",
        "-n",
        environment_name,
        "Met3D",
        "--datasets",
        str(files["dataset"]),
        "--actors",
        ";".join(str(actor) for actor in actor_files),
        "--batch",
        str(files["batch"]),
    ]
    command = [
        "xvfb-run",
        "-a",
        f"--server-args={XVFB_SERVER_ARGUMENTS}",
        *met3d_command,
    ]
    log_file = preparation["runtime_directory"] / "met3d.log"
    environment = met3d_environment(preparation, conda_executable, environment_name)
    preparation["evidence"].update({"met3d_command": command, "met3d_base": environment["MET3D_BASE"], "status": "capturing"})
    save_execution_evidence(preparation)
    print(f"Met.3D: registro de captura en {log_file}", flush=True)
    try:
        with log_file.open("w", encoding="utf-8") as log:
            subprocess.run(command, check=True, env=environment, stdout=log, stderr=subprocess.STDOUT)
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró un ejecutable del render Met.3D ({error.filename}); se requieren Conda y xvfb-run.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Met.3D no pudo renderizar {animation['name']}, {preparation['metadata']['center']}-{preparation['metadata']['model']}, corrida {preparation['metadata']['forecast_date']}: {error}. Revise {log_file}.") from error
    log_text = log_file.read_text(encoding="utf-8")
    if "streamlines" in files:
        for message in ("Cannot load seed point source", "Please add at least one seed point source", "Not all wind components required for the streamline computation could be loaded"):
            if message in log_text:
                raise RuntimeError(f"La animación {animation['name']} de {preparation['metadata']['center']}-{preparation['metadata']['model']}, corrida {preparation['metadata']['forecast_date']}, no pudo calcular la circulación 3D: {message}. Revise {log_file}.")

    if not list(frames_directory.glob("frame-FN*.png")):
        raise RuntimeError("Met.3D terminó sin escribir fotogramas PNG para la animación.")
    metadata = preparation["metadata"]
    timeline = preparation["timeline"]
    first_time = metadata["valid_times"][0]
    frame_names = {frame.name for frame in frames_directory.glob("frame-FN*.png")}
    if "camera_sequence" in files:
        minimum_frames = int(animation["camera"]["trajectory"]["minimum_frames"])
        if len(frame_names) < minimum_frames or len(frame_names) not in (timeline["frame_count"] - 1, timeline["frame_count"], timeline["frame_count"] + 1):
            raise RuntimeError(f"La trayectoria de {animation['name']} esperaba aproximadamente {timeline['frame_count']} fotogramas y Met.3D generó {len(frame_names)}.")
    selected_timestamps = set()
    for valid_time in metadata["valid_times"]:
        if (valid_time - first_time).total_seconds() > timeline["range_seconds"]:
            break
        timestamp = valid_time.strftime("%Y-%m-%dT%H%M%SZ")
        selected_timestamps.add(timestamp)
        if not any(name.endswith(f"-{timestamp}.png") for name in frame_names):
            raise RuntimeError(
                f"La animación {animation['name']} de {metadata['center']}-{metadata['model']} "
                f"no generó fotogramas para el plazo {valid_time}; revise la sincronización de cámara y tiempo."
            )
        if "camera_sequence" not in files and sum(name.endswith(f"-{timestamp}.png") for name in frame_names) != 1:
            raise RuntimeError(f"La animación {animation['name']} requiere un fotograma para el plazo {valid_time}.")
    for frame_name in frame_names:
        match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)\.png$", frame_name)
        timestamp = match.group(1) if match else ""
        if timestamp not in selected_timestamps:
            raise RuntimeError(f"La animación {animation['name']} generó un fotograma fuera de los plazos seleccionados: {frame_name}.")
    for index, frame_name in enumerate(sorted(frame_names)):
        time_index = min(index // timeline["frames_per_interval"], len(timeline["valid_times"]) - 1) if "camera_sequence" in files else index
        expected_time = timeline["valid_times"][time_index].strftime("%Y-%m-%dT%H%M%SZ")
        if not frame_name.endswith(f"-{expected_time}.png"):
            raise RuntimeError(f"La animación {animation['name']} no sincronizó el fotograma {frame_name} con el plazo {expected_time}.")
    frames = [frames_directory / name for name in sorted(frame_names)]
    expected_size = (int(animation["output"]["width_px"]), int(animation["output"]["height_px"]))
    for frame in frames:
        with Image.open(frame) as image:
            if image.size != expected_size:
                raise RuntimeError(f"El fotograma {frame.name} tiene dimensiones {image.size}; se esperaban {expected_size}.")
            image.verify()
    preparation["evidence"].update({"status": "frames_verified", "frames": [frame.name for frame in frames], "frame_count": len(frames), "width_px": expected_size[0], "height_px": expected_size[1]})
    save_execution_evidence(preparation)
    return frames


def save_execution_evidence(preparation: dict, product_file: Path | None = None) -> None:
    """Registra comprobaciones y adjunta las configuraciones exactas al producto."""

    runtime_directory = preparation["runtime_directory"]
    evidence = preparation["evidence"]
    if product_file is not None:
        evidence["product_file"] = str(product_file.resolve())
    verification_file = runtime_directory / "verification.yaml"
    verification_file.write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if product_file is not None:
        verification_file = product_file.with_suffix(".verification.yaml")
        verification_file.write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), encoding="utf-8")
        for name in ("configuration.yaml", "scene.yaml", "pressure_palette.yaml", "met3d.log", "ffmpeg.log", "ffprobe.json"):
            source = runtime_directory / name
            if source.exists():
                shutil.copy2(source, product_file.with_suffix("." + name))


def render_frame(preparation: dict, conda_executable: str, environment_name: str) -> Path:
    """Exporta el plazo nativo solicitado y conserva la historia interna usada por el rastro."""

    requested_time = preparation["requested_time"]
    if requested_time is None:
        raise RuntimeError("La captura de un fotograma requiere indicar --frame-hour con un plazo nativo.")
    frames = capture_animation_frames(preparation, conda_executable, environment_name)
    timestamp = requested_time.strftime("%Y-%m-%dT%H%M%SZ")
    selected = [frame for frame in frames if frame.name.endswith(f"-{timestamp}.png")]
    if len(selected) != 1:
        raise RuntimeError(f"La captura requiere exactamente un fotograma para {requested_time}; se obtuvieron {len(selected)}.")
    frame_file = preparation["video_file"].with_name(preparation["video_file"].stem + f"_frame_{requested_time:%Y%m%d_%H%MZ}.png")
    frame_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected[0], frame_file)
    preparation["evidence"].update({"status": "frame_verified", "selected_frame": selected[0].name})
    save_execution_evidence(preparation, frame_file)
    return frame_file


def render_animation(preparation: dict, conda_executable: str, environment_name: str) -> Path:
    """Captura los plazos nativos y publica el MP4 sólo después de verificarlo con FFprobe."""

    frames = capture_animation_frames(preparation, conda_executable, environment_name)
    output = preparation["animation"]["output"]
    video_file = preparation["video_file"]
    runtime_directory = preparation["runtime_directory"]
    next_video = runtime_directory / "video.mp4"
    ffmpeg_command = [
        "ffmpeg", "-y", "-framerate", str(output["frames_per_second"]),
        "-pattern_type", "glob", "-i", str(preparation["frames_directory"] / "frame-FN*.png"),
        "-vf", f"scale={output['width_px']}:{output['height_px']}:flags=lanczos",
        "-c:v", str(output["video_codec"]), "-pix_fmt", str(output["pixel_format"]), str(next_video),
    ]
    ffprobe_command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                       "-show_streams", "-show_format", "-of", "json", str(next_video)]
    try:
        with (runtime_directory / "ffmpeg.log").open("w", encoding="utf-8") as log:
            subprocess.run(ffmpeg_command, check=True, stdout=log, stderr=subprocess.STDOUT)
        result = subprocess.run(ffprobe_command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError(f"No se encontró {error.filename}; se requieren FFmpeg y FFprobe para verificar el video.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"No se pudo codificar o verificar el video {video_file.name}: {error}. Revise {runtime_directory / 'ffmpeg.log'}.") from error
    (runtime_directory / "ffprobe.json").write_text(result.stdout, encoding="utf-8")
    video_metadata = json.loads(result.stdout)
    if len(video_metadata["streams"]) != 1:
        raise RuntimeError(f"FFprobe no encontró una única pista de video en {next_video}.")
    stream = video_metadata["streams"][0]
    expected_fps = Fraction(str(output["frames_per_second"]))
    expected_duration = len(frames) / float(expected_fps)
    if (int(stream["width"]) != int(output["width_px"])
            or int(stream["height"]) != int(output["height_px"])
            or Fraction(stream["avg_frame_rate"]) != expected_fps
            or int(stream["nb_read_frames"]) != len(frames)
            or stream["pix_fmt"] != output["pixel_format"]
            or not math.isclose(float(stream["duration"]), expected_duration, abs_tol=0.001)):
        raise RuntimeError(f"FFprobe detectó dimensiones, frecuencia, número de fotogramas, formato de píxel o duración distintos a lo solicitado. Revise {runtime_directory / 'ffprobe.json'}.")
    video_file.parent.mkdir(parents=True, exist_ok=True)
    # Copiar desde el runtime también permite que outputs resida en otro sistema de archivos.
    next_output = video_file.with_name(video_file.stem + f".{runtime_directory.name}.preparing.mp4")
    shutil.copy2(next_video, next_output)
    next_output.replace(video_file)
    preparation["evidence"].update({
        "status": "video_verified", "ffmpeg_command": ffmpeg_command, "ffprobe_command": ffprobe_command,
        "video": {key: stream[key] for key in ("width", "height", "codec_name", "pix_fmt", "avg_frame_rate", "nb_read_frames", "duration")},
    })
    save_execution_evidence(preparation, video_file)
    return video_file
