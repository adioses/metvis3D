"""Preparación manual de copias y miniaturas de publicación."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import yaml

from catalog import (CatalogError, IDENTIFIER, parse_video_name, published_file,
                     read_metadata, read_yaml, website_path)


def sha256_file(path):
    """Comparar el contenido cuando ya existe un video con el mismo nombre."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_video(path):
    """Consultar el video y detener la preparación ante contenido ilegible."""
    result = subprocess.run([
        str(Path(sys.executable).parent / "ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate:format=duration",
        "-of", "json", str(path),
    ], capture_output=True, text=True)
    if result.returncode:
        raise CatalogError(f"{path}: FFprobe no pudo leer el video: {result.stderr.strip()}")
    content = json.loads(result.stdout)
    if not content.get("streams"):
        raise CatalogError(f"{path}: FFprobe no encontró un flujo de video.")
    stream = content["streams"][0]
    playback = {"duration_seconds": float(content["format"]["duration"]),
                "width": stream["width"], "height": stream["height"],
                "codec": stream["codec_name"], "frame_rate": float(Fraction(stream["avg_frame_rate"]))}
    if any(playback[field] <= 0 for field in ("duration_seconds", "width", "height", "frame_rate")):
        raise CatalogError(f"{path}: dimensiones, duración o tasa de fotogramas no válidas.")
    return playback


def run_publication(config_path="config/publication.yaml"):
    """Buscar los videos configurados, identificar sus destinos y preparar copias e imágenes."""
    # Configuración e inventario de videos limitado al origen declarado en YAML.
    config = read_yaml(website_path(config_path))
    settings_path = website_path(config["website_config"])
    settings = read_yaml(settings_path)
    if missing := {"video_root", "collections"} - settings.keys():
        raise CatalogError(f"{settings_path.name}: faltan campos {', '.join(sorted(missing))}.")
    settings["video_root"] = website_path(settings["video_root"])
    source_root = website_path(config["source_root"])
    collection = config["collection"]
    if collection not in settings["collections"]:
        raise CatalogError(f"publication.yaml: colección no permitida: {collection}.")
    if not source_root.is_dir():
        raise CatalogError(f"No existe el directorio de origen configurado: {source_root}.")
    thumbnail = config["thumbnail"]
    if (type(thumbnail["fraction"]) not in (int, float) or not 0 < thumbnail["fraction"] < 1
            or type(thumbnail["width"]) is not int or thumbnail["width"] < 1):
        raise CatalogError("publication.yaml: la miniatura requiere fraction entre 0 y 1 y width entero positivo.")
    # Si el origen contiene la publicación, sus colecciones no se vuelven a importar.
    published_directories = [published_file(settings["video_root"], name, ".gitkeep").parent
                             for name in ("recent", "historical")]
    video_files = sorted(path for path in source_root.rglob("*.mp4")
                         if not any(path.resolve().is_relative_to(directory) for directory in published_directories))
    if not video_files:
        raise CatalogError(f"No hay videos MP4 en el origen configurado: {source_root}.")
    # Cada nombre y cada colisión se comprueban antes de crear copias.
    planned = []
    destinations = set()
    for source_path in video_files:
        relative = source_path.relative_to(source_root)
        if len(relative.parts) != 4:
            raise CatalogError(f"{relative}: se requiere software/producto/fuente/archivo.mp4.")
        software, product, source, filename = relative.parts
        mapping = config["mappings"].get(software, {}).get(product)
        if mapping is None:
            raise CatalogError(f"{relative}: falta correspondencia explícita en publication.yaml.")
        match = re.fullmatch(rf"{re.escape(product)}_({IDENTIFIER})_(\d{{8}}_\d{{2}}Z)\.mp4", filename)
        if not match or match[1] != source:
            raise CatalogError(f"{relative}: producto, fuente o fecha del nombre no coinciden con las carpetas.")
        name = f"{match[2]}__{mapping['animation']}__{mapping['scene']}__{source}__{software}.mp4"
        identification = parse_video_name(name)
        destination = published_file(settings["video_root"], collection, name)
        if source_path.resolve() == destination:
            raise CatalogError(f"{source_path}: el origen y el destino son el mismo archivo.")
        if destination in destinations:
            raise CatalogError(f"Colisión de publicación: {relative} → {destination}.")
        destinations.add(destination)
        existing_hash = None
        if destination.exists():
            existing_hash = sha256_file(destination)
            if sha256_file(source_path) != existing_hash:
                raise CatalogError(f"Contenido diferente; no se sobrescribe: {source_path} → {destination}.")
        metadata_path = published_file(settings["video_root"], collection, destination.stem + ".metadata.yaml")
        identity = {field: identification[field] for field in ("reference", "animation", "scene", "source", "software")}
        identity["collection"] = collection
        if metadata_path.exists():
            read_metadata(metadata_path, identity)
        planned.append((source_path, destination, existing_hash, metadata_path))

    # Copias sin recodificación; las herramientas multimedia pertenecen al ambiente web.
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "status": "in_progress",
              "source_root": str(source_root), "count": len(planned), "files": []}
    report_path = website_path(config["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        for source_path, destination, existing_hash, metadata_path in planned:
            record = {"source": str(source_path), "destination": str(destination)}
            if existing_hash is not None:
                record["compared_sha256"] = existing_hash
            report["files"].append(record)
            playback = inspect_video(source_path)
            seconds = thumbnail["exceptions"].get(str(source_path.relative_to(source_root)),
                                                    playback["duration_seconds"] * thumbnail["fraction"])
            if type(seconds) not in (int, float) or not 0 < seconds < playback["duration_seconds"]:
                raise CatalogError(f"{source_path}: el instante de miniatura debe estar dentro del video.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            record["copy"] = "conserved" if destination.exists() else "copied"
            if not destination.exists():
                with source_path.open("rb") as source_stream, destination.open("xb") as destination_stream:
                    shutil.copyfileobj(source_stream, destination_stream)
            image_path = published_file(settings["video_root"], collection, destination.stem + ".jpg")
            if not image_path.exists():
                temporary_image = image_path.with_suffix(".preparing.jpg")
                result = subprocess.run([
                    str(Path(sys.executable).parent / "ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                    "-ss", str(seconds), "-i", str(destination), "-frames:v", "1",
                    "-vf", f"scale={thumbnail['width']}:-2", "-q:v", "2", str(temporary_image),
                ], capture_output=True, text=True)
                if result.returncode or not temporary_image.is_file() or temporary_image.stat().st_size == 0:
                    raise CatalogError(f"{source_path}: FFmpeg no pudo extraer la miniatura: {result.stderr.strip()}")
                temporary_image.rename(image_path)
            if not metadata_path.exists():
                with metadata_path.open("x", encoding="utf-8") as stream:
                    yaml.safe_dump({"playback": playback}, stream, allow_unicode=True, sort_keys=False)
            record.update(status="prepared", playback=playback, thumbnail=str(image_path), thumbnail_seconds=seconds)
            print(f"Preparado {len(report['files'])}/{len(planned)}: {destination.name}", flush=True)
    except (CatalogError, OSError, subprocess.SubprocessError) as error:
        report.update(status="failed", error=str(error))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise CatalogError(f"Preparación detenida: {error}. Registro: {report_path}") from error
    report.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Preparación completa: {len(planned)} videos preparados. Registro: {report_path}")
    return report
