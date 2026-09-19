"""Genera inventarios reproducibles de fuentes GRIB2 en exploración."""

import argparse
import collections
import datetime
import glob
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pygrib
import yaml


def run_wgrib2(command: list[str]) -> str:
    """Ejecuta WGRIB2 y devuelve su salida; ante un fallo detiene el diagnóstico."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or str(error)
        raise RuntimeError(f"WGRIB2 no pudo generar el inventario: {detail}") from error
    return result.stdout


def read_wgrib2_configuration(grib_file: str) -> str:
    """Lee la configuración; WGRIB2 finaliza esta consulta con código 8."""
    result = subprocess.run(
        ["wgrib2", grib_file, "-config"], capture_output=True, text=True, check=False
    )
    if not result.stdout.strip():
        detail = result.stderr.strip() or str(result.returncode)
        raise RuntimeError(f"WGRIB2 no devolvió su configuración: {detail}")
    return result.stdout


def forecast_hour_from_name(grib_file: Path) -> int:
    """Obtiene el plazo desde los nombres conocidos de las dos fuentes exploradas."""
    match = re.search(r"(?:\.f(\d{3})$|-(\d{3})h-oper)", grib_file.name)
    if match is None:
        raise RuntimeError(f"No se pudo obtener el plazo del archivo {grib_file.name}.")
    return int(match.group(1) or match.group(2))


def message_signature(message) -> tuple:
    """Describe un mensaje por sus propiedades meteorológicas, sin usar su posición."""
    return (
        message.discipline,
        message.parameterCategory,
        message.parameterNumber,
        message.typeOfLevel,
        message.level,
        message.stepType,
        message.stepRange,
        message.productDefinitionTemplateNumber,
    )


def source_metadata(message) -> tuple:
    """Recoge la procedencia GRIB necesaria para evaluar la fuente."""
    return (
        message.centre,
        message.centreDescription,
        message.subCentre,
        message.tablesVersion,
        message.localTablesVersion,
        message.productionStatusOfProcessedData,
        message.typeOfProcessedData,
        message.typeOfGeneratingProcess,
        message.generatingProcessIdentifier,
    )


def grid_metadata(message) -> tuple:
    """Recoge los atributos que definen la malla y su orden de escaneo."""
    return (
        message.gridDefinitionTemplateNumber,
        message["Ni"],
        message["Nj"],
        message.iDirectionIncrementInDegrees,
        message.jDirectionIncrementInDegrees,
        message.latitudeOfFirstGridPointInDegrees,
        message.longitudeOfFirstGridPointInDegrees,
        message.latitudeOfLastGridPointInDegrees,
        message.longitudeOfLastGridPointInDegrees,
        message.scanningMode,
    )


def ncep_inventory_variables(grib_file: Path) -> set[str]:
    """Obtiene las etiquetas variables que WGRIB2 entrega con la convención NCEP."""
    output = run_wgrib2(
        [
            "wgrib2",
            str(grib_file),
            "-names",
            "ncep",
            "-VT",
            "-var",
            "-lev0",
            "-ftime",
            "-s",
        ]
    )
    variables = set()
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) < 6:
            raise RuntimeError(f"Inventario WGRIB2 inesperado en {grib_file.name}: {line}")
        variables.add(parts[3])
    return variables


def read_grib_metadata(grib_file: Path) -> tuple:
    """Lee los metadatos de un archivo con PyGRIB sin solicitar sus valores."""
    field_catalogue = collections.defaultdict(lambda: {"count": 0, "levels": set(), "steps": set()})
    origin_catalogue = collections.Counter()
    grid_catalogue = collections.Counter()
    with pygrib.open(str(grib_file)) as messages:
        rows = list(messages)
    if not rows:
        raise RuntimeError(f"El archivo {grib_file.name} no contiene mensajes GRIB.")

    for message in rows:
        origin_catalogue[source_metadata(message)] += 1
        grid_catalogue[grid_metadata(message)] += 1
        key = (
            message.discipline,
            message.parameterCategory,
            message.parameterNumber,
            message.shortName,
            message.name,
            message.units,
            message.typeOfLevel,
            message.stepType,
            message.productDefinitionTemplateNumber,
        )
        field_catalogue[key]["count"] += 1
        field_catalogue[key]["levels"].add(message.level)
        field_catalogue[key]["steps"].add((message.startStep, message.endStep, message.stepRange))
    return len(rows), origin_catalogue, grid_catalogue, field_catalogue


def inspect_source(source: dict) -> dict:
    """Inventaría todos los mensajes y mallas de una fuente, sin leer valores."""
    grib_files = sorted(
        (Path(item) for item in glob.glob(source["input_pattern"])),
        key=forecast_hour_from_name,
    )
    if not grib_files:
        raise RuntimeError(f"No se encontraron archivos para {source['id']}.")

    inventory_variables = set()
    field_catalogue = collections.defaultdict(lambda: {"count": 0, "levels": set(), "steps": set()})
    origin_catalogue = collections.Counter()
    grid_catalogue = collections.Counter()
    file_messages = {}

    # WGRIB2 sólo lee cabeceras durante el inventario; se ejecuta en paralelo
    # para no alterar ni crear índices junto a los GRIB originales.
    with ThreadPoolExecutor(max_workers=4) as executor:
        for index, variables in enumerate(executor.map(ncep_inventory_variables, grib_files), start=1):
            inventory_variables.update(variables)
            if index % 4 == 0 or index == len(grib_files):
                print(f"  {source['id']}: cabeceras WGRIB2 {index}/{len(grib_files)}", flush=True)

    with ThreadPoolExecutor(max_workers=4) as executor:
        metadata_rows = executor.map(read_grib_metadata, grib_files)
        for index, (grib_file, metadata) in enumerate(zip(grib_files, metadata_rows), start=1):
            message_count, file_origins, file_grids, file_fields = metadata
            file_messages[grib_file.name] = message_count
            origin_catalogue.update(file_origins)
            grid_catalogue.update(file_grids)
            for key, values in file_fields.items():
                field_catalogue[key]["count"] += values["count"]
                field_catalogue[key]["levels"].update(values["levels"])
                field_catalogue[key]["steps"].update(values["steps"])
            if index % 4 == 0 or index == len(grib_files):
                print(f"  {source['id']}: metadatos PyGRIB {index}/{len(grib_files)}", flush=True)

    forecast_hours = [forecast_hour_from_name(grib_file) for grib_file in grib_files]
    expected_hours = list(range(forecast_hours[0], forecast_hours[-1] + 1, 3))
    missing_hours = sorted(set(expected_hours) - set(forecast_hours))

    return {
        "id": source["id"],
        "grib_files": grib_files,
        "forecast_hours": forecast_hours,
        "missing_hours": missing_hours,
        "file_messages": file_messages,
        "inventory_variables": inventory_variables,
        "field_catalogue": field_catalogue,
        "origin_catalogue": origin_catalogue,
        "grid_catalogue": grid_catalogue,
    }


def format_values(values: set) -> str:
    """Presenta conjuntos de valores sin perder información en tablas Markdown."""
    return ", ".join(str(value) for value in sorted(values))


def summarize_steps(steps: set[tuple]) -> str:
    """Resume la cobertura temporal de un producto sin repetir cada plazo."""
    start_steps = [item[0] for item in steps]
    end_steps = [item[1] for item in steps]
    return (
        f"{len(steps)} intervalos; inicio {min(start_steps)}–{max(start_steps)} h; "
        f"fin {min(end_steps)}–{max(end_steps)} h"
    )


def summarize_wgrib2_configuration(wgrib2_config: str) -> str:
    """Extrae sólo la versión y la convención de nombres relevantes al inventario."""
    relevant_lines = [
        line.strip()
        for line in wgrib2_config.splitlines()
        if line.startswith("wgrib2 ") or line.startswith("default WMO names:")
    ]
    if len(relevant_lines) != 2:
        raise RuntimeError("La configuración de WGRIB2 no incluye versión y convención de nombres.")
    return "; ".join(relevant_lines)


def write_source_report(source_inventory: dict, report_path: Path, wgrib2_config: str) -> None:
    """Escribe un reporte compacto, legible y suficiente para comparar fuentes."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    forecast_hours = source_inventory["forecast_hours"]
    message_counts = list(source_inventory["file_messages"].values())
    wgrib2_variables = sorted(source_inventory["inventory_variables"])
    lines = [
        f"# Inventario GRIB2 — {source_inventory['id']}",
        "",
        "Este reporte describe una fuente en exploración. No valida su procedencia "
        "ni define aún el estándar NetCDF.",
        "",
        f"Generado: {datetime.datetime.now(datetime.UTC).isoformat()}",
        "",
        "## WGRIB2",
        "",
        f"- Comando de inventario: `-names ncep -VT -var -lev0 -ftime -s`.",
        f"- {summarize_wgrib2_configuration(wgrib2_config)}.",
        f"- Etiquetas NCEP observadas: {', '.join(wgrib2_variables)}.",
        "",
        "## Archivos y plazos",
        "",
        f"- Archivos: {len(source_inventory['grib_files'])}",
        f"- Mensajes GRIB: {sum(message_counts)}; por archivo: {min(message_counts)}–{max(message_counts)}.",
        f"- Cobertura: {min(forecast_hours)}–{max(forecast_hours)} h; {len(forecast_hours)} plazos presentes.",
        f"- Plazos faltantes en una secuencia de 3 h: {format_values(set(source_inventory['missing_hours'])) or 'ninguno'}",
    ]

    lines.extend(["", "## Procedencia declarada en GRIB", "", "| Centro | Descripción | Subcentro | Tabla maestra | Tabla local | Estado | Tipo | Proceso | Identificador | Mensajes |", "|---|---|---:|---:|---:|---:|---|---:|---:|---:|"])
    for metadata, count in sorted(source_inventory["origin_catalogue"].items(), key=lambda item: str(item[0])):
        lines.append("| " + " | ".join(str(value) for value in metadata) + f" | {count} |")

    lines.extend(["", "## Mallas declaradas en GRIB", "", "| Plantilla | Ni | Nj | Δlon | Δlat | Latitud inicial | Longitud inicial | Latitud final | Longitud final | Escaneo | Mensajes |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for metadata, count in sorted(source_inventory["grid_catalogue"].items(), key=lambda item: str(item[0])):
        lines.append("| " + " | ".join(str(value) for value in metadata) + f" | {count} |")

    lines.extend(["", "## Catálogo meteorológico PyGRIB", "", "Cada fila agrupa mensajes con la misma identidad física y de producto. Los plazos individuales se resumen para mantener el informe revisable.", "", "| Disciplina-categoría-parámetro | Nombre corto | Nombre | Unidad | Tipo de nivel | Proceso temporal | PDT | Niveles | Cobertura temporal | Mensajes |", "|---|---|---|---|---|---|---:|---|---|---:|"])
    for key, values in sorted(source_inventory["field_catalogue"].items(), key=lambda item: str(item[0])):
        discipline, category, parameter, short_name, name, units, level_type, step_type, pdt = key
        row = [
            f"{discipline}-{category}-{parameter}",
            short_name,
            name,
            units,
            level_type,
            step_type,
            pdt,
            format_values(values["levels"]),
            summarize_steps(values["steps"]),
            values["count"],
        ]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalized_longitudes(longitudes: np.ndarray) -> np.ndarray:
    """Convierte longitudes a -180..180 sin cambiar la posición de los puntos."""
    return ((longitudes + 180.0) % 360.0) - 180.0


def coordinate_indexes(global_values: np.ndarray, regional_values: np.ndarray, coordinate_name: str) -> list[int]:
    """Ubica cada coordenada regional en la malla global sin interpolar."""
    indexes = []
    for value in regional_values:
        matches = np.flatnonzero(np.isclose(global_values, value, atol=1e-8))
        if len(matches) != 1:
            raise RuntimeError(
                f"La coordenada {coordinate_name}={value} no identifica un único punto global."
            )
        indexes.append(int(matches[0]))
    return indexes


def compare_ecmwf_sources(comparison: dict, source_inventories: dict) -> list[str]:
    """Compara malla, catálogo y muestras de valores entre ECMWF global y SUD."""
    global_inventory = source_inventories[comparison["global_source"]]
    regional_inventory = source_inventories[comparison["regional_source"]]
    global_files = {forecast_hour_from_name(item): item for item in global_inventory["grib_files"]}
    regional_files = {forecast_hour_from_name(item): item for item in regional_inventory["grib_files"]}
    common_hours = sorted(set(global_files) & set(regional_files))

    with pygrib.open(str(global_files[common_hours[0]])) as global_messages:
        global_reference = global_messages.message(1)
        global_latitudes, global_longitudes = global_reference.latlons()
    with pygrib.open(str(regional_files[common_hours[0]])) as regional_messages:
        regional_reference = regional_messages.message(1)
        regional_latitudes, regional_longitudes = regional_reference.latlons()

    latitude_indexes = coordinate_indexes(global_latitudes[:, 0], regional_latitudes[:, 0], "latitud")
    longitude_indexes = coordinate_indexes(
        normalized_longitudes(global_longitudes[0, :]),
        normalized_longitudes(regional_longitudes[0, :]),
        "longitud",
    )

    comparison_lines = [
        f"# Comparación ECMWF global y SUD — {comparison['id']}",
        "",
        "La comparación verifica metadatos de malla para todas las fuentes y valores "
        "de una muestra configurada. No certifica por sí sola la procedencia original.",
        "",
        f"- Plazos comunes: {format_values(set(common_hours))}",
        f"- Latitudes SUD presentes exactamente en global: {len(latitude_indexes)} de {regional_latitudes.shape[0]}",
        f"- Longitudes SUD presentes exactamente en global: {len(longitude_indexes)} de {regional_longitudes.shape[1]}",
        "",
        "## Comparación de valores configurada",
        "",
        "| Plazo (h) | Disciplina-categoría-parámetro | Nivel | Proceso | Resultado |",
        "|---:|---|---|---|---|",
    ]

    for forecast_hour in comparison["sample_forecast_hours"]:
        if forecast_hour not in global_files or forecast_hour not in regional_files:
            comparison_lines.append(f"| {forecast_hour} | — | — | — | No disponible en ambas fuentes |")
            continue
        with pygrib.open(str(global_files[forecast_hour])) as global_messages, pygrib.open(
            str(regional_files[forecast_hour])
        ) as regional_messages:
            global_by_signature = {message_signature(message): message for message in global_messages}
            regional_by_signature = {message_signature(message): message for message in regional_messages}

            for field in comparison["sample_fields"]:
                discipline, category, parameter, level_type, level, step_type = field
                matches = [
                    signature
                    for signature in global_by_signature
                    if signature[:6] == (discipline, category, parameter, level_type, level, step_type)
                    and signature in regional_by_signature
                ]
                if len(matches) != 1:
                    comparison_lines.append(
                        f"| {forecast_hour} | {discipline}-{category}-{parameter} | {level_type} {level} | {step_type} | "
                        f"Coincidencias no unívocas: {len(matches)} |"
                    )
                    continue
                signature = matches[0]
                global_values = global_by_signature[signature].values
                regional_values = regional_by_signature[signature].values
                cropped_values = global_values[np.ix_(latitude_indexes, longitude_indexes)]
                equal_values = np.array_equal(cropped_values, regional_values)
                maximum_difference = float(np.max(np.abs(cropped_values - regional_values)))
                result = "Iguales" if equal_values else f"Diferencia máxima {maximum_difference}"
                comparison_lines.append(
                    f"| {forecast_hour} | {discipline}-{category}-{parameter} | {level_type} {level} | {step_type} | {result} |"
                )
    return comparison_lines


def main() -> None:
    """Ejecuta el inventario solicitado y escribe sus reportes Markdown."""
    parser = argparse.ArgumentParser(description="Inventaría fuentes GRIB2 con WGRIB2 y PyGRIB.")
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--source", action="append", dest="source_ids")
    parser.add_argument("--comparison-only", action="store_true")
    arguments = parser.parse_args()

    configuration = yaml.safe_load(arguments.configuration.read_text(encoding="utf-8"))
    if arguments.comparison_only:
        source_inventories = {
            source["id"]: {
                "grib_files": sorted(
                    (Path(item) for item in glob.glob(source["input_pattern"])),
                    key=forecast_hour_from_name,
                )
            }
            for source in configuration["sources"]
        }
        for comparison in configuration["comparisons"]:
            report_path = Path(comparison["report_path"])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                "\n".join(compare_ecmwf_sources(comparison, source_inventories)) + "\n",
                encoding="utf-8",
            )
        return
    selected_sources = [
        source
        for source in configuration["sources"]
        if arguments.source_ids is None or source["id"] in arguments.source_ids
    ]
    if not selected_sources:
        raise RuntimeError("No hay fuentes seleccionadas para inventariar.")
    first_pattern = selected_sources[0]["input_pattern"]
    first_files = sorted(glob.glob(first_pattern), key=lambda item: forecast_hour_from_name(Path(item)))
    if not first_files:
        raise RuntimeError("No se encontró un archivo para consultar la configuración de WGRIB2.")
    wgrib2_config = read_wgrib2_configuration(first_files[0])
    source_inventories = {}
    for source in selected_sources:
        print(f"Inventariando {source['id']}...")
        source_inventory = inspect_source(source)
        source_inventories[source["id"]] = source_inventory
        write_source_report(source_inventory, Path(source["report_path"]), wgrib2_config)

    for comparison in configuration["comparisons"]:
        if (
            comparison["global_source"] not in source_inventories
            or comparison["regional_source"] not in source_inventories
        ):
            continue
        print(f"Comparando {comparison['id']}...")
        report_path = Path(comparison["report_path"])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "\n".join(compare_ecmwf_sources(comparison, source_inventories)) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
