"""Genera un reporte Markdown del inventario WGRIB2 y sus remapeos.

Uso:
    python scripts/report_grib2_inventory.py "data/raw/ECMWF/*.grib2" \
        --center ecmwf --model ifs \
        --output outputs/grib2-analysis/ecmwf-inventory.md
"""

import argparse
import glob
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from standardize.grib2_to_netcdf import Grib2ToNetCDF, logger as converter_logger


class RemappingWarningCollector(logging.Handler):
    """Conserva las firmas que el conversor advierte como locales sin remapeo."""

    _SIGNATURE = re.compile(r"firma (?P<signature>\d+-\d+-\d+)")

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.signatures: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Extrae la firma de cada advertencia local emitida por el conversor."""

        match = self._SIGNATURE.search(record.getMessage())
        if match is not None:
            self.signatures.append(match["signature"])


def parse_arguments() -> argparse.Namespace:
    """Obtiene las rutas y la identidad de la corrida que se inventariará."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grib_patterns", nargs="+", help="Rutas o patrones de archivos GRIB2.")
    parser.add_argument("--center", default="ecmwf", help="Centro productor usado por los remapeos.")
    parser.add_argument("--model", default="ecmwf", help="Identificador del modelo para el reporte.")
    parser.add_argument(
        "--configuration-yml",
        type=Path,
        default=Path("config/grib2-definitions.yaml"),
        help="Configuración de definiciones y remapeos GRIB2.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Reporte Markdown de salida.")
    return parser.parse_args()


def resolve_grib_files(grib_patterns: list[str]) -> tuple[list[Path], int]:
    """Expande rutas GRIB y conserva sólo los tres primeros archivos ordenados."""

    grib_files = sorted(
        Path(grib_file)
        for grib_pattern in grib_patterns
        for grib_file in glob.glob(grib_pattern)
    )
    if not grib_files:
        raise RuntimeError("No se encontraron archivos GRIB2 para el inventario.")
    return grib_files[:3], len(grib_files)


def markdown_value(value) -> str:
    """Presenta un valor de tabla Markdown sin alterar su significado."""

    if value is None:
        return "—"
    return str(value).replace("|", "\\|")


def markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    """Construye una tabla Markdown a partir de filas ya resumidas."""

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(markdown_value(value) for value in row) + " |"
        for row in rows
    )
    return lines


def format_levels(levels) -> str:
    """Resume niveles sin repetirlos dentro de una misma variable o firma."""

    return ", ".join(str(level) for level in dict.fromkeys(levels))


def build_variable_rows(converter: Grib2ToNetCDF) -> list[list[object]]:
    """Resume las variables finales planeadas después de aplicar los remapeos."""

    inventory = converter.wgrib2_inventory
    rows = []
    for variable in converter.netcdf_variables.itertuples(index=False):
        levels = inventory.loc[
            inventory["var_name"] == variable.var_name, "level"
        ].tolist()
        rows.append(
            [
                variable.var_name,
                variable.parameter_signature,
                variable.short_name,
                variable.long_name,
                variable.output_units,
                format_levels(levels),
                "sí" if variable.remapping_applied else "no",
                variable.factor if variable.remapping_applied else "—",
                variable.offset if variable.remapping_applied else "—",
            ]
        )
    return rows


def build_unmapped_rows(converter: Grib2ToNetCDF, warning_signatures: list[str]) -> list[list[object]]:
    """Resume sólo las firmas para las que el conversor emitió una advertencia."""

    inventory = converter.wgrib2_inventory
    rows = []
    for signature in dict.fromkeys(warning_signatures):
        messages = inventory.loc[inventory["parameter_signature"] == signature]
        first_message = messages.iloc[0]
        rows.append(
            [
                signature,
                first_message.short_name,
                first_message.description,
                first_message.units,
                format_levels(messages["level"].tolist()),
                len(messages),
            ]
        )
    return rows


def main() -> None:
    """Ejecuta sólo inventario WGRIB2 y escribe su revisión científica en Markdown."""

    arguments = parse_arguments()
    grib_files, available_file_count = resolve_grib_files(arguments.grib_patterns)
    converter = Grib2ToNetCDF(
        grib_files=grib_files,
        model=arguments.model,
        center=arguments.center,
        configuration_yml=arguments.configuration_yml,
    )
    warning_collector = RemappingWarningCollector()
    original_level = converter_logger.level
    converter_logger.addHandler(warning_collector)
    converter_logger.setLevel(logging.WARNING)
    try:
        converter._build_inventory()
        converter._build_netcdf_variables()
    finally:
        converter_logger.removeHandler(warning_collector)
        converter_logger.setLevel(original_level)

    inventory = converter.wgrib2_inventory
    valid_times = sorted(inventory["valid_time"].unique())
    reference_times = sorted(inventory["reference_time"].unique())
    domains = ", ".join(inventory["domain"].drop_duplicates().tolist())
    grid_shapes = ", ".join(
        f"{row.nx} × {row.ny}"
        for row in inventory[["nx", "ny"]].drop_duplicates().itertuples(index=False)
    )
    variable_rows = build_variable_rows(converter)
    unmapped_rows = build_unmapped_rows(converter, warning_collector.signatures)

    lines = [
        f"# Inventario GRIB2 — {converter.center}-{converter.model}",
        "",
        "Reporte de cabeceras WGRIB2 y planificación de remapeos. No lee matrices "
        "GRIB ni crea NetCDF.",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Cobertura inventariada",
        "",
        f"- Archivos encontrados: {available_file_count}",
        f"- Archivos inventariados: {len(grib_files)} primeros en orden ascendente",
        f"- Mensajes GRIB2: {len(inventory)}",
        f"- Hora de referencia: {', '.join(value.isoformat() for value in reference_times)}",
        f"- Tiempos válidos: {valid_times[0].isoformat()} a {valid_times[-1].isoformat()} ({len(valid_times)} tiempos)",
        f"- Dominio WGRIB2: {domains}",
        f"- Resolución: {grid_shapes}",
        "",
        "## Variables finales planeadas",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "Variable final",
                "Firma",
                "Nombre WGRIB2",
                "Long name",
                "Unidades",
                "Niveles",
                "Remapeo",
                "Factor",
                "Offset",
            ],
            variable_rows,
        )
    )
    lines.extend(["", "## Parámetros locales sin remapeo aprobado", ""])
    if unmapped_rows:
        lines.extend(
            markdown_table(
                ["Firma", "Nombre WGRIB2", "Descripción", "Unidades", "Niveles", "Mensajes"],
                unmapped_rows,
            )
        )
        signatures = " ".join(row[0] for row in unmapped_rows)
        lines.extend(
            [
                "",
                "## Investigación de remapeos",
                "",
                "Las siguientes firmas fueron emitidas por la advertencia del conversor. "
                "Para consultar los candidatos ECMWF definidos por ecCodes:",
                "",
                f"```bash\npython scripts/inspect_ecmwf_parameter.py {signatures} --output outputs/grib2-analysis/ecmwf-parameters.md\n```",
            ]
        )
    else:
        lines.append("No se emitieron advertencias de parámetros locales sin remapeo.")

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reporte de inventario: {arguments.output}")


if __name__ == "__main__":
    main()
