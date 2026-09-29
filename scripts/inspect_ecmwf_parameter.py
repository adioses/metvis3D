"""Investiga candidatos ECMWF ecCodes a partir de firmas GRIB2 locales.

Uso:
    python scripts/inspect_ecmwf_parameter.py 0-1-193 2-0-201 \
        --output outputs/grib2-analysis/ecmwf-parameters.md
"""

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import eccodes as ecc


_SIGNATURE = re.compile(r"(?P<discipline>\d+)-(?P<category>\d+)-(?P<parameter>\d+)$")
_BLOCK = re.compile(
    r"(?m)^(?:#(?P<label>[^\n]*)\n)?'(?P<value>[^']+)'\s*=\s*\{(?P<keys>.*?)^\s*\}",
    re.DOTALL,
)
_KEY_VALUE = re.compile(r"(?m)^\s*(?P<key>\w+)\s*=\s*(?P<value>[^;]+);")


def parse_arguments() -> argparse.Namespace:
    """Obtiene las firmas ECMWF que se investigarán y el reporte de salida."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parameter_signatures", nargs="+", help="Firmas disciplina-categoría-parámetro.")
    parser.add_argument("--output", type=Path, required=True, help="Reporte Markdown de salida.")
    return parser.parse_args()


def parse_signature(signature: str) -> tuple[int, int, int]:
    """Convierte una firma textual en su terna numérica GRIB2."""

    match = _SIGNATURE.fullmatch(signature)
    if match is None:
        raise ValueError(f"La firma debe usar disciplina-categoría-parámetro: {signature}")
    return tuple(int(match[group]) for group in ("discipline", "category", "parameter"))


def read_parameter_definitions() -> list[dict]:
    """Lee los conceptos locales ECMWF de paramId instalados con ecCodes."""

    definitions_path = Path(ecc.codes_definition_path())
    definition_file = definitions_path / "grib2" / "localConcepts" / "ecmf" / "paramId.def"
    definition_text = definition_file.read_text(encoding="utf-8")
    definitions = []
    for block in _BLOCK.finditer(definition_text):
        conditions = {
            match["key"]: match["value"].strip().strip("'")
            for match in _KEY_VALUE.finditer(block["keys"])
        }
        definitions.append(
            {
                "param_id": int(block["value"]),
                "label": block["label"] or "Sin descripción en la definición local",
                "conditions": conditions,
            }
        )
    return definitions


def find_candidates(definitions: list[dict], signature: tuple[int, int, int]) -> list[dict]:
    """Selecciona los conceptos ECMWF que comparten la firma solicitada."""

    expected = dict(zip(("discipline", "parameterCategory", "parameterNumber"), signature))
    return [
        definition
        for definition in definitions
        if all(definition["conditions"].get(key) == str(value) for key, value in expected.items())
    ]


def set_condition(grib_handle, key: str, value: str) -> None:
    """Asigna una condición ecCodes preservando sus valores numéricos."""

    ecc.codes_set(grib_handle, key, int(value) if value.isdigit() else value)


def resolve_candidate(candidate: dict) -> dict:
    """Resuelve el candidato en una plantilla GRIB2 ECMWF creada en memoria."""

    conditions = candidate["conditions"]
    grib_handle = ecc.codes_grib_new_from_samples("GRIB2")
    try:
        ecc.codes_set(grib_handle, "centre", "ecmf")
        if "typeOfStatisticalProcessing" in conditions:
            ecc.codes_set(grib_handle, "productDefinitionTemplateNumber", 8)

        for key in (
            "localTablesVersion",
            "discipline",
            "parameterCategory",
            "parameterNumber",
        ):
            if key in conditions:
                set_condition(grib_handle, key, conditions[key])
        for key, value in conditions.items():
            if key not in {"localTablesVersion", "discipline", "parameterCategory", "parameterNumber"}:
                set_condition(grib_handle, key, value)

        resolved_param_id = ecc.codes_get(grib_handle, "paramId")
        if resolved_param_id != candidate["param_id"]:
            raise RuntimeError(
                f"ecCodes resolvió {resolved_param_id} y no el candidato {candidate['param_id']}."
            )
        return {
            "param_id": resolved_param_id,
            "short_name": ecc.codes_get(grib_handle, "shortName"),
            "name": ecc.codes_get(grib_handle, "name"),
            "units": ecc.codes_get(grib_handle, "units"),
        }
    finally:
        ecc.codes_release(grib_handle)


def markdown_value(value: object) -> str:
    """Presenta valores sin romper las tablas Markdown."""

    return str(value).replace("|", "\\|")


def main() -> None:
    """Genera un Markdown de candidatos locales ECMWF sin abrir archivos GRIB."""

    arguments = parse_arguments()
    definitions = read_parameter_definitions()
    definition_path = Path(ecc.codes_definition_path())
    lines = [
        "# Candidatos de parámetros locales ECMWF",
        "",
        "Este reporte consulta las definiciones locales instaladas por ecCodes. "
        "No abre archivos GRIB ni aprueba remapeos.",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat()}",
        f"- ecCodes: {ecc.codes_get_api_version()}",
        f"- Definiciones: `{definition_path}`",
    ]

    for signature_text in arguments.parameter_signatures:
        signature = parse_signature(signature_text)
        candidates = find_candidates(definitions, signature)
        lines.extend(["", f"## Firma `{signature_text}`", ""])
        if not candidates:
            lines.append("No hay candidatos en las definiciones locales ECMWF instaladas.")
            continue

        lines.extend(
            [
                f"Candidatos ECMWF encontrados: {len(candidates)}.",
                "",
                "| paramId | shortName | Nombre | Unidades | URL |",
                "|---:|---|---|---|---|",
            ]
        )
        resolved_candidates = [
            (candidate, resolve_candidate(candidate)) for candidate in candidates
        ]
        for _, resolved in resolved_candidates:
            parameter_url = f"https://codes.ecmwf.int/grib/param-db/{resolved['param_id']}"
            lines.append(
                "| "
                + " | ".join(
                    markdown_value(value)
                    for value in (
                        resolved["param_id"],
                        resolved["short_name"],
                        resolved["name"],
                        resolved["units"],
                        f"[{parameter_url}]({parameter_url})",
                    )
                )
                + " |"
            )

        for candidate, resolved in resolved_candidates:
            lines.extend(
                [
                    "",
                    f"### Candidato `{resolved['param_id']}` — {resolved['name']}",
                    "",
                    f"- `shortName`: `{resolved['short_name']}`",
                    f"- `units`: `{resolved['units']}`",
                    f"- Definición local: {candidate['label']}",
                    "",
                    "#### Condiciones ecCodes",
                    "",
                ]
            )
            lines.extend(
                f"- `{key}`: `{value}`" for key, value in candidate["conditions"].items()
            )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reporte de candidatos ECMWF: {arguments.output}")


if __name__ == "__main__":
    main()
