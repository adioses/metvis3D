"""Lectura del catálogo publicado, sin ejecutar herramientas multimedia."""

import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

WEBSITE_ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = r"[a-z0-9]+(?:[-_][a-z0-9]+)*"
VIDEO_NAME = re.compile(
    rf"(?P<reference>\d{{8}}_\d{{2}}Z)__(?P<animation>{IDENTIFIER})__"
    rf"(?P<scene>{IDENTIFIER})__(?P<source>{IDENTIFIER})__(?P<software>{IDENTIFIER})\.mp4"
)


class CatalogError(ValueError):
    """Dato publicado o configuración que impide construir un catálogo completo."""


def read_yaml(path):
    """Leer un mapa YAML e indicar el archivo ante errores de lectura o formato."""
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as stream:
            content = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise CatalogError(f"No se pudo leer {path.name}: {error}") from error
    if not isinstance(content, dict):
        raise CatalogError(f"{path.name}: se requiere un mapa YAML.")
    return content


def website_path(value):
    """Resolver rutas operativas respecto de website/, nunca del directorio actual."""
    path = Path(value)
    return (WEBSITE_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def read_website_config(config_path=None):
    config_path = website_path(config_path or os.environ.get(
        "METVIS3D_WEBSITE_CONFIG", "config/website.yaml"
    ))
    settings = read_yaml(config_path)
    required = {"title", "video_root", "catalog", "collections", "server", "url_prefix",
                "demonstration", "playback"}
    if missing := required - settings.keys():
        raise CatalogError(f"{config_path.name}: faltan campos {', '.join(sorted(missing))}.")
    if not isinstance(settings["collections"], dict) or set(settings["collections"]) != {"recent", "historical"}:
        raise CatalogError(f"{config_path.name}: las colecciones deben ser recent y historical.")
    prefix = settings["url_prefix"]
    if not isinstance(prefix, str) or (prefix and not re.fullmatch(r"(?:/[a-zA-Z0-9_-]+)+", prefix)):
        raise CatalogError(f"{config_path.name}: url_prefix debe ser vacío o /prefijo sin barra final.")
    if not isinstance(settings["demonstration"], bool):
        raise CatalogError(f"{config_path.name}: demonstration debe ser booleano.")
    for field in ("title", "video_root", "catalog"):
        if not isinstance(settings[field], str) or not settings[field]:
            raise CatalogError(f"{config_path.name}: {field} requiere texto no vacío.")
    playback = settings["playback"]
    if (not isinstance(playback, dict) or not isinstance(playback.get("speeds"), list)
            or not playback["speeds"]
            or any(type(speed) not in (int, float) or not math.isfinite(speed) or speed <= 0
                   for speed in playback["speeds"])
            or playback.get("initial_speed") not in playback["speeds"]
            or not isinstance(playback.get("loop"), bool)):
        raise CatalogError(f"{config_path.name}: revisar velocidades y repetición de playback.")
    settings["video_root"] = website_path(settings["video_root"])
    settings["catalog"] = website_path(settings["catalog"])
    return settings


def parse_video_name(filename):
    """Obtener la identificación meteorológica y validar fecha y ciclo UTC."""
    match = VIDEO_NAME.fullmatch(filename)
    if not match:
        raise CatalogError(
            f"{filename}: se requiere YYYYMMDD_HHZ__animation__scene__center-model__software.mp4 "
            "con identificadores ASCII en minúsculas y separadores simples."
        )
    fields = match.groupdict()
    try:
        reference = datetime.strptime(fields["reference"], "%Y%m%d_%HZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise CatalogError(f"{filename}: fecha u hora UTC inválida: {error}") from error
    if "-" not in fields["source"]:
        raise CatalogError(f"{filename}: source debe identificar centro-modelo o centro-conjunto.")
    fields["date"] = reference.strftime("%Y-%m-%d")
    fields["cycle"] = reference.strftime("%H")
    fields["reference_utc"] = reference.isoformat().replace("+00:00", "Z")
    return fields


def published_file(video_root, collection, filename):
    """Impedir entregas fuera de la colección, incluidas rutas mediante enlaces."""
    if collection not in ("recent", "historical") or Path(filename).name != filename:
        raise CatalogError("Colección o nombre de archivo no permitido.")
    directory = (video_root / collection).resolve()
    if not directory.is_relative_to(video_root.resolve()):
        raise CatalogError(f"{collection}: la colección resuelta está fuera de la raíz de publicación.")
    path = (directory / filename).resolve()
    if not path.is_relative_to(directory) or path.parent != directory:
        raise CatalogError(f"{collection}/{filename}: destino fuera de la colección.")
    return path


def read_metadata(path, identification):
    """Comprobar información opcional sin inventar variables ni plazos."""
    data = read_yaml(path)
    allowed = set(identification) | {"variables", "period", "notes", "playback"}
    if unknown := data.keys() - allowed:
        raise CatalogError(f"{path.name}: campos no reconocidos: {', '.join(sorted(unknown))}.")
    for field, value in identification.items():
        if field in data and data[field] != value:
            raise CatalogError(f"{path.name}: {field} contradice el nombre del MP4 o su colección.")
    if "notes" in data and not isinstance(data["notes"], str):
        raise CatalogError(f"{path.name}: notes debe ser texto.")
    if "variables" in data:
        variables = data["variables"]
        if not isinstance(variables, list):
            raise CatalogError(f"{path.name}: variables debe ser una lista.")
        for variable in variables:
            if (not isinstance(variable, dict) or not variable.get("name")
                    or variable.keys() - {"name", "title", "units"}
                    or any(not isinstance(value, str) for value in variable.values())):
                raise CatalogError(f"{path.name}: cada variable requiere name y admite title y units como texto.")
    if "period" in data:
        period = data["period"]
        if not isinstance(period, dict) or set(period) != {"start", "end"}:
            raise CatalogError(f"{path.name}: period requiere start y end con tiempos UTC explícitos.")
        times = []
        for field in ("start", "end"):
            try:
                value = datetime.fromisoformat(str(period[field]).replace("Z", "+00:00"))
            except ValueError as error:
                raise CatalogError(f"{path.name}: period.{field} inválido: {error}") from error
            if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
                raise CatalogError(f"{path.name}: period.{field} debe declarar UTC.")
            times.append(value)
        if times[1] < times[0]:
            raise CatalogError(f"{path.name}: period.end es anterior a period.start.")
    if "playback" in data:
        playback = data["playback"]
        allowed_playback = {"duration_seconds", "width", "height", "codec", "frame_rate"}
        if not isinstance(playback, dict) or playback.keys() - allowed_playback:
            raise CatalogError(f"{path.name}: campos de playback inválidos.")
        for field, value in playback.items():
            if field == "codec":
                valid = isinstance(value, str) and bool(value)
            else:
                valid = type(value) in (int, float) and math.isfinite(value) and value > 0
            if not valid:
                raise CatalogError(f"{path.name}: playback.{field} inválido.")
    return {field: data[field] for field in ("variables", "period", "notes", "playback") if field in data}


def read_catalog(settings):
    """Leer configuración, revisar las colecciones y construir el catálogo completo."""
    # Enriquecimiento descriptivo independiente de los identificadores publicados.
    descriptions = read_yaml(settings["catalog"])
    categories = {"animations", "scenes", "sources", "software"}
    if descriptions.keys() - categories:
        raise CatalogError("catalog.yaml: se admiten animations, scenes, sources y software.")
    for category in categories:
        entries = descriptions.get(category, {})
        if not isinstance(entries, dict):
            raise CatalogError(f"catalog.yaml: {category} debe ser un mapa por identificador.")
        for identifier, entry in entries.items():
            if not isinstance(identifier, str) or not re.fullmatch(IDENTIFIER, identifier) or not isinstance(entry, dict):
                raise CatalogError(f"catalog.yaml: entrada inválida en {category}: {identifier}.")
            if entry.keys() - {"title", "description", "order", "kind"}:
                raise CatalogError(f"catalog.yaml: campos inválidos en {category}/{identifier}.")
            for field in ("title", "description"):
                if field in entry and not isinstance(entry[field], str):
                    raise CatalogError(f"catalog.yaml: {category}/{identifier}/{field} debe ser texto.")
            if "order" in entry and type(entry["order"]) is not int:
                raise CatalogError(f"catalog.yaml: order inválido en {category}/{identifier}.")
            if "kind" in entry and (category != "sources" or entry["kind"] not in ("forecast", "reanalysis")):
                raise CatalogError(f"catalog.yaml: kind inválido en {category}/{identifier}.")

    # La raíz ausente es un error; una colección todavía ausente es válida.
    video_root = settings["video_root"]
    if not video_root.is_dir():
        raise CatalogError("La raíz de publicación configurada no existe o no es un directorio accesible.")
    try:
        list(video_root.iterdir())
        videos = []
        for collection in settings["collections"]:
            directory = published_file(video_root, collection, ".gitkeep").parent
            if not directory.exists():
                continue
            for path in sorted(directory.iterdir()):
                if path.suffix.lower() != ".mp4":
                    continue
                video_path = published_file(video_root, collection, path.name)
                if not video_path.is_file():
                    raise CatalogError(f"{collection}/{path.name}: no es un MP4 regular accesible.")
                fields = parse_video_name(path.name)
                identification = {key: fields[key] for key in ("reference", "animation", "scene", "source", "software")}
                identification["collection"] = collection
                metadata_path = published_file(video_root, collection, f"{path.stem}.metadata.yaml")
                metadata = read_metadata(metadata_path, identification) if metadata_path.exists() else {}
                thumbnail_path = published_file(video_root, collection, f"{path.stem}.jpg")
                entry = {"id": f"{collection}/{path.name}", "filename": path.name, "collection": collection,
                         **fields, "metadata": metadata, "has_thumbnail": thumbnail_path.is_file()}
                for field, category in (("animation", "animations"), ("scene", "scenes"),
                                        ("source", "sources"), ("software", "software")):
                    entry[f"{field}_info"] = {"title": fields[field], **descriptions.get(category, {}).get(fields[field], {})}
                entry["reference_label"] = "Corrida" if entry["source_info"].get("kind") == "forecast" else "Fecha de referencia"
                videos.append(entry)
    except OSError as error:
        raise CatalogError(f"No se pudo revisar la publicación: {error}") from error

    # UTC y nombres físicos definen la identidad; ninguna fecha se reclasifica.
    videos.sort(key=lambda video: (video["reference"], video["filename"]), reverse=True)
    return videos
