"""Inventario WGRIB2 para la conversión de GRIB2 a NetCDF."""

import logging
import re
import subprocess as sp
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


class Grib2ToNetCDF:
    """Construye el inventario WGRIB2 de los mensajes de una corrida GRIB2.

    Inventaría todos los mensajes de los archivos ordenados y conserva el orden
    de cada archivo para asociarlo con la lectura secuencial de PyGRIB durante
    la escritura futura. No decodifica matrices, no selecciona variables, no
    aplica remapeos YAML y no crea archivos NetCDF en esta fase.

    Args:
        grib_files: Archivos GRIB2 de una misma corrida meteorológica.
        model: Identificador del modelo usado para informar errores.
        center: Centro productor usado por los remapeos de fases posteriores.
        configuration_yml: Configuración única del conversor.
        area: Área opcional ``(west, east, south, north)`` para una fase
            posterior de recorte geográfico.
    """

    _DESCRIPTION_WITH_UNITS = re.compile(
        r"^(?P<description>.+?)\s+\[(?P<units>[^\[\]]*)\]$"
    )

    def __init__(
        self,
        grib_files: Sequence[str | Path],
        model: str,
        center: str,
        configuration_yml: str | Path = "config/grib2-definitions.yaml",
        area: tuple[float, float, float, float] | None = None,
    ) -> None:
        if not grib_files:
            raise ValueError("Se requiere al menos un archivo GRIB2 para construir el inventario.")
        if not model.strip():
            raise ValueError("Se requiere el identificador del modelo para construir el inventario.")
        if not center.strip():
            raise ValueError("Se requiere el centro productor para construir el inventario.")

        self.grib_files = sorted(Path(grib_file) for grib_file in grib_files)
        self.model = model.lower()
        self.center = center.lower()
        self.configuration_yml = Path(configuration_yml)
        self.area = area
        self.wgrib2_inventory: pd.DataFrame | None = None

    def __str__(self) -> str:
        return f"Grib2ToNetCDF inventariando {len(self.grib_files)} archivos GRIB2"

    def __repr__(self) -> str:
        return f"<Grib2ToNetCDF con {len(self.grib_files)} archivos GRIB2>"

    # ------------------------------------------------------------------
    # Inventario WGRIB2
    # ------------------------------------------------------------------

    def _run_wgrib2_command(self, grib_file: Path) -> str:
        """Ejecuta WGRIB2 sobre un archivo GRIB2 y devuelve su inventario."""

        command = ["wgrib2", "-names", "ncep", "-T", "-VT", "-domain", "-lev0", "-nxny", "-ctl_inv", str(grib_file)]

        try:
            result = sp.run(command, capture_output=True, text=True, check=True)
        except sp.CalledProcessError as error:
            detail = error.stderr.strip() or str(error)
            raise RuntimeError(f"WGRIB2 no pudo inventariar el archivo {grib_file.name} del modelo {self.model}: {detail}") from error

        if not result.stdout.strip():
            raise RuntimeError(f"WGRIB2 no devolvió mensajes para el archivo {grib_file.name} del modelo {self.model}.")
        return result.stdout

    def _parse_wgrib2_output(self, grib_file: Path, output: str) -> pd.DataFrame:
        """Interpreta la salida de WGRIB2 con los argumentos de inventario.

        El comando ejecutado es:

            wgrib2 -names ncep -T -VT -domain -lev0 -nxny -ctl_inv {filename}

        ``-names ncep`` fija la nomenclatura inicial de ``var_name``. ``-T`` y
        ``-VT`` entregan la fecha de inicio de la corrida y el tiempo válido.
        ``-domain`` y ``-nxny`` describen la extensión y el tamaño de grilla;
        ``-lev0`` entrega el nivel textual del mensaje. ``-ctl_inv`` aporta la
        identidad disciplina-categoría-parámetro, el proceso estadístico, la
        descripción y las unidades según la lógica de g2ctl.

        La salida contiene ocho segmentos separados por ``:``: mensaje, byte,
        fecha de corrida, tiempo válido, dominio, nivel, tamaño de grilla y
        ``ctl_inv``. El cuarto componente opcional de la definición de parámetro
        corresponde a una tabla local y no interviene en esta fase.
        """
        rows = []

        for line in output.splitlines():
            if not line.strip():
                continue

            _, _, forecast_date_text, valid_time_text, domain, level, grid_size, ctl_inventory = line.split(":", 7)
            var_name, _, parameter_definition, statistical_process, full_name = ctl_inventory.split(maxsplit=4)
            discipline, category, parameter, *_ = parameter_definition.split(",")
            nx, ny = (int(value) for value in grid_size.strip("()").split(" x "))

            units_match = self._DESCRIPTION_WITH_UNITS.fullmatch(full_name)
            if units_match is None:
                description = full_name
                units = None
            else:
                description = units_match["description"]
                units = units_match["units"].strip() or None
                if units == "-":
                    units = None

            reference_time = datetime.strptime(forecast_date_text.removeprefix("D="), "%Y%m%d%H%M%S")
            valid_time = datetime.strptime(valid_time_text.removeprefix("vt="), "%Y%m%d%H%M%S")

            rows.append(
                {
                    "grib_file": str(grib_file),
                    "var_name": var_name,
                    "discipline": int(discipline),
                    "category": int(category),
                    "parameter": int(parameter),
                    "level": level,
                    "statistical_process": statistical_process,
                    "valid_time": valid_time,
                    "reference_time": reference_time,
                    "domain": domain,
                    "nx": nx,
                    "ny": ny,
                    "description": description,
                    "units": units,
                }
            )

        return pd.DataFrame(rows)

    def _build_inventory(self) -> pd.DataFrame:
        """Construye el inventario completo conservando el orden de los archivos."""
        inventory_frames = []

        # Revisión de archivos GRIB2
        for grib_file in self.grib_files:
            if not grib_file.is_file():
                raise FileNotFoundError(f"No se encontró el archivo GRIB2 {grib_file} para el modelo {self.model}.")

        # Lectura de salidas WGRIB2
        for grib_file in self.grib_files:
            output = self._run_wgrib2_command(grib_file)
            inventory_frames.append(self._parse_wgrib2_output(grib_file, output))

        # El orden de las filas se respeta porque es el contenido de los archivos
        self.wgrib2_inventory = pd.concat(inventory_frames, ignore_index=True)
        logger.info("Inventario WGRIB2 completado para %s: %s mensajes en %s archivos.", self.model, len(self.wgrib2_inventory), len(self.grib_files))
        return self.wgrib2_inventory
