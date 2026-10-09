
"""Conversión de GRIB2 a NetCDF.

Esta versión separa los metadatos rápidos por archivo, el inventario de
mensajes y la definición de variables NetCDF.
"""

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
    El inventario extrae información de las variables directamente del archivo
    GRIB2, luego se agrupan en niveles isobaricos y nombran segun nomenclatura g2ctl;
    las reglas YAML remapean parámetros locales cuandocorresponde. 
    Se permite un subset de la información al definir un área, variables.

    Args:
        grib_files: Archivos GRIB2 de una misma corrida de modelo.
        model: nombre del modelo meteorológico.
        center: (ECMWF, NCEP) Centro productor usado por los remapeos YAML.
        configuration_yml: Configuración única del conversor, contiene los remapeos
        area: Área opcional `(west, south, east, north)` para el recorte geográfico.
        longitude_convention: Rango longitudinal del NetCDF final: `0_360` o `-180_180`.
        variables: Nombres finales exactos de las variables a convertir.
    """

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
        if len(grib_files) < 3:
            raise ValueError("Se requiere al menos de 3 archivos GRIB2 para conversión.")
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
        self.inventory: pd.DataFrame | None = None
        self.netcdf_variables: pd.DataFrame | None = None
        self.selected_variables: set[str] = set()
        self.forecast_date: datetime | None = None
        self.grid_template: int | None = None
        self.nx: int | None = None
        self.ny: int | None = None
        self.grib_file_valid_times: dict[str, datetime] = {}
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
        """Crea y llena el NetCDF final de una corrida de modelo."""

        # Metadatos rápidos y validación inicial de la corrida.
        self._validate_domain_times()

        # Obtener variables y agruparlas
        self._get_variable_inventory()
        self._build_netcdf_variables()

        # Iniciando netcdf
        file_name = f"{self.center}-{self.model}_{self.forecast_date:%Y%m%d}_{self.forecast_date:%H}Z.nc"
        netcdf_output = Path(output_dir) / file_name
        if netcdf_output.exists():
            raise RuntimeError(f"Ya existe el NetCDF: {netcdf_output.name}")

        netcdf_output.parent.mkdir(parents=True, exist_ok=True)
        dataset = self._create_netcdf(netcdf_output)
        try:
            self._write_grib_messages(dataset)
        except Exception as error:
            raise RuntimeError(f"Error al escribir los mensajes GRIB2 en {netcdf_output.name}: {error}") from error
        finally:
            dataset.close()

        logger.info(f"Conversión GRIB2 a NetCDF completada: {netcdf_output}")
        return netcdf_output

    # ------------------------------------------------------------------
    # Validación de metadatos
    # ------------------------------------------------------------------

    def _validate_domain_times(self) -> None:
        """Valida dominio, grilla y tiempos antes del inventario completo."""

        domain_times = self._get_domain_times()
        domain_times = domain_times.sort_values("valid_time").reset_index(drop=True)

        # Validaciones de consistencia entre archivos GRIB2
        if len(domain_times["forecast_date"].drop_duplicates()) != 1:
            raise RuntimeError(f"Existe más de una fecha de inicialización")
        if len(domain_times["domain"].drop_duplicates()) != 1:
            raise RuntimeError(f"No todos los archivos GRIB2 comparten el mismo dominio")
        if len(domain_times[["nx", "ny"]].drop_duplicates()) != 1:
            raise RuntimeError(f"Los archivos grib2 no tienen la misma resolución (distintos grid shapes)")
        if len(domain_times["grid_template"].drop_duplicates()) != 1:
            raise RuntimeError(f"Los archivos GRIB2 no comparten el mismo grid code")
        if len(domain_times) != len(domain_times["valid_time"].drop_duplicates()):
            raise RuntimeError(f"Existe archivos duplicados para una fecha")

        # Asignando Valores:
        self.forecast_date = domain_times["forecast_date"].iloc[0]
        self.domain = domain_times["domain"].iloc[0]
        self.grid_template = int(domain_times["grid_template"].iloc[0])
        self.nx = int(domain_times["nx"].iloc[0])
        self.ny = int(domain_times["ny"].iloc[0])
        self.time_list = domain_times["valid_time"].tolist()
        self.grib_files = [Path(x) for x in domain_times["grib_file"].tolist()]


        # creando relacion tiempo archivos
        self.time_map = {
            valid_time: index
            for index, valid_time in enumerate(self.time_list)
        }

        self.grib_file_valid_times = dict(
            zip(domain_times["grib_file"], domain_times["valid_time"])
        )


        # Verificaciones de área
        if self.area is None:
            return

        # Rectángulo geográfico del área.
        west, south, east, north = self.area
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("El área debe ser un rectángulo: -180 <= west < east <= 180 y -90 <= south < north <= 90.")
        area_geometry = box(west, south, east, north)

        # Rectángulo geográfico del dominio GRIB.
        domain_match = self._DOMAIN_LIMITS.fullmatch(self.domain)
        north, south, west, east = map(float, domain_match.group("north", "south", "west", "east"))
        domain_geometry = box(west, south, east, north)

        # Contención del área dentro del dominio.
        if not domain_geometry.covers(area_geometry):
            raise RuntimeError(f"El área solicitada no está contenida en el dominio {self.domain}")

    # ------------------------------------------------------------------
    # Wgrib2 executions and parsing
    # ------------------------------------------------------------------
    def _run_wgrib2_command(self, grib_file: Path, args: list[str]) -> str:
        """Ejecuta WGRIB2 con los argumentos indicados."""

        command = ["wgrib2", *args, str(grib_file)]

        try:
            result = sp.run(command, capture_output=True, text=True, check=True)
        except sp.CalledProcessError as error:
            detail = error.stderr.strip() or str(error)
            raise RuntimeError(f"WGRIB2 fallo para {grib_file.name}: {detail}") from error

        if not result.stdout.strip():
            raise RuntimeError(f"WGRIB2 no devolvió mensajes para {grib_file.name}")
        return result.stdout
    

    def _get_domain_times(self) -> pd.DataFrame:
        """Ejecuta WGRIB2 para obtener los tiempos y el domino de los archivos.

        El comando ejecutado es:

            wgrib2 -one_line -d 1 -T -VT -domain -nxny -grid {filename}
        
        -T: Es la fecha en la que se inicio el pronóstico (D=YYYYMMDDHHMMSS).
        -VT: Es la fecha para la que es válido el pronóstico (vt=YYYYMMDDHHMMSS).
        -domain: Extension de la data (N=%.6f S=%.6f W=%.6f E=%.6f).
        -nxny: tamaño de la grilla (nx, ny).
        -grid: código de la plantilla de grilla (grid_template=%d).
        """

        args = ['-one_line', '-d', '1', '-T', '-VT', '-domain', '-nxny','-grid']

        # Ejecuta WGRIB2 para cada archivo y acumula la salida
        rows = []
        for grib_file in self.grib_files:
            output = self._run_wgrib2_command(grib_file, args)

            # Parsea la salida de WGRIB2 para extraer los metadatos de cada archivo
            _, _, forecast_date, valid_time, domain, grid_size, grid_template, _ = output.split(":", 7)
            nx, ny = (int(value) for value in grid_size.strip("()").split(" x "))
            rows.append(
                {
                    "grib_file": str(grib_file),
                    "forecast_date": datetime.strptime(forecast_date.removeprefix("D="), "%Y%m%d%H%M%S"),
                    "valid_time": datetime.strptime(valid_time.removeprefix("vt="), "%Y%m%d%H%M%S"),
                    "grid_template": int(grid_template.removeprefix("grid_template=")),
                    "domain": domain,
                    "nx": nx,
                    "ny": ny
                }
            )
            
        return pd.DataFrame(rows)


    def _parse_wgrib2_var_output(self, output: str) -> list:
        """Interpreta la salida de wgrib2 con estas opciones:

            wgrib2 -names ncep -lev -lev0 -varX -ctl_inv {filename}

        -lev: nombre completo del nivel (surface, m above ground, etc)
        -lev0: sufijo del nivel (sfc, 2m, clm, etc)
        -varX: datos de variable var{discipline}_{master table}_{local table}_{center}_{parameter_category}_{parameter}
        -ctl_inv: 
        """


        rows = []
        for line in output.splitlines():
            if not line.strip():
                continue
            # La información esta separada por ":", asi que se divide
            message_id, _, level_name, level, var_data, ctl_inventory = line.split(":", 6)
            # extrayendo data de ctl_inventory:
            # short_name vertical_definition parameter_definition statistical_process long_name [units]
            short_name, vertical_definition, _, statistical_process, description = ctl_inventory.split(maxsplit=4) # ctl_inv
            surface_type, _, surface_values = vertical_definition.partition(",")
            
            match = re.match(r"^(.*?)\s*\[(.*?)\]\s*$", description) # description: long_name [units]
            long_name = match.group(1).strip()
            units = match.group(2).strip()
            
            # var_data : var{discipline}_{master table}_{local table}_{center}_{parameter_category}_{parameter}
            discipline, master_table, local_table, center, category, parameter = var_data.removeprefix('var').split('_')

            # Definiendo valores respecto a nivel
            surface_type = int(surface_type)
            is_isobaric = surface_type == 100
            level_suffix = 'prs' if is_isobaric else level
            level_name = 'Isobaric Levels' if is_isobaric else f'{level_name} ({level})'
            pressure_level = int(surface_values) // 100 if is_isobaric else None
            
            # construyendo varname_key, siguiendo logica de g2ctl
            varname_key = f"{short_name}//{statistical_process}//:{level_suffix}"

            rows.append(
                {
                    "message_id": int(message_id),
                    "varname_key": varname_key,
                    "short_name": short_name,
                    "long_name": long_name,
                    "units": units,
                    "is_isobaric": is_isobaric,
                    "level_suffix": level_suffix,
                    "level_name": level_name,
                    "pressure_level": pressure_level,
                    "surface_type": surface_type,
                    "surface_value": surface_values,
                    "statistical_process": statistical_process,
                    "parameter_signature": f"{discipline}-{category}-{parameter}",
                    "parameter_info": f"center: {center} | master_table: {master_table} | local_table: {local_table}",
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Agrupar variables según logica g2ctl
    # ------------------------------------------------------------------

    def _get_variable_inventory(self):
        """Ejecuta WGRIB2 para los 2 primeros y ultimo archivo, con esto se construye
        el dataframe de todas las variables y su metadata para saber que ingormacion 
        contienen los archivos GRIB2.

           wgrib2 -names ncep -lev -lev0 -varX -ctl_inv {filename}
        """
        # Lista de archivos a revisar
        files = self.grib_files[:2] + self.grib_files[-1:]

        # iterar archivos para obtener data
        inventory = []
        args = ['-names', 'ncep', '-lev', '-lev0', '-varX', '-ctl_inv']
        for file in files:
            output = self._run_wgrib2_command(file, args)
            inventory.extend(self._parse_wgrib2_var_output(output))

        self.inventory = pd.DataFrame(inventory)


    @staticmethod 
    def unique_or_join(series):
        values = series.dropna().drop_duplicates().tolist()
        return values[0] if len(values) == 1 else ", ".join(map(str, values))


    def _group_grib2_variables(self):
        """ se encarga de agrupar las variables obtenidas por el inventario
        las capas Isobaricas se usan como una solo variable con sufijo prs
        los nombres de variables se contruye:
            short_name + level_suffix
        en caso haya mas de una variable resultante con el mismo nombre se
        añade el proceso estadistico para diferenciarlo
            short_name + statical_process + level_suffix
        En caso aún persitan las repeticiones se falla por no poder diferenciar
        todas las variables.
        Esta logica es la que sigue g2ctl
        """
        inventory = self.inventory
        group_columns = ['parameter_signature', 'varname_key']
        groups = inventory.groupby(group_columns, sort=True).agg(self.unique_or_join).reset_index()

        # Nombre simplificado: elimina siempre el proceso estadístico.
        groups['base_var_name'] = groups['short_name'] + groups['level_suffix']

        # Decidir si statistical_process se mantiene en el nombre final de la variable
        name_collision = groups['base_var_name'].duplicated(keep=False) 
        process_required = name_collision & groups["statistical_process"].ne("none")
        groups['use_statistical'] = process_required
      
        # Creando nombre final
        groups['var_name'] = groups['base_var_name']
        # agregando proceso a quienes lo necesitan
        cols = ['short_name', 'statistical_process', 'level_suffix']
        groups.loc[process_required, 'var_name'] = groups.loc[process_required, cols].fillna('').sum(axis=1)

        # Si aún hay duplicados, el proceso estadístico no alcanza para distinguirlos.
        repeated_names = groups[groups['var_name'].duplicated(keep=False)][['var_name', 'parameter_signature', 'varname_key']]
        if not repeated_names.empty:
            raise RuntimeError( f"No se pudieron distinguir las variables GRIB2: {repeated_names.to_dict('records')}")
        
        # Los perfiles isobáricos se normalizan como "Isobaric Levels". Se conservan los grupos con una sola descripción vertical; 
        # los grupos no isobáricos con varias descripciones a variaciones 4D no consideradas, solo se considera variaciones Isobaricas
        groups['level_name_count'] = inventory.groupby(group_columns, sort=True)['level_name'].nunique().to_numpy()
        groups = groups[groups['level_name_count'].eq(1)]

        return groups.drop(columns = ['base_var_name','message_id','level_name_count'])

    # ------------------------------------------------------------------
    # Construir netcdf variables 
    # ------------------------------------------------------------------
    @staticmethod
    def _is_local_parameter(disciplines, categories, parameters, signature):
        discipline, category, parameter = map(int, signature.split("-"))
        is_local = discipline in disciplines and (
            categories[0] <= category <= categories[1]
            or parameters[0] <= parameter <= parameters [1]
        )
        return is_local


    def _apply_remappings(self, variables):
        """Lee archivo YAML con los remappings, y aplica los remappings a las variables
        modificando los datos necesarios
        """
        with self.configuration_yml.open(encoding="utf-8") as configuration_file:
            configuration = yaml.safe_load(configuration_file)
        # Leyendo grupos importantes del YAML
        local_definitions = configuration["local_definitions_reserved"]
        disciplines = local_definitions['disciplines']
        categories = local_definitions['category_range']
        parameters = local_definitions['parameter_range']
        self.remappings = configuration["remappings"][self.center]

        # Determinando si las variables son definiciones locales
        is_local = variables["parameter_signature"].apply(lambda x: self._is_local_parameter(disciplines, categories, parameters, x))

        # Añadiendo los remappings
        for key, remapping in self.remappings.items():
            id_key = variables['parameter_signature'] == key
            old_name = variables.loc[id_key, "short_name"].iloc[0]
            variables.loc[id_key, 'units'] = remapping['units']
            variables.loc[id_key, 'short_name'] = remapping['name']
            variables.loc[id_key, 'long_name'] = remapping['long_name']
            variables.loc[id_key, "var_name"] = variables.loc[id_key, "var_name"].str.replace(old_name, remapping['name'], regex=False)

        # Aviso de variables locales no remapeadas
        warning_keys = variables[is_local & ~variables['parameter_signature'].isin(self.remappings)]['parameter_signature'].unique().tolist()
        if warning_keys and self.center != 'ncep':
            logger.warning(f'Se usara la definición NCEP para los estos parametro locales: {warning_keys}')
        
        return variables


    def _build_netcdf_variables(self) -> pd.DataFrame:
        """Decide las variables se escribiran en el netCDF
        
        Agrupa la informacion en el GRIB2 según naming de g2ctl, luego
        aplica remapping y finalmente filtra de acuerdo a seleccion del 
        usuario
        """
        # Agrupando variables
        raw_variables = self._group_grib2_variables()
        variables = self._apply_remappings(raw_variables)
    
        # Pasando a minusculas los nombres
        variables["var_name"] = variables["var_name"].str.lower()

        # Verificando si hay colisiones de nombre
        repeated_names = variables.loc[variables['var_name'].duplicated(keep=False),['parameter_signature', 'var_name']]
        if not repeated_names.empty:
            raise RuntimeError(f"Colision de variables finales, revisar remappings: {repeated_names.to_dict('records')}")
        
        # Filtrar variables por seleccion del usuario
        if self.variables is not None:
            requested = pd.Index(self.variables)
            available = variables["var_name"]
            missing = requested[~requested.isin(available)]
            variables = variables.loc[available.isin(requested)].copy()
            
            # Detener la ejecución porque ninguna variable seleccionada esta presente
            if variables.empty:
                raise RuntimeError(f'Ninguna de las variables solicitadas estan presentes en los archivos GRIB2')
            # Aviso para variables no encontradas
            if not missing.empty:
                logger.warning("Variables no presentes en los GRIB2: %s", missing.tolist())

        # Creando map de niveles isobaricos
        if variables["is_isobaric"].any():
            self.pressure_levels = sorted(self.inventory["pressure_level"].dropna().unique(),reverse=True)
            self.lev_map = {pressure_level: index for index, pressure_level in enumerate(self.pressure_levels)}

        self.netcdf_variables = variables.reset_index(drop=True)
        self.selected_variables = set(self.netcdf_variables["var_name"])
        return self.netcdf_variables

    # ------------------------------------------------------------------
    # Crear estructura NetCDF
    # ------------------------------------------------------------------
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


    def _create_netcdf(self, netcdf_output: Path) -> Dataset:
        """Crea el NetCDF final con atributos, coordenadas y variables vacías.

        La dimensión `time` es ilimitada y su coordenada se escribe antes de las
        matrices. Las variables isobáricas usan cuatro dimensiones y las demás
        usan tres; todas las variables meteorológicas usan compresión y
        cuantización decimal.
        """

        # Inicia netCDF en modo escritura con atributos globales
        dataset = Dataset(netcdf_output, "w", format="NETCDF4")
        dataset.title = "Conversión GRIB2 a NetCDF"
        dataset.model = self.model
        dataset.center = self.center
        dataset.domain = self.domain
        dataset.forecast_date = self.forecast_date.isoformat()
        dataset.longitude_convention = self.longitude_convention

        # Se obtine coordendas de acuerdo a si hay subset o no
        latitude, longitude = self._prepare_netcdf_grid(self.grib_files[0])

        # Dimensiones espaciales, vertical y temporal del producto final.
        dataset.createDimension("time", None)
        if self.pressure_levels:
            dataset.createDimension("lev", len(self.pressure_levels))
        dataset.createDimension("latitude", len(latitude))
        dataset.createDimension("longitude", len(longitude))

        # Dimension tiempo
        time_coordinate = dataset.createVariable("time", "f8", ("time",))
        time_coordinate.units = "hours since 1800-01-01 00:00:00"

        # Dimension lev (Isobaric levels)
        if self.pressure_levels:
            lev_coordinate = dataset.createVariable("lev", "i2", ("lev",))
            lev_coordinate.units = "millibars"
            lev_coordinate[:] = self.pressure_levels

        # Dimension latitud
        latitude_coordinate = dataset.createVariable("latitude", "f4", ("latitude",))
        latitude_coordinate.units = "degrees_north"
        latitude_coordinate[:] = latitude

        # Dimension longitud
        longitude_coordinate = dataset.createVariable("longitude", "f4", ("longitude",))
        longitude_coordinate.units = "degrees_east"
        longitude_coordinate[:] = longitude

        # Variables meteorológicas según su estructura vertical.
        for variable in self.netcdf_variables.itertuples(index=False):
            pressure_var = variable.is_isobaric
            dimensions = ("time", "lev", "latitude", "longitude") if pressure_var else ("time", "latitude", "longitude")
            netcdf_variable = dataset.createVariable(variable.var_name, "f4", dimensions, zlib=True, least_significant_digit=2)
            
            netcdf_variable.units = variable.units
            netcdf_variable.long_name = f'{variable.long_name} at Isobaric levels' if pressure_var else f'{variable.long_name} at {variable.level_name}'
            netcdf_variable.surface_code = variable.surface_type
            netcdf_variable.surface_name = 'Isobaric levels' if pressure_var else variable.level_name
            netcdf_variable.parameter_info = variable.parameter_info
            netcdf_variable.parameter_signature = variable.parameter_signature
            netcdf_variable.statistical_process = variable.statistical_process.replace('none', 'instantanea')

            remapping = self.remappings.get(variable.parameter_signature)
            if remapping:
                netcdf_variable.remapping_applied = "true"
                netcdf_variable.remapping_factor = remapping['factor']
                netcdf_variable.remapping_offset = remapping['offset']

        return dataset

    # ------------------------------------------------------------------
    # Lectura archivos grib2 y escritura NetCDF
    # ------------------------------------------------------------------
    def _write_grib_messages(self, dataset: Dataset) -> None:
        """Escribe el eje temporal y las matrices GRIB en el NetCDF.
        
        PyGRIB abre cada archivo una vez para leer sus mensajes (data). Los
        índices geográficos y las posiciones temporal y vertical ya están
        preparados antes de iniciar esta escritura.
        """
        args = ["-names", "ncep", "-lev", "-lev0", "-varX", "-ctl_inv"]
        varname_map = self.netcdf_variables.set_index("varname_key")["var_name"]

        # La coordenada temporal extiende la dimensión ilimitada antes de escribir las variables.
        for valid_time, time_index in self.time_map.items():
            dataset["time"][time_index] = date2num(valid_time, dataset["time"].units)
        
        # iterar archivos gribfiles para leer y escribir en el netCDF final
        for grib_file in self.grib_files:
            # ejecutar wgrib2 para obtener detalle del GRIB2
            output = self._run_wgrib2_command(grib_file, args)
            # Generar Dataframe de la salida de wgrib2
            file_inventory = pd.DataFrame(self._parse_wgrib2_var_output(output))
            # Obtener la fecha de validez del pronostico en base al archivo
            file_inventory["valid_time"] = self.grib_file_valid_times[str(grib_file)]
            # Mapear varname en base a varname_key
            file_inventory["var_name"] = file_inventory["varname_key"].map(varname_map)
            # Filtrar para solo variables seleccionadas
            file_inventory = file_inventory.loc[file_inventory["var_name"].isin(self.selected_variables)]

            with pygrib.open(str(grib_file)) as source_grib:
                for inventory_row in file_inventory.itertuples(index=False):
                    grib_message = source_grib.message(inventory_row.message_id)
                    self._write_message(dataset, inventory_row, grib_message)

    def _write_message(self, dataset: Dataset, inventory_row, grib_message) -> None:
        """Selecciona, convierte cuando corresponde y escribe una matriz GRIB.
        
        La selección aplica el subset espacial y el orden longitudinal de las
        coordenadas NetCDF. Los remapeos YAML usan sólo factor y desplazamiento.
        Las variables isobáricas se escriben con dimensiones `time, lev,
        latitude, longitude`; las demás usan `time, latitude, longitude`.
        """

        variable_name = inventory_row.var_name
        remapping = self.remappings.get(inventory_row.parameter_signature)
        values = grib_message.values[np.ix_(self.latitude_indices, self.longitude_indices)]

        if remapping:
            values = values * remapping['factor'] + remapping['offset']

        time_index = self.time_map[inventory_row.valid_time]
        if inventory_row.is_isobaric:
            pressure_level = inventory_row.pressure_level
            lev_index = self.lev_map[pressure_level]
            dataset[variable_name][time_index, lev_index, :, :] = values
        else:
            dataset[variable_name][time_index, :, :] = values

