"""Conversión de archivos GRIB2 a un único NetCDF."""

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
    """Convierte archivos GRIB2 en un único NetCDF.

    WGRIB2 interpreta los metadatos de los mensajes con nomenclatura NCEP usando
    wgrib2.PyGRIB lee las coordenadas y las matrices meteorológicas mediante. 
    El inventario define las variables, coordenadas y posiciones de
    escritura del NetCDF; las reglas YAML remapean parámetros locales cuando
    corresponde. Se permite un subset de la información al definir un área.

    Args:
        grib_files: Archivos GRIB2 de una misma corrida de modelo.
        model: nombre del modelo meteorológico.
        center: (ECMWF, NCEP) Centro productor usado por los remapeos YAML.
        configuration_yml: Configuración única del conversor, contiene los remapeos
        area: Área opcional `(west, south, east, north)` para el recorte geográfico.
        longitude_convention: Rango longitudinal del NetCDF final: `0_360` o `-180_180`.
        variables: Nombres finales exactos de las variables a convertir.
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
        variables: Sequence[str] | None = None,
    ) -> None:
        if not grib_files:
            raise ValueError("Se requiere al menos un archivo GRIB2 para conversión.")
        if not model.strip():
            raise ValueError("Se requiere el nombre del modelo.")
        if not center.strip():
            raise ValueError("Se requiere el centro de modelamiento.")
        if longitude_convention not in {"0_360", "-180_180"}:
            raise ValueError("La convención longitudinal debe ser '0_360' o '-180_180'.")

        self.grib_files = sorted(Path(grib_file) for grib_file in grib_files)
        self.model = model.lower()
        self.center = center.lower()
        self.configuration_yml = Path(configuration_yml)
        self.area = area
        self.longitude_convention = longitude_convention
        self.variables = None if variables is None else tuple(variables)
        self.wgrib2_inventory: pd.DataFrame | None = None
        self.netcdf_variables: pd.DataFrame | None = None
        self.selected_variables: set[str] = set()
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
        """Crea y llena el NetCDF final de una corrida de modelo.

        Args:
            output_dir: Directorio donde se crea el NetCDF final.

        Returns:
            Ruta del NetCDF creado.
        """

        # Inventario usando wgrib2 y definición de variables NetCDF.
        self._build_inventory()
        self._build_netcdf_variables()

        # Creación del NetCDF y preparación de sus coordenadas.
        reference_time = self.wgrib2_inventory["reference_time"].iloc[0]
        netcdf_output = Path(output_dir) / (
            f"{self.center}-{self.model}_{reference_time:%Y%m%d}_{reference_time:%H}Z.nc"
        )
        if netcdf_output.exists():
            raise RuntimeError(f"Ya existe el NetCDF final {netcdf_output.name} del modelo {self.model}.")

        netcdf_output.parent.mkdir(parents=True, exist_ok=True)
        dataset = self._create_netcdf(netcdf_output)
        try:
            # lectura de matrices en GRIB2 y escritura en el NetCDF final.
            self._write_grib_messages(dataset)
        finally:
            # El cierre libera recursos aunque la conversión no complete todas las matrices.
            dataset.close()

        logger.info(f"Conversión GRIB2 a NetCDF completada: {netcdf_output}")
        return netcdf_output

    # ------------------------------------------------------------------
    # Inventario WGRIB2
    # ------------------------------------------------------------------

    def _run_wgrib2_command(self, grib_file: Path) -> str:
        """Ejecuta WGRIB2 para obtener el inventario con nomenclatura NCEP de un archivo GRIB2."""

        command = ["wgrib2", "-names", "ncep", "-T", "-VT", "-domain", "-lev0", "-nxny", "-ctl_inv", str(grib_file)]

        try:
            result = sp.run(command, capture_output=True, text=True, check=True)
        except sp.CalledProcessError as error:
            detail = error.stderr.strip() or str(error)
            raise RuntimeError(f"WGRIB2 fallo para {grib_file.name}: {detail}") from error

        if not result.stdout.strip():
            raise RuntimeError(f"WGRIB2 no devolvió mensajes para {grib_file.name}")
        return result.stdout

    def _parse_wgrib2_output(self, grib_file: Path, output: str) -> pd.DataFrame:
        """Interpreta el inventario generado por WGRIB2.

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

        Devuelve una fila por mensaje con sus metadatos, nombre inicial, tiempo,
        nivel, dominio y tamaño de grilla.
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

            # Los niveles isobáricos comparten una variable vertical; los demás niveles forman parte del nombre.
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
        """Crea `wgrib2_inventory` con una fila por mensaje de la corrida."""
        inventory_frames = []

        # Verificación de los archivos GRIB2 de entrada.
        for grib_file in self.grib_files:
            if not grib_file.is_file():
                raise FileNotFoundError(f"No se encontró el archivo GRIB2 {grib_file} para el modelo {self.model}.")

        # Interpretación NCEP de los metadatos GRIB2.
        for grib_file in self.grib_files:
            output = self._run_wgrib2_command(grib_file)
            inventory_frames.append(self._parse_wgrib2_output(grib_file, output))

        # Cada archivo conserva su secuencia de mensajes dentro del inventario.
        self.wgrib2_inventory = pd.concat(inventory_frames, ignore_index=True)
        logger.info("Inventario WGRIB2 completado para %s: %s mensajes en %s archivos.", self.model, len(self.wgrib2_inventory), len(self.grib_files))

    # ------------------------------------------------------------------
    # Consolidación de variables NetCDF
    # ------------------------------------------------------------------

    @classmethod
    def _match_pressure_level(cls, level: str) -> re.Match[str] | None:
        """Reconoce niveles isobáricos textuales como `500mb`."""
        return cls._PRESSURE_LEVEL.fullmatch(level)

    def _read_grib2_configurations(self) -> tuple[dict, dict]:
        """Carga las definiciones locales y los remapeos YAML del centro productor."""

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
            center_remappings = {} if self.center == "ncep" else configuration["remappings"].get(self.center, {})
        except yaml.YAMLError as error:
            raise ValueError(f"La configuración YAML es inválida en {self.configuration_yml}") from error
        except (KeyError, TypeError) as error:
            raise ValueError(f"Falta o está mal definida una sección de {self.configuration_yml}: {error}") from error
        return local_definitions, center_remappings

    def _validate_inventory(self) -> None:
        """Valida una corrida homogénea y que el área de subset este contenida en el dominio."""

        # El inventario debe contener mensajes GRIB2.
        if self.wgrib2_inventory is None or self.wgrib2_inventory.empty:
            raise RuntimeError(f"Los archivos revisado no corresponden al formato grib2 o no contienen información")
        inventory = self.wgrib2_inventory
        reference_times = inventory["reference_time"].unique()
        domains = inventory["domain"].unique()
        grid_shapes = inventory[["nx", "ny"]].drop_duplicates()
        if len(reference_times) != 1:
            raise RuntimeError(f"No existe una sola fecha de inicializacion de la corrida de {self.model}")
        if len(domains) != 1:
            raise RuntimeError(f"No todos los archivos GRIB2 comparten el mismo dominio: {domains.tolist()}.")
        if len(grid_shapes) != 1:
            raise RuntimeError(f"Los archivos grib2 no tienen la misma resolución (distintos grid shapes)")

        self.domain = domains[0]
        # Validación geográfica del área solicitada.
        if self.area is None:
            return

        # Rectángulo geográfico del área.
        west, south, east, north = self.area
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(
                "El área debe ser un rectángulo: -180 <= west < east <= 180 y -90 <= south < north <= 90."
            )
        area_geometry = box(west, south, east, north)

        # Rectángulo geográfico del dominio GRIB.
        domain_match = self._DOMAIN_LIMITS.fullmatch(self.domain)
        north, south, west, east = map(float, domain_match.group("north", "south", "west", "east"))
        domain_geometry = box(west, south, east, north)

        # Contención del área dentro del dominio.
        if not domain_geometry.covers(area_geometry):
            raise RuntimeError(f"El área solicitada no está contenida en el dominio {self.domain}")

    def _build_coordinates(self) -> None:
        """Deriva las coordenadas temporal y vertical, junto con sus índices de escritura."""

        # Los tiempos válidos definen los índices temporales de escritura.
        self.time_list = sorted(self.wgrib2_inventory["valid_time"].unique())
        self.time_map = {valid_time: index for index, valid_time in enumerate(self.time_list)}

        # Los niveles isobáricos se ordenan de mayor a menor presión.
        self.pressure_levels = sorted(
            {
                int(match.group(1))
                for level in self.wgrib2_inventory.loc[
                    self.wgrib2_inventory["var_name"].isin(self.selected_variables), "level"
                ]
                if (match := self._match_pressure_level(level))
            },
            reverse=True,
        )
        self.lev_map = {
            pressure_level: index
            for index, pressure_level in enumerate(self.pressure_levels)
        }

    def _create_netcdf(self, netcdf_output: Path) -> Dataset:
        """Crea el NetCDF final con atributos, coordenadas y variables vacías.

        La dimensión `time` es ilimitada y su coordenada se escribe antes de las
        matrices. Las variables isobáricas usan cuatro dimensiones y las demás
        usan tres; todas las variables meteorológicas usan compresión y
        cuantización decimal.
        """

        # Atributos que identifican la corrida y la convención longitudinal.
        dataset = Dataset(netcdf_output, "w", format="NETCDF4")
        reference_time = self.wgrib2_inventory["reference_time"].iloc[0]
        dataset.title = "Conversión GRIB2 a NetCDF"
        dataset.model = self.model
        dataset.center = self.center
        dataset.domain = self.domain
        dataset.reference_time = reference_time.isoformat()
        dataset.longitude_convention = self.longitude_convention

        latitude, longitude = self._prepare_netcdf_grid(self.grib_files[0])

        # Dimensiones espaciales, vertical y temporal del producto final.
        dataset.createDimension("time", None)
        if self.pressure_levels:
            dataset.createDimension("lev", len(self.pressure_levels))
        dataset.createDimension("latitude", len(latitude))
        dataset.createDimension("longitude", len(longitude))

        # Coordenada temporal de longitud ilimitada.
        time_coordinate = dataset.createVariable("time", "f8", ("time",))
        time_coordinate.units = "hours since 1800-01-01 00:00:00"

        # Coordenada vertical isobárica, si existen variables 4D.
        if self.pressure_levels:
            lev_coordinate = dataset.createVariable("lev", "i2", ("lev",))
            lev_coordinate.units = "millibars"
            lev_coordinate[:] = self.pressure_levels

        # Coordenada latitudinal.
        latitude_coordinate = dataset.createVariable("latitude", "f4", ("latitude",))
        latitude_coordinate.units = "degrees_north"
        latitude_coordinate[:] = latitude

        # Coordenada longitudinal.
        longitude_coordinate = dataset.createVariable("longitude", "f4", ("longitude",))
        longitude_coordinate.units = "degrees_east"
        longitude_coordinate[:] = longitude

        # Variables meteorológicas según su estructura vertical.
        for variable in self.netcdf_variables.itertuples(index=False):
            dimensions = ("time", "lev", "latitude", "longitude") if variable.is_pressure else ("time", "latitude", "longitude")
            netcdf_variable = dataset.createVariable(variable.var_name, "f4", dimensions, zlib=True, least_significant_digit=2)

            if variable.output_units is not None:
                netcdf_variable.units = variable.output_units
            netcdf_variable.long_name = variable.long_name
            netcdf_variable.parameter_signature = variable.parameter_signature
            netcdf_variable.wgrib2_short_name = variable.short_name
            if variable.remapping_applied:
                netcdf_variable.remapping_applied = "true"
                netcdf_variable.remapping_factor = variable.factor
                netcdf_variable.remapping_offset = variable.offset
        return dataset

    def _prepare_netcdf_grid(self, grib_file: Path) -> tuple[np.ndarray, np.ndarray]:
        """Lee la grilla del primer GRIB y prepara las coordenadas NetCDF.

        Obtiene las coordenadas con `latlons()`, normaliza las longitudes
        según `longitude_convention`, calcula el orden de las columnas y
        aplica el área opcional. Conserva `latitude_indices` y
        `longitude_indices` para que la escritura posterior recorte y
        reordene las matrices GRIB sin interpolación. Devuelve las coordenadas
        finales del NetCDF sin leer matrices meteorológicas.
        """

        # Coordenadas del primer mensaje GRIB.
        with pygrib.open(str(grib_file)) as source_grib:
            latitude, longitude = source_grib.message(1).latlons()
        latitude = latitude[:, 0]
        longitude = longitude[0, :]

        # Conversión de longitudes a la convención elegida para el producto.
        if self.longitude_convention == "0_360":
            longitude = np.mod(longitude, 360)
        else:
            longitude = (longitude + 180) % 360 - 180

        # Índices de columnas que ordenan coordenadas y matrices con la misma longitud.
        latitude_indices = np.arange(len(latitude))
        longitude_indices = np.argsort(longitude)
        ordered_longitude = longitude[longitude_indices]

        # Selección de los puntos de la grilla solicitada.
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

        # Índices geográficos aplicados a cada matriz decodificada.
        self.latitude_indices = latitude_indices
        self.longitude_indices = longitude_indices

        # Coordenadas finales del NetCDF.
        return latitude[latitude_indices], longitude[longitude_indices]

    # ------------------------------------------------------------------
    # Lectura archivos grib2 y escritura NetCDF
    # ------------------------------------------------------------------

    def _write_grib_messages(self, dataset: Dataset) -> None:
        """Escribe el eje temporal y las matrices GRIB en el NetCDF.

        PyGRIB abre cada archivo una vez para leer sus mensajes (data). Los
        índices geográficos y las posiciones temporal y vertical ya están
        preparados antes de iniciar esta escritura.
        """

        # La coordenada temporal extiende la dimensión ilimitada antes de escribir las variables.
        for valid_time, time_index in self.time_map.items():
            dataset["time"][time_index] = date2num(
                valid_time, dataset["time"].units
            )

        for grib_file in self.grib_files:
            file_inventory = self.wgrib2_inventory.loc[
                self.wgrib2_inventory["grib_file"] == str(grib_file)
            ]

            # lectura secuencial de los mensajes del archivo GRIB2.
            with pygrib.open(str(grib_file)) as source_grib:
                for message_index, grib_message in enumerate(source_grib):
                    inventory_row = file_inventory.iloc[message_index]
                    if inventory_row.var_name not in self.selected_variables:
                        continue
                    self._write_message(dataset, inventory_row, grib_message)

    def _write_message(self, dataset: Dataset, inventory_row: pd.Series, grib_message) -> None:
        """Selecciona, convierte cuando corresponde y escribe una matriz GRIB.

        La selección aplica el subset espacial y el orden longitudinal de las
        coordenadas NetCDF. Los remapeos YAML usan sólo factor y desplazamiento.
        Las variables isobáricas se escriben con dimensiones `time, lev,
        latitude, longitude`; las demás usan `time, latitude, longitude`.
        """

        variable_name = inventory_row.var_name
        valid_time = inventory_row.valid_time
        pressure_match = self._match_pressure_level(inventory_row.level)
        conversion = self.netcdf_variables.loc[self.netcdf_variables["var_name"] == variable_name].iloc[0]

        # Subset espacial y orden longitudinal definidos por las coordenadas NetCDF.
        values = grib_message.values[np.ix_(self.latitude_indices, self.longitude_indices)]

        # Factor y desplazamiento definidos para el parámetro remapeado.
        if conversion.remapping_applied:
            values = values * conversion.factor + conversion.offset

        # Variables isobáricas usan tiempo y nivel; las demás usan sólo tiempo.
        time_index = self.time_map[valid_time]
        if pressure_match is not None:
            pressure_level = int(pressure_match.group(1))
            lev_index = self.lev_map[pressure_level]
            dataset[variable_name][time_index, lev_index, :, :] = values
        else:
            dataset[variable_name][time_index, :, :] = values

    def _build_netcdf_variables(self) -> pd.DataFrame:
        """Construye `netcdf_variables` a partir de parámetros y remapeos YAML.

        Cada fila contiene el nombre final, la estructura vertical, las unidades,
        el factor, el desplazamiento y el estado de remapeo de una variable
        meteorológica.
        """

        # Definiciones meteorológicas y validación de la corrida.
        local_definitions, center_remappings = (
            self._read_grib2_configurations()
        )
        self._validate_inventory()

        # Los remapeos sustituyen el nombre NCEP y conservan nivel y proceso estadístico.
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
            long_name = inventory_row.description if output is None else output["long_name"]
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
                    "long_name": long_name,
                    "parameter_signature": signature,
                    "short_name": inventory_row.short_name,
                    "factor": factor,
                    "offset": offset,
                    "remapping_applied": remapping is not None,
                })

        # FV3-GFS puede repetir APCP acumulado; ambos mensajes conservan el
        # mismo destino NetCDF, mientras la variable se define una sola vez.
        self.netcdf_variables = pd.DataFrame(variable_rows).drop_duplicates(
            "var_name", ignore_index=True
        )

        # La selección usa los nombres finales, después de los remapeos YAML.
        if self.variables is not None:
            available_variables = set(self.netcdf_variables["var_name"])
            for variable_name in self.variables:
                if variable_name not in available_variables:
                    logger.warning(
                        "La variable final solicitada %s no está disponible en los archivos GRIB2.",
                        variable_name,
                    )
            self.netcdf_variables = self.netcdf_variables.loc[
                self.netcdf_variables["var_name"].isin(self.variables)
            ].reset_index(drop=True)
            if self.netcdf_variables.empty:
                raise RuntimeError(
                    f"El filtro de variables no contiene variables disponibles para el modelo {self.model}."
                )

        self.selected_variables = set(self.netcdf_variables["var_name"])
        self._build_coordinates()
        return self.netcdf_variables
