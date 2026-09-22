"""Inventario WGRIB2 para la conversión de GRIB2 a NetCDF."""

import logging
import re
import subprocess as sp
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pygrib
import yaml
from netCDF4 import Dataset, date2num
from shapely.geometry import box


logger = logging.getLogger(__name__)


class Grib2ToNetCDF:
    """Construye el inventario WGRIB2 de los mensajes de una corrida GRIB2.

    Inventaría todos los mensajes de los archivos ordenados y conserva el orden
    de cada archivo para asociarlo con la lectura secuencial de PyGRIB durante
    la escritura futura. No decodifica ni escribe matrices meteorológicas. La
    consolidación agrupa las variables NetCDF y resuelve sus remapeos YAML. La
    fase de estructura crea el único NetCDF final y obtiene sólo las
    coordenadas del primer mensaje PyGRIB.

    Args:
        grib_files: Archivos GRIB2 de una misma corrida meteorológica.
        model: Identificador del modelo usado para informar errores.
        center: Centro productor usado por los remapeos de fases posteriores.
        configuration_yml: Configuración única del conversor.
        area: Área opcional `(west, south, east, north)` para una fase
            de recorte geográfico.
        longitude_convention: Rango longitudinal del NetCDF final:
            `0_360` o `-180_180`.
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
        longitude_convention: str = "0_360",
    ) -> None:
        if not grib_files:
            raise ValueError("Se requiere al menos un archivo GRIB2 para construir el inventario.")
        if not model.strip():
            raise ValueError("Se requiere el identificador del modelo para construir el inventario.")
        if not center.strip():
            raise ValueError("Se requiere el centro productor para construir el inventario.")
        if longitude_convention not in {"0_360", "-180_180"}:
            raise ValueError("La convención longitudinal debe ser '0_360' o '-180_180'.")

        self.grib_files = sorted(Path(grib_file) for grib_file in grib_files)
        self.model = model.lower()
        self.center = center.lower()
        self.configuration_yml = Path(configuration_yml)
        self.area = area
        self.longitude_convention = longitude_convention
        self.wgrib2_inventory: pd.DataFrame | None = None
        self.netcdf_variables: pd.DataFrame | None = None
        self.time_list: list[datetime] = []
        self.time_map: dict[datetime, int] = {}
        self.pressure_levels: list[int] = []
        self.lev_map: dict[int, int] = {}
        self.domain: str | None = None
        self.latitude_indices: np.ndarray | None = None
        self.longitude_indices: np.ndarray | None = None

    def __str__(self) -> str:
        return f"Grib2ToNetCDF inventariando {len(self.grib_files)} archivos GRIB2"

    def __repr__(self) -> str:
        return f"<Grib2ToNetCDF con {len(self.grib_files)} archivos GRIB2>"

    def run_conversion(self, output_dir: str | Path) -> Path:
        """Crea la estructura del NetCDF final de una corrida meteorológica."""

        # Lectura de configuración, revisión de archivos e inventario WGRIB2
        self._build_inventory()
        self._build_netcdf_variables()

        # Construcción de coordenadas y estructura NetCDF
        reference_time = self.wgrib2_inventory["reference_time"].iloc[0]
        netcdf_output = Path(output_dir) / (
            f"{self.center}-{self.model}_{reference_time:%Y%m%d}_{reference_time:%H}Z.nc"
        )
        if netcdf_output.exists():
            raise RuntimeError(f"Ya existe el NetCDF final {netcdf_output.name} del modelo {self.model}.")

        netcdf_output.parent.mkdir(parents=True, exist_ok=True)
        dataset = self._create_netcdf(netcdf_output)
        dataset.close()

        logger.info("Estructura NetCDF completada para %s: %s", self.model, netcdf_output)
        return netcdf_output

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

    def _create_netcdf(self, netcdf_output: Path) -> Dataset:
        """Crea el NetCDF final, sus coordenadas y sus variables."""

        # Abriendo el NetCDF y añadiendo atributos
        dataset = Dataset(netcdf_output, "w", format="NETCDF4")
        reference_time = self.wgrib2_inventory["reference_time"].iloc[0]
        dataset.title = "Conversión GRIB2 a NetCDF"
        dataset.model = self.model
        dataset.center = self.center
        dataset.domain = self.domain
        dataset.reference_time = reference_time.isoformat()
        dataset.longitude_convention = self.longitude_convention

        latitude, longitude = self._prepare_netcdf_grid(self.grib_files[0])

        # Creando Dimensiones
        dataset.createDimension("time", len(self.time_list))
        dataset.createDimension("lev", len(self.pressure_levels))
        dataset.createDimension("latitude", len(latitude))
        dataset.createDimension("longitude", len(longitude))

        # Variable time
        time_coordinate = dataset.createVariable("time", "f8", ("time",))
        time_coordinate.units = "hours since 1800-01-01 00:00:00"
        time_coordinate[:] = date2num(self.time_list, time_coordinate.units)

        # Variable lev
        lev_coordinate = dataset.createVariable("lev", "i2", ("lev",))
        lev_coordinate.units = "millibars"
        lev_coordinate[:] = self.pressure_levels

        # Variable latitud
        latitude_coordinate = dataset.createVariable("latitude", "f4", ("latitude",))
        latitude_coordinate.units = "degrees_north"
        latitude_coordinate[:] = latitude

        # Variable longitud
        longitude_coordinate = dataset.createVariable("longitude", "f4", ("longitude",))
        longitude_coordinate.units = "degrees_east"
        longitude_coordinate[:] = longitude

        # Creando la variables para las demas
        for variable in self.netcdf_variables.itertuples(index=False):
            dimensions = ("time", "lev", "latitude", "longitude") if variable.is_pressure else ("time", "latitude", "longitude")
            netcdf_variable = dataset.createVariable(variable.var_name, "f4", dimensions, zlib=True)

            if variable.output_units is not None:
                netcdf_variable.units = variable.output_units
        return dataset

    def _prepare_netcdf_grid(self, grib_file: Path) -> tuple[np.ndarray, np.ndarray]:
        """Lee la grilla del primer GRIB y prepara las coordenadas NetCDF.

        Obtiene las coordenadas con `latlons()`, normaliza las longitudes
        según `longitude_convention`, calcula el orden de las columnas y
        aplica el área opcional. Conserva `latitude_indices` y
        longitude_indices` para que la escritura posterior recorte y
        reordene las matrices GRIB sin interpolación. Devuelve las coordenadas
        finales del NetCDF sin leer matrices meteorológicas.
        """

        # Lectura de coordenadas del primer mensaje GRIB.
        with pygrib.open(str(grib_file)) as source_grib:
            latitude, longitude = source_grib.message(1).latlons()
        latitude = latitude[:, 0]
        longitude = longitude[0, :]

        # Normalización de longitudes para el NetCDF final.
        if self.longitude_convention == "0_360":
            longitude = np.mod(longitude, 360)
        else:
            longitude = (longitude + 180) % 360 - 180

        # Orden de columnas de la matriz GRIB en la convención final.
        latitude_indices = np.arange(len(latitude))
        longitude_indices = np.argsort(longitude)
        ordered_longitude = longitude[longitude_indices]

        # Selección de la grilla solicitada por el usuario.
        if self.area is not None:
            west, south, east, north = self.area
            latitude_mask = (latitude >= south) & (latitude <= north)
            if self.longitude_convention == "0_360":
                west = west % 360
                east = east % 360
                longitude_mask = (
                    (ordered_longitude >= west) & (ordered_longitude <= east)
                    if west <= east
                    else (ordered_longitude >= west) | (ordered_longitude <= east)
                )
            else:
                longitude_mask = (ordered_longitude >= west) & (ordered_longitude <= east)
            latitude_indices = np.flatnonzero(latitude_mask)
            longitude_indices = longitude_indices[longitude_mask]
            if not len(latitude_indices) or not len(longitude_indices):
                raise RuntimeError(f"El área solicitada no contiene puntos de la malla del modelo {self.model}.")

        # Índices reutilizados durante la escritura de matrices.
        self.latitude_indices = latitude_indices
        self.longitude_indices = longitude_indices

        # Coordenadas finales del NetCDF.
        return latitude[latitude_indices], longitude[longitude_indices]

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
