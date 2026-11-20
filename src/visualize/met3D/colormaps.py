"""Prepara bandas discretas de color y transparencia para campos meteorológicos."""

from __future__ import annotations

import math
import re
import struct

import numpy as np


def encode_met3d_rgb_colour(rgb: list[int]) -> str:
    """Serializa sRGB en el formato XYZ del editor nativo de Met.3D 2.0.0b11."""

    # El editor conserva XYZ con blanco D65; estos coeficientes siguen su conversión sRGB.
    linear_rgb = [((value / 255 + 0.055) / 1.055) ** 2.4 if value / 255 > 0.03928 else value / 255 / 12.92 for value in rgb]
    red, green, blue = linear_rgb
    xyz = (
        100 * (0.412453 * red + 0.357580 * green + 0.180423 * blue),
        100 * (0.212671 * red + 0.715160 * green + 0.072169 * blue),
        100 * (0.019334 * red + 0.119193 * green + 0.950227 * blue),
    )
    # Met.3D guarda su estructura XYZ como bytes nativos: tres doubles y dos indicadores.
    colour = struct.pack("=3d??6x", *xyz, True, True)
    return "@ByteArray(" + "".join("\\0" if value == 0 else f"\\x{value:02x}" for value in colour) + ")"


def prepare_pressure_colour_bands(colourmap: dict, description: str) -> list[dict]:
    """Valida intervalos contiguos y prepara su representación exacta con presión float32."""

    if colourmap.get("units") != "hPa" or colourmap.get("intervals") != "left_closed_right_open":
        raise RuntimeError(f"{description}: la paleta requiere unidades hPa e intervalos [Li, Ls).")
    bands = colourmap.get("bands")
    if not isinstance(bands, list) or len(bands) < 3:
        raise RuntimeError(f"{description}: se requieren bandas interiores y dos extremos abiertos.")

    # Revisar cada rango antes de generar colores o límites para Met.3D.
    for index, band in enumerate(bands):
        if not isinstance(band, dict) or not {"lower", "upper", "hex", "opacity"} <= band.keys():
            raise RuntimeError(f"{description}: la banda {index + 1} requiere lower, upper, hex y opacity.")
        lower, upper = band["lower"], band["upper"]
        if (lower is None) != (index == 0) or (upper is None) != (index == len(bands) - 1):
            raise RuntimeError(f"{description}: sólo la primera y la última banda pueden tener extremos abiertos, banda {index + 1}.")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in (lower, upper) if value is not None):
            raise RuntimeError(f"{description}: límites de presión inválidos en la banda {index + 1}.")
        if lower is not None and upper is not None and lower >= upper:
            raise RuntimeError(f"{description}: la banda {index + 1} requiere Li < Ls.")
        if index and lower != bands[index - 1]["upper"]:
            raise RuntimeError(f"{description}: hay un hueco o solapamiento antes de la banda {index + 1}.")
        if not isinstance(band["hex"], str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", band["hex"]) is None:
            raise RuntimeError(f"{description}: color HEX inválido en la banda {index + 1}.")
        if not isinstance(band["opacity"], (int, float)) or not 0 <= band["opacity"] <= 1:
            raise RuntimeError(f"{description}: la opacidad de la banda {index + 1} debe estar entre 0 y 1.")

    # Cada banda recibe un color constante y límites independientes: no hay degradados.
    prepared = []
    for index, band in enumerate(bands):
        lower, upper = band["lower"], band["upper"]
        # Los extremos gráficos finitos permiten extender el color hacia el infinito correspondiente.
        minimum = lower if lower is not None else upper - (bands[index + 1]["upper"] - upper)
        maximum = upper if upper is not None else lower + (lower - bands[index - 1]["lower"])
        minimum_pa = float(np.float32(minimum * 100))
        # El límite superior excluido se representa con el float32 inmediatamente anterior.
        maximum_pa = float(np.nextafter(np.float32(maximum * 100), np.float32(-np.inf))) if upper is not None else float(np.float32(maximum * 100))
        if minimum_pa >= maximum_pa:
            raise RuntimeError(f"{description}: la banda {index + 1} no tiene un intervalo float32 representable.")
        rgb = [int(band["hex"][offset:offset + 2], 16) for offset in (1, 3, 5)]
        label = f"< {upper:g}" if lower is None else f">= {lower:g}" if upper is None else f"[{lower:g}, {upper:g})"
        if band["opacity"] == 0:
            label += " sin relleno"
        prepared.append({
            **band, "index": index + 1,
            "minimum_pa": minimum_pa, "maximum_pa": maximum_pa,
            "extend_below": lower is None, "extend_above": upper is None,
            "rgb": rgb, "colour_xyz": encode_met3d_rgb_colour(rgb), "label": label,
            "transfer_function": f"PNM - banda {index + 1:02d}",
        })
    return prepared
