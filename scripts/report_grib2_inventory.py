"""Genera un reporte Markdown de las variables presentes en una corrida GRIB2.

Uso:
    python scripts/report_grib2_inventory.py "data/raw/ECMWF/*.grib2" \
        --center ecmwf --model ifs \
        --output outputs/grib2-analysis/ecmwf-inventory.md
"""

import argparse
import glob
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from standardize.grib2_to_netcdf import Grib2ToNetCDF


GROUP_COLUMNS = ["parameter_signature", "varname_key"]


def parse_arguments() -> argparse.Namespace:
    """Obtiene las rutas, configuración y destino del reporte."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grib_patterns", nargs="+", help="Rutas o patrones de archivos GRIB2.")
    parser.add_argument("--center", default="ecmwf", help="Centro productor usado por los remapeos.")
    parser.add_argument("--model", default="ecmwf", help="Identificador del modelo.")
    parser.add_argument(
        "--configuration-yml",
        type=Path,
        default=Path("config/grib2-definitions.yaml"),
        help="Configuración de definiciones y remapeos GRIB2.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Reporte Markdown de salida.")
    return parser.parse_args()


def resolve_grib_files(grib_patterns: list[str]) -> tuple[list[Path], int]:
    """Expande las rutas GRIB y conserva su orden temporal lexicográfico."""

    grib_files = sorted(
        Path(grib_file)
        for grib_pattern in grib_patterns
        for grib_file in glob.glob(grib_pattern)
    )
    if not grib_files:
        raise RuntimeError("No se encontraron archivos GRIB2 para el inventario.")
    return grib_files, len(grib_files)


def markdown_value(value: object) -> str:
    """Presenta valores de tablas Markdown sin alterar su significado."""

    if value is None or pd.isna(value):
        return "—"
    return str(value).replace("|", "\\|").replace("\n", "; ")


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


def group_unsupported_variables(
    inventory: pd.DataFrame, supported_variables: pd.DataFrame
) -> pd.DataFrame:
    """Agrupa mensajes presentes que la lógica vertical no admite para NetCDF."""

    supported_keys = supported_variables[GROUP_COLUMNS].drop_duplicates()
    unsupported_messages = inventory.merge(
        supported_keys,
        on=GROUP_COLUMNS,
        how="left",
        indicator=True,
    )
    unsupported_messages = unsupported_messages.loc[
        unsupported_messages["_merge"].eq("left_only")
    ].drop(columns="_merge")
    if unsupported_messages.empty:
        return pd.DataFrame(columns=[*GROUP_COLUMNS, "level_name", "surface_value"])
    return (
        unsupported_messages.groupby(GROUP_COLUMNS, sort=True)
        .agg(Grib2ToNetCDF.unique_or_join)
        .reset_index()
    )


def build_supported_rows(supported_variables: pd.DataFrame) -> list[list[object]]:
    """Construye filas de las variables presentes que el conversor admite."""

    return [
        [
            variable.parameter_signature,
            variable.var_name,
            variable.units,
            variable.long_name,
            variable.level_name,
            variable.surface_value,
        ]
        for variable in supported_variables.itertuples(index=False)
    ]


def build_unsupported_rows(unsupported_variables: pd.DataFrame) -> list[list[object]]:
    """Construye filas de las variaciones verticales presentes no admitidas."""

    rows = []
    for variable in unsupported_variables.itertuples(index=False):
        rows.append(
            [
                variable.parameter_signature,
                variable.short_name,
                variable.units,
                variable.long_name,
                variable.level_name,
                variable.surface_value,
                "Más de un level_name para la misma firma y clave de agrupación.",
            ]
        )
    return rows


def build_local_rows(
    supported_variables: pd.DataFrame,
    configuration_yml: Path,
    center: str,
) -> tuple[list[list[object]], list[str]]:
    """Lista parámetros locales y devuelve firmas que no tienen remapeo YAML."""

    with configuration_yml.open(encoding="utf-8") as configuration_file:
        configuration = yaml.safe_load(configuration_file)
    local_definition = configuration["local_definitions_reserved"]
    remappings = configuration["remappings"][center]
    is_local = supported_variables["parameter_signature"].apply(
        lambda signature: Grib2ToNetCDF._is_local_parameter(
            local_definition["disciplines"],
            local_definition["category_range"],
            local_definition["parameter_range"],
            signature,
        )
    )
    local_variables = supported_variables.loc[is_local]
    rows = []
    unmapped_signatures = []
    for variable in local_variables.itertuples(index=False):
        remapping = remappings.get(variable.parameter_signature)
        if remapping is None:
            unmapped_signatures.append(variable.parameter_signature)
        rows.append(
            [
                variable.parameter_signature,
                variable.short_name if remapping is None else remapping["name"],
                variable.long_name if remapping is None else remapping["long_name"],
                variable.units if remapping is None else remapping["units"],
                variable.level_name,
                variable.statistical_process,
                "sí" if remapping is not None else "no",
                variable.parameter_info,
            ]
        )
    return rows, list(dict.fromkeys(unmapped_signatures))


def main() -> None:
    """Prepara el inventario de variables sin leer matrices ni crear NetCDF."""

    arguments = parse_arguments()
    grib_files, available_file_count = resolve_grib_files(arguments.grib_patterns)
    converter = Grib2ToNetCDF(
        grib_files=grib_files,
        model=arguments.model,
        center=arguments.center,
        configuration_yml=arguments.configuration_yml,
    )

    # El refactor valida la corrida completa e identifica sus variables sin
    # decodificar matrices meteorológicas ni crear un NetCDF.
    converter._validate_domain_times()
    converter._get_variable_inventory()
    supported_variables = converter._group_grib2_variables()
    unsupported_variables = group_unsupported_variables(
        converter.inventory, supported_variables
    )

    supported_rows = build_supported_rows(supported_variables)
    unsupported_rows = build_unsupported_rows(unsupported_variables)
    local_rows, unmapped_signatures = build_local_rows(
        supported_variables,
        arguments.configuration_yml,
        converter.center,
    )

    sampled_files = [path.name for path in converter.grib_files[:2] + converter.grib_files[-1:]]
    lines = [
        f"# Inventario GRIB2 — {converter.center}-{converter.model}",
        "",
        "Este reporte usa el inventario de variables del conversor. No lee matrices "
        "meteorológicas ni crea un NetCDF.",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Cobertura inventariada",
        "",
        f"- Archivos encontrados y validados: {available_file_count}",
        "- Archivos usados para identificar variables: " + ", ".join(sampled_files),
        f"- Hora de inicialización: {converter.forecast_date.isoformat()}",
        "- Tiempos válidos: "
        f"{converter.time_list[0].isoformat()} a {converter.time_list[-1].isoformat()} "
        f"({len(converter.time_list)} tiempos)",
        f"- Dominio WGRIB2: {converter.domain}",
        f"- Resolución: {converter.nx} × {converter.ny}",
        f"- Plantilla de grilla: {converter.grid_template}",
        "",
        "## Variables presentes y soportadas",
        "",
        "Estas variables se identifican mediante la agrupación g2ctl del conversor "
        "y pueden representarse con la estructura NetCDF canónica.",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "Parameter signature",
                "Variable g2ctl",
                "Unidades",
                "Nombre largo",
                "Nivel",
                "Surface values",
            ],
            supported_rows,
        )
    )
    lines.extend(["", "## Variables presentes no soportadas", ""])
    lines.extend(
        [
            "El NetCDF canónico admite una dimensión vertical 4D sólo para "
            "superficies isobáricas (`surface_type == 100`). Los campos con una "
            "única superficie vertical no isobárica se representan en 3D. Las "
            "variaciones que requieren múltiples niveles verticales no isobáricos, "
            "como las capas de suelo, no están soportadas.",
            "",
        ]
    )
    if unsupported_rows:
        lines.extend(
            markdown_table(
                [
                    "Parameter signature",
                    "Short name",
                    "Unidades",
                    "Nombre largo",
                    "Level names encontrados",
                    "Surface values",
                    "Motivo",
                ],
                unsupported_rows,
            )
        )
    else:
        lines.append("No se identificaron variaciones verticales no soportadas.")
    lines.extend(["", "## Parámetros locales", ""])
    if local_rows:
        lines.extend(
            markdown_table(
                [
                    "Parameter signature",
                    "Short name",
                    "Nombre largo",
                    "Unidades",
                    "Nivel",
                    "Proceso estadístico",
                    "Remapeado",
                    "Parameter info",
                ],
                local_rows,
            )
        )
    else:
        lines.append("No se identificaron parámetros locales en las variables soportadas.")

    if converter.center == "ecmwf" and unmapped_signatures:
        signatures = " ".join(unmapped_signatures)
        lines.extend(
            [
                "",
                "## Investigación de remapeos",
                "",
                "Las siguientes firmas locales no tienen un remapeo YAML aprobado. "
                "Para consultar candidatos ECMWF definidos por ecCodes:",
                "",
                "```bash",
                "python scripts/inspect_ecmwf_parameter.py "
                f"{signatures} --output outputs/grib2-analysis/ecmwf-parameters.md",
                "```",
            ]
        )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reporte de inventario: {arguments.output}")


if __name__ == "__main__":
    main()
