"""Inventario WGRIB2 para la conversión de GRIB2 a NetCDF."""

import logging
import re
import subprocess as sp
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from shapely.geometry import box


logger = logging.getLogger(__name__)


class Grib2ToNetCDF:
    """Construye el inventario WGRIB2 de los mensajes de una corrida GRIB2.

    Inventaría todos los mensajes de los archivos ordenados y conserva el orden
    de cada archivo para asociarlo con la lectura secuencial de PyGRIB durante
    la escritura futura. No decodifica matrices, no selecciona variables ni
    crea archivos NetCDF. La consolidación posterior
    agrupa las variables NetCDF y resuelve sus remapeos YAML.

    Args:
        grib_files: Archivos GRIB2 de una misma corrida meteorológica.
        model: Identificador del modelo usado para informar errores.
        center: Centro productor usado por los remapeos de fases posteriores.
        configuration_yml: Configuración única del conversor.
        area: Área opcional `(west, south, east, north)` para una fase
            posterior de recorte geográfico.
    """

    _DESCRIPTION_WITH_UNITS = re.compile(
        r"^(?P<description>.+?)\s+\[(?P<units>[^\[\]]*)\]$"
    )
    _PRESSURE_LEVEL = re.compile(r"(\d+)mb")
    _DOMAIN_LIMITS = re.compile(
        r"N=(?P<north>-?\d+(?:\.\d+)?)\s+"
        r"S=(?P<south>-?\d+(?:\.\d+)?)\s+"
        r"W=(?P<west>-?\d+(?:\.\d+)?)\s+"
        r"E=(?P<east>-?\d+(?:\.\d+)?)$"
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
        self.netcdf_variables: pd.DataFrame | None = None
        self.time_list: list[datetime] = []
        self.time_map: dict[datetime, int] = {}
        self.pressure_levels: list[int] = []
        self.lev_map: dict[int, int] = {}

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

        `-names ncep` fija la nomenclatura inicial de `short_name`. `-T` y
        `-VT` entregan la fecha de inicio de la corrida y el tiempo válido.
        `-domain` y `-nxny` describen la extensión y el tamaño de grilla;
        `-lev0` entrega el nivel textual del mensaje. `-ctl_inv` aporta la
        identidad disciplina-categoría-parámetro, el proceso estadístico, la
        descripción y las unidades según la lógica de g2ctl.

        La salida contiene ocho segmentos separados por `:`: mensaje, byte,
        fecha de corrida, tiempo válido, dominio, nivel, tamaño de grilla y
        `ctl_inv`. El cuarto componente opcional de la definición de parámetro
        corresponde a una tabla local y no interviene en esta fase.
        """
        rows = []

        for line in output.splitlines():
            if not line.strip():
                continue

            _, _, forecast_date, valid_time_text, domain, level, grid_size, ctl_inventory = line.split(":", 7)
            short_name, _, parameter_definition, statistical_process, full_name = ctl_inventory.split(maxsplit=4)
            discipline, category, parameter, *_ = parameter_definition.split(",")
            nx, ny = (int(value) for value in grid_size.strip("()").split(" x "))
            parameter_signature = "-".join((discipline, category, parameter))

            # Logica para el nombre de variables, sigue nomenclatura g2ctl
            level_suffix = f"{statistical_process}{level}" if statistical_process == "ave" else level
            if self._match_pressure_level(level):
                var_name = f"{short_name.lower()}prs"
            else:
                var_name = f"{short_name.lower()}{level_suffix}"

            units_match = self._DESCRIPTION_WITH_UNITS.fullmatch(full_name)
            if units_match is None:
                description = full_name
                units = None
            else:
                description = units_match["description"]
                units = units_match["units"].strip() or None
                if units == "-":
                    units = None

            reference_time = datetime.strptime(forecast_date.removeprefix("D="), "%Y%m%d%H%M%S")
            valid_time = datetime.strptime(valid_time_text.removeprefix("vt="), "%Y%m%d%H%M%S")

            rows.append(
                {
                    "grib_file": str(grib_file),
                    "short_name": short_name,
                    "parameter_signature": parameter_signature,
                    "var_name": var_name,
                    "level": level,
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

    # ------------------------------------------------------------------
    # Consolidación de variables NetCDF
    # ------------------------------------------------------------------

    @classmethod
    def _match_pressure_level(cls, level: str) -> re.Match[str] | None:
        """Reconoce niveles isobáricos textuales como ``500mb``."""
        return cls._PRESSURE_LEVEL.fullmatch(level)

    def _read_grib2_configurations(self) -> tuple[dict, dict]:
        """Lee las reglas locales y los remapeos del centro productor."""

        if not self.configuration_yml.is_file():
            raise FileNotFoundError(
                f"No se encontró el archivo YAML de configuración: {self.configuration_yml}"
            )
        try:
            with self.configuration_yml.open(encoding="utf-8") as configuration_file:
                configuration = yaml.safe_load(configuration_file)
            local_definitions = {
                "disciplines": configuration["local_definitions_reserved"]["disciplines"],
                "category_range": configuration["local_definitions_reserved"]["category_range"],
                "parameter_range": configuration["local_definitions_reserved"]["parameter_range"],
            }
            center_remappings = (
                {}
                if self.center == "ncep"
                else configuration["remappings"].get(self.center, {})
            )
        except yaml.YAMLError as error:
            raise ValueError(f"La configuración YAML es inválida en {self.configuration_yml}") from error
        except (KeyError, TypeError) as error:
            raise ValueError(f"Falta o está mal definida una sección de {self.configuration_yml}: {error}") from error
        return local_definitions, center_remappings

    def _validate_inventory(self) -> None:
        """Comprueba que el inventario describa una sola corrida y su subset."""

        # Comprueba que se hayan escaneado archivo grib2
        if self.wgrib2_inventory is None or self.wgrib2_inventory.empty:
            raise RuntimeError(f"Los archivos revisado no corresponden al formato grib2 o no contienen información")
        inventory = self.wgrib2_inventory
        reference_times = inventory["reference_time"].unique()
        domains = inventory["domain"].unique()
        grid_shapes = inventory[["nx", "ny"]].drop_duplicates()
        if len(reference_times) != 1:
            raise RuntimeError(f"Los archivos no corresponden a la misma corrida del modelo {self.model}")
        if len(domains) != 1:
            raise RuntimeError(f"Los archivos tienen dominios distintos: {domains.tolist()}.")
        if len(grid_shapes) != 1:
            raise RuntimeError(f"Los archivos no tienen la misma resolución (distintos grid shapes)")

        self.domain = domains[0]
        grid_shape = grid_shapes.iloc[0]
        self.grid_shape = (int(grid_shape["nx"]), int(grid_shape["ny"]))

        # Verificación que el área de subset es valida
        if self.area is None:
            return

        # crea area bbox
        west, south, east, north = self.area
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(
                "El área debe ser un rectángulo: -180 <= west < east <= 180 y -90 <= south < north <= 90."
            )
        area_geometry = box(west, south, east, north)

        # crea domain bbox
        domain_match = self._DOMAIN_LIMITS.fullmatch(self.domain)
        north, south, west, east = map(float, domain_match.group("north", "south", "west", "east"))
        domain_geometry = box(west, south, east, north)

        # Comparacion dominio vs area
        if not domain_geometry.covers(area_geometry):
            raise RuntimeError(f"El área solicitada no está contenida en el dominio {self.domain} del modelo {self.model}.")

    def _build_coordinates(self) -> None:
        """Construye los ejes temporal y de presión para el NetCDF posterior."""

        # Eje temporal: conserva exactamente los tiempos válidos inventariados.
        self.time_list = sorted(self.wgrib2_inventory["valid_time"].unique())
        self.time_map = {valid_time: index for index, valid_time in enumerate(self.time_list)}

        # Eje vertical: conserva los niveles isobáricos descendentes del inventario.
        self.pressure_levels = sorted(
            {
                int(match.group(1))
                for level in self.wgrib2_inventory["level"]
                if (match := self._match_pressure_level(level))
            },
            reverse=True,
        )
        self.lev_map = {
            pressure_level: index
            for index, pressure_level in enumerate(self.pressure_levels)
        }

    def _build_netcdf_variables(self) -> pd.DataFrame:
        """Agrupa los mensajes inventariados por su variable NetCDF final."""

        # Lectura de configuración meteorológica y revisión de la corrida
        local_definitions, center_remappings = (
            self._read_grib2_configurations()
        )
        self._validate_inventory()
        self._build_coordinates()

        # Los remapeos sustituyen el nombre NCEP dentro de `var_name`, que ya
        # conserva la agrupación g2ctl por presión, nivel y promedio.
        variable_rows = []
        for signature, messages in self.wgrib2_inventory.groupby(
            "parameter_signature", sort=False
        ):
            inventory_row = messages.iloc[0]
            discipline, category, parameter = (
                int(value) for value in signature.split("-")
            )
            remapping = center_remappings.get(signature)
            is_local = discipline in local_definitions["disciplines"] and (
                local_definitions["category_range"][0]
                <= category
                <= local_definitions["category_range"][1]
                or local_definitions["parameter_range"][0]
                <= parameter
                <= local_definitions["parameter_range"][1]
            )
            if is_local and remapping is None:
                logger.warning(
                    f"Parámetro local sin remapeo para {self.center}: firma {signature} se conserva definicion NCEP"
                )

            output = None if remapping is None else remapping["output"]
            output_name = inventory_row.short_name if output is None else output["name"]
            output_units = inventory_row.units if output is None else output["units"]
            factor = 1 if output is None else output.get("factor", 1)
            offset = 0 if output is None else output.get("offset", 0)
            if remapping is not None:
                self.wgrib2_inventory.loc[messages.index, "var_name"] = (
                    messages["var_name"].str.replace(
                        inventory_row.short_name.lower(), output_name.lower(), regex=False
                    )
                )

            for var_name, level in self.wgrib2_inventory.loc[
                messages.index, ["var_name", "level"]
            ].drop_duplicates("var_name").itertuples(index=False, name=None):
                variable_rows.append({
                    "var_name": var_name,
                    "is_pressure": self._match_pressure_level(level) is not None,
                    "output_units": output_units,
                    "factor": factor,
                    "offset": offset,
                    "remapping_applied": remapping is not None,
                })

        # FV3-GFS puede repetir APCP acumulado; ambos mensajes conservan el
        # mismo destino NetCDF, mientras la variable se define una sola vez.
        self.netcdf_variables = pd.DataFrame(variable_rows).drop_duplicates(
            "var_name", ignore_index=True
        )
        return self.netcdf_variables
