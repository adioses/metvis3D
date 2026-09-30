# Plan de implementación: conversión GRIB2 a NetCDF

## Propósito y uso continuo

Implementar una clase que convierta todos los mensajes de una corrida y modelo
GRIB2 en un único NetCDF final. La clase no interpola, no rellena vacíos y no
crea productos parciales por variable ni por tiempo.

WGRIB2 inventaría los mensajes, resuelve la codificación que interesa al flujo
y determina su nomenclatura NCEP. La fase 3 usa PyGRIB sólo para obtener las
coordenadas del primer mensaje; la fase 4 lo abre una vez por archivo para
leer las matrices de valores que se escribirán en NetCDF. No se usará CFGRIB
ni Xarray.

Este documento es el contexto operativo acumulativo del conversor. Debe leerse
al iniciar cada conversación de implementación y actualizarse al terminar una
fase, una decisión o una verificación. Así evita que un chat nuevo reabra
acuerdos ya definidos o dé por implementado trabajo que aún está pendiente.

Cada fase debe precisarse y aprobarse antes de implementarla. El documento
registra el contrato y las verificaciones; el código operativo reside en
`src/standardize/grib2_to_netcdf.py`.

## Estado de implementación

**Última actualización:** 2026-09-23
**Fase activa:** 5. Verificación científica y operación.
**Estado global:** las fases de contrato, inventario WGRIB2, consolidación de
variables, estructura NetCDF y escritura de matrices están verificadas. La
selección de variables finales y sus atributos de procedencia forman parte de
la fase 4 verificada. La verificación científica de los campos convertidos
continúa en la fase 5.

| Fase | Estado | Resultado verificable | Próximo paso |
|---|---|---|---|
| 0. Contrato de ejecución y YAML | Verificada | Interfaz y YAML inicial aprobados | Iniciar la fase 1 con el inventario WGRIB2. |
| 1. Inventario WGRIB2 | Verificada | Inventario completo de GFS y ECMWF, en orden por archivo | Consolidar variables, tiempos y niveles. |
| 2. Plan de variables y nombres | Verificada | Nombres finales, remapeos, tiempos y niveles de GFS y ECMWF | Crear la estructura NetCDF y preparar el subset. |
| 3. NetCDF y subset | Verificada | Estructura, coordenadas e índices de recorte verificables | Leer matrices y escribir el NetCDF final. |
| 4. Escritura con PyGRIB | Verificada | Una pasada PyGRIB por archivo, selección final y atributos NetCDF para GFS y ECMWF | Iniciar la verificación científica de los campos escritos. |
| 5. Verificación científica | Pendiente | Casos GFS y ECMWF documentados | Verificar los campos convertidos contra sus fuentes GRIB2. |

Estados permitidos: `Pendiente`, `En definición`, `En implementación`,
`Verificada` o `Bloqueada`. Un estado `Verificada` exige el criterio de cierre
de su fase y una evidencia enlazable: prueba, salida reproducible o documento.

## Registro acumulativo de acuerdos

Las entradas se agregan al final de esta tabla; no se reescriben acuerdos
históricos. Si una decisión cambia, se añade una nueva entrada que indique cuál
sustituye. Las decisiones de este conversor se registran exclusivamente en
este documento.

| Fecha | Estado | Acuerdo o decisión | Impacto en el diseño |
|---|---|---|---|
| 2026-09-19 | Acordado | WGRIB2 inventaría y resuelve los nombres NCEP; PyGRIB lee matrices de valores una sola vez por archivo. | No hay pasada PyGRIB previa de metadatos ni comprobación independiente de conteos. |
| 2026-09-19 | Acordado | Se inventarían todos los mensajes; no existe selección previa de variables. | El YAML sólo clasifica parámetros locales y remapea casos aprobados. |
| 2026-09-19 | Acordado | La asociación WGRIB2–PyGRIB es por posición dentro de cada archivo. | El inventario debe conservar archivo y posición de mensaje. |
| 2026-09-19 | Acordado | Los remapeos conservan el nivel original y sólo reemplazan el nombre base y, opcionalmente, unidades mediante factor/desplazamiento. | `0-6-192` de ECMWF puede generar `TCDC` y multiplicarse por 100. |
| 2026-09-19 | Pendiente | Definir la unidad final de `pressure`: Pa según el estándar o hPa como la referencia. | Afecta el eje vertical y la documentación, no la agrupación de perfiles. |
| 2026-09-21 | Acordado | La interfaz recibe `grib_files`, `model`, `center`, `configuration_yml` y `area`; `center` y `model` se normalizan a minúsculas y no se verifican contra los GRIB. `run_conversion` recibe `output_dir`. | El nombre final es `{center}-{model}_{YYYYmmdd}_{HH}Z.nc`, con la inicialización común de la corrida GRIB. |
| 2026-09-21 | Acordado | El YAML único es `config/grib2-definitions.yaml`. Para las disciplinas trabajadas 0, 1, 2, 3, 4 y 10, clasifica como locales las categorías o parámetros 192–254; las disciplinas 20 y 191 no se procesan. `name` y `units` son obligatorios, mientras `factor` y `offset` toman 1 y 0 por defecto. | Sólo una combinación incluida en la regla local puede recibir un remapeo; sin regla se advierte y se conserva el nombre WGRIB2. |
| 2026-09-21 | Acordado | El código local ECMWF `0-1-193` se remapea a `APCP` con unidad objetivo `mm`, sin `factor` ni `offset` por ahora. | La conversión numérica de la fuente a milímetros queda pendiente antes de usar el campo como producto científico. |
| 2026-09-21 | Acordado | El área usa `(west, east, south, north)`, admite cruce del antimeridiano y se ajusta a puntos de malla más próximos. Las longitudes finales se normalizan y ordenan en `-180..180`. | El área debe estar íntegramente contenida en el dominio fuente; no hay interpolación. |
| 2026-09-21 | Acordado | Los campos no isobáricos conservan las dimensiones `(time, latitude, longitude)`, incluso cuando sólo haya dato para un tiempo. La salida existente no se sobrescribe y un NetCDF fallido se conserva para análisis. | Las posiciones temporales sin mensaje no se escriben. |
| 2026-09-21 | Diferida | La unidad final de `pressure` se decidirá durante la fase 3 al implementar la inicialización NetCDF, usando inspecciones adicionales. | No bloquea la fase 0 ni modifica aún el estándar de datos. |
| 2026-09-21 | Verificada | La fase 1 se implementó en `src/standardize/grib2_to_netcdf.py`. Ejecuta WGRIB2 una vez por archivo con `-names ncep -T -VT -domain -lev0 -nxny -ctl_inv`, conserva el orden por archivo y no lee matrices. | La asociación futura con PyGRIB usa el orden de las filas, sin columna de posición explícita. La ejecución manual con WGRIB2 3.8.0 inventarió 44 mensajes GFS y 246 ECMWF. |
| 2026-09-21 | Acordado | El inventario conserva `var_name`, disciplina, categoría, parámetro, nivel textual, proceso estadístico, tiempos, dominio, `nx`, `ny`, descripción y unidades. La definición vertical interna de `ctl_inv` se descarta. | El nivel textual de `-lev0` será la única representación vertical disponible para la fase 2. |
| 2026-09-21 | Acordado | La salida controlada de WGRIB2 se interpreta como ocho segmentos separados por `:`, con `ctl_inv` como último segmento. La terna disciplina-categoría-parámetro se toma de sus tres primeros componentes; un cuarto componente local no interviene. | El análisis es directo y sigue la estructura de la salida g2ctl, sin añadir `-varX`, `-ftime`, `-lev`, `-scan` ni `-grid`. |
| 2026-09-21 | Acordado | La clave vigente de una salida de `remappings` es `output.name`; `output.ncep_name` era una referencia obsoleta. | La fase 2 aplicará `output.name` al construir el nombre final. |
| 2026-09-21 | Acordado | Este conversor no incorpora pruebas automatizadas. Las verificaciones se documentan como ejecuciones manuales reproducibles en este plan. | No se crearán archivos de pruebas para el conversor ni se exigirá ese entregable en la fase 5. |
| 2026-09-21 | Acordado | El análisis, la revisión y la discusión de diseño no autorizan cambios. Sólo se implementa o modifica código, configuración o documentación cuando el usuario lo indique explícitamente. | Antes de una instrucción explícita, el trabajo se limita a lectura, diagnóstico y propuesta; no se alteran archivos del proyecto. |
| 2026-09-21 | Verificada | Sustituye la enumeración previa del inventario: la fase 1 compacta la identidad de parámetro como `parameter_signature` y construye el nombre NCEP inicial con `wgrib2_name` y `netcdf_suffix`; ya no conserva disciplina, categoría, parámetro ni proceso estadístico como columnas independientes. | El inventario conserva sólo los campos requeridos para asociar mensajes y consolidar variables, sin metadatos redundantes. |
| 2026-09-21 | Verificada | Los inventarios completos de grillas enteras registraron 32,631 mensajes en 129 archivos GFS (110.68 s) y 11,313 mensajes en 66 archivos ECMWF (288.28 s). | La evidencia sustituye las muestras reducidas previas y confirma el orden de mensajes de cada archivo. |
| 2026-09-21 | Verificada | La fase 2 agrupa mensajes por `parameter_signature`, resuelve remapeos una sola vez por variable y construye `netcdf_variables` con nombre final, unidades, factor, offset y estado de remapeo. La ejecución manual consolidó 56 variables, 129 tiempos y 26 niveles GFS; y 49 variables, 65 tiempos y 13 niveles ECMWF. | `wgrib2_inventory` conserva el nombre final por mensaje; la conversión se conserva por variable y se aplicará durante la escritura. |
| 2026-09-21 | Acordado | Sustituye la regla temporal sin validación de intervalos: la disponibilidad se declara por modelo y tramo en `forecast_availability`. Cada plazo y cada intervalo entre plazos debe pertenecer a la disponibilidad del tramo correspondiente, sin exigir una cadencia única para toda la corrida. | GFS y ECMWF pueden usar cadencias variables autorizadas sin completar plazos ni inferir datos ausentes. |
| 2026-09-21 | Acordado | Sustituye el acuerdo anterior sobre el área: la validación previa al NetCDF exige una única hora de referencia, dominio y tamaño de grilla. El área es un rectángulo continuo en coordenadas geográficas: `-180 <= west < east <= 180` y `-90 <= south < north <= 90`, contenido en el dominio normalizado por WGRIB2. | No se admiten áreas que crucen el antimeridiano; Shapely comprueba su contención antes de iniciar la escritura. |
| 2026-09-21 | Acordado | Sustituye la unidad vertical diferida: la fase 3 usará la dimensión `lev`, con niveles isobáricos descendentes y unidad `millibars`, igual que la referencia. | El inventario de fase 2 ya entrega los niveles y su índice para crear el eje vertical. |
| 2026-09-21 | Acordado | WGRIB2 normaliza los límites del dominio a `-180..180`, mientras PyGRIB puede entregar longitudes nativas en `0..360`. | Antes del subset, la fase 3 normalizará y reordenará conjuntamente longitudes, coordenadas y columnas de datos a `-180..180`. |
| 2026-09-22 | Acordado | El área de usuario será siempre un rectángulo continuo en `-180..180` y `-90..90`, con `west < east` y `south < north`; no se admiten áreas que crucen el antimeridiano. | La fase 2 valida el bbox y su contención con Shapely. La fase 3 sólo normaliza y reordena grillas PyGRIB nativas en `0..360` antes de calcular sus índices. |
| 2026-09-22 | Acordado | Sustituye las columnas compactas previas: el inventario conserva `short_name` con la definición NCEP y `var_name` con la agrupación g2ctl. Los remapeos reemplazan `short_name` dentro de `var_name`; no existe `netcdf_suffix` ni una columna separada de nombre NetCDF. | La fase 2 conserva `var_name` como identificador final tanto por mensaje como en `netcdf_variables`. |
| 2026-09-22 | Acordado | `area` usa el orden de bbox `(west, south, east, north)`, igual que `shapely.box`. | La validación construye primero el bbox del área, después el dominio WGRIB2 y finalmente comprueba su contención. |
| 2026-09-22 | Implementado | Sustituye la validación de disponibilidad temporal: el usuario es responsable de entregar los GRIB sin plazos faltantes. El conversor conserva todos los tiempos válidos únicos que entregue WGRIB2, sin comprobar cadencia, rango ni intervalos. | Se retiró `forecast_availability` del YAML y de `src/standardize/grib2_to_netcdf.py`; el eje `time` se construye directamente desde `valid_time`. |
| 2026-09-22 | Verificada | Se verificó la fase 2 en el contenedor Docker `dev`, con el entorno `metvis3d`: un inventario en memoria con tiempos irregulares conserva su eje temporal y consolida variables; el remapeo ECMWF `0-6-192` genera `tcdcclm`, unidad `%` y factor 100. | La consolidación de variables, los ejes de tiempo y presión, los remapeos y la responsabilidad temporal del usuario cumplen el criterio de cierre de la fase 2. |
| 2026-09-22 | Acordado | Sustituye la inicialización horizontal diferida: la fase 3 abre sólo el primer GRIB, obtiene `latlons()` de su primer mensaje y no lee matrices meteorológicas. | `_prepare_netcdf_grid()` crea las coordenadas horizontales y conserva los índices que la fase 4 aplicará a todas las matrices. |
| 2026-09-22 | Acordado | Sustituye la salida longitudinal única `-180..180`: el constructor recibe `longitude_convention`, con `0_360` como valor predeterminado y `-180_180` como alternativa. El área de usuario continúa en EPSG:4326 `-180..180`. | Las coordenadas y las columnas GRIB se normalizan y ordenan según la convención elegida; el NetCDF registra la convención en un atributo global. |
| 2026-09-22 | Acordado | Las fuentes controladas se tratan como grillas geográficas rectangulares; no se repite un contraste entre `nx`/`ny` inventariado y `latlons()`, ni se valida su rectangularidad en la fase 3. | El inventario ya garantiza una única resolución por corrida; una grilla con otra geometría requerirá un acuerdo previo antes de ser admitida. |
| 2026-09-22 | Verificada | La fase 3 se implementó en `src/standardize/grib2_to_netcdf.py`: `_create_netcdf()` crea dimensiones, coordenadas, atributos y variables; `_prepare_netcdf_grid()` normaliza, ordena y recorta la grilla, conservando índices de matriz. En Docker `dev` se verificaron GFS y ECMWF reales, ambas convenciones longitudinales, con y sin área; la estructura NetCDF se verificó en memoria sin crear productos temporales. | La fase 4 sólo leerá matrices PyGRIB y las escribirá usando los índices geográficos preparados. |
| 2026-09-23 | Acordado | Todas las variables meteorológicas creadas por `_create_netcdf()` usarán compresión `zlib` y `least_significant_digit=2`; las coordenadas conservarán su representación actual. | La cuantización decimal reduce el volumen y costo de escritura, y permite comparar el rendimiento con la referencia que emplea la misma opción. La fase 4 se medirá primero con cinco GRIB GFS usando Python 3.11. |
| 2026-09-23 | Verificada | La muestra GFS de cinco archivos (`f000`–`f012`) con área `(-130, -57, -10, 30)` y convención `0_360` escribió 1,259 mensajes en un único NetCDF de 196 MiB. En Python 3.11 del contenedor, el inventario WGRIB2 tomó 3.88 s, la lectura PyGRIB y escritura 11.16 s y la corrida completa 22.45 s. | El NetCDF contenía los cinco tiempos y `tmp2m` con zlib y `least_significant_digit=2`; frente al GRIB `f000`, su diferencia máxima absoluta fue 0.003662 K, dentro de la cuantización acordada. Sus productos se eliminaron antes del benchmark completo. |
| 2026-09-23 | Verificada | Las comparaciones de `tmp2m` en `f000` mostraron el GRIB de extensión completa, el rectángulo solicitado y el NetCDF convertido para GFS y ECMWF. GFS fuente cubre 216–354°E y 70°S–30°N, por lo que el subset 230–350°E y 57°S–30°N conserva gran parte de su dominio; ECMWF parte de la grilla global. | No hay remuestreo: la coincidencia se obtiene con selección de índices y reordenamiento longitudinal. La diferencia máxima absoluta fue 0.003662 K para la muestra GFS cuantizada y 0.000015 K para el NetCDF ECMWF existente. Sus figuras se eliminaron antes del benchmark completo. |
| 2026-09-23 | Acordado | El benchmark GFS usa los archivos que coinciden con `data/raw/GFS27/gfs*.fNNN` y escribe exclusivamente en `data/standardized/benchmark/`, sin sufijo de fecha. Por defecto toma los 129 archivos, mientras `--file-count` permite una muestra inicial controlada. Su `ncep-gfs_benchmark.log` registra una línea `INVENTORY` y una `CONVERT` por archivo, con duración, acumulado, promedio, ETA y número de mensajes. | El producto previo se elimina manualmente antes de una nueva corrida; el archivo final conserva el nombre normal del conversor dentro de la carpeta de benchmark. El log permite seguir y comparar la ejecución con la referencia. |
| 2026-09-23 | Verificada | La fase 4 se implementó en `src/standardize/grib2_to_netcdf.py`. `_write_grib_messages()` escribe primero la coordenada `time` de dimensión ilimitada y recorre una vez los mensajes de cada archivo; `_write_message()` selecciona y reordena cada matriz con los índices de fase 3, aplica sólo `factor + offset` cuando existe remapeo y la escribe según su estructura 3D o 4D. | La dimensión temporal no hace crecer los chunks con la duración completa de la corrida. El NetCDF se cierra aun si la conversión falla y queda disponible para análisis. |
| 2026-09-23 | Verificada | Amplía el benchmark inicialmente definido para GFS: admite cualquier combinación de centro y modelo mediante sus argumentos de entrada y nombra el log como `<center>-<model>_benchmark.log`. Las corridas completas produjeron `ncep-gfs_20260903_00Z.nc` desde 129 archivos GFS en 39.90 min, y `ecmwf-ecmwf_20260903_00Z.nc` desde 65 archivos ECMWF globales en 7.15 min. | Los NetCDF y sus logs quedaron en `data/standardized/benchmark/` como evidencia operativa reproducible. La comprobación científica de los valores se realizará en la fase 5. |
| 2026-09-23 | Implementado | El constructor admite opcionalmente una secuencia de nombres finales exactos de variables. El inventario WGRIB2 y el eje `time` permanecen completos; tras resolver los remapeos YAML se filtra el plan NetCDF, PyGRIB recorre todos los mensajes por posición y sólo decodifica/escribe matrices seleccionadas. | Los parámetros locales ECMWF se remapean para formar variables meteorológicas estandarizadas finales; la selección usa exclusivamente esos nombres, no códigos locales ni nombres intermedios. Cada nombre solicitado ausente genera una advertencia y sólo se detiene si el filtro no conserva ninguna variable. Si no quedan campos isobáricos se omiten `lev` y su coordenada. |
| 2026-09-23 | Implementado | Cada variable NetCDF conserva `long_name`, `parameter_signature` y `wgrib2_short_name`. Los remapeos añaden `remapping_applied`, `remapping_factor` y `remapping_offset`; su `long_name` procede de `output.long_name` en YAML. | Las descripciones de `TCDC` y `APCP` se declaran temporalmente en YAML y deberán actualizarse cuando se apruebe su nomenclatura final. Las variables sin remapeo usan la descripción extraída de WGRIB2 como `long_name`. |
| 2026-09-23 | Implementado | El benchmark acepta opcionalmente `--variables-yml`, carga `selected_variables` y las entrega al conversor. Su lectura temporizada conserva el conteo completo de mensajes por archivo y omite las matrices no seleccionadas antes de acceder a `values`. | El tiempo de inventario y el número de mensajes informados permanecen comparables con el benchmark completo; el tiempo `CONVERT` mide la reducción de decodificación, subset y escritura de la selección. |
| 2026-09-23 | Verificada | La muestra ECMWF de cinco archivos (`f000`–`f012`), con área `(-130, -57, -10, 30)`, convención `0_360` y `config/models/ecmwf.yaml`, inventarió 873 mensajes y creó un NetCDF de 52 MiB en 0.19 min. `INVENTORY` tomó 0.06 min y `CONVERT` 0.08 min. | La salida contiene nueve variables meteorológicas seleccionadas; `prmslmsl` emitió la advertencia acordada. Se verificaron `long_name`, `parameter_signature` y `wgrib2_short_name` en `tmp2m`, y los atributos de remapeo en `apcpsfc`. La evidencia queda en `data/standardized/benchmark/ecmwf_selection_test/`. |
| 2026-09-23 | Verificada | El benchmark ECMWF completo de 65 archivos, con la misma área, convención y selección YAML, inventarió 11,313 mensajes y creó `ecmwf-ifs_20260903_00Z.nc` de 654 MiB en 5.51 min. `INVENTORY` tomó 2.31 min y `CONVERT` 3.02 min. | El NetCDF contiene nueve variables meteorológicas: `apcpsfc`, `tmp2m`, `tmpprs`, `hgtprs`, `ugrd10m`, `ugrdprs`, `vgrd10m`, `vgrdprs` y `rhprs`. Se confirmaron los atributos de procedencia de `tmp2m` y los atributos de remapeo de `apcpsfc`; `prmslmsl` conservó la advertencia acordada. La evidencia queda en `data/standardized/benchmark/ecmwf_selection_full/`. |
| 2026-09-23 | Verificada | El benchmark GFS completo de 129 archivos, con `config/models/gfs.yaml`, área `(-130, -57, -10, 30)` y convención `0_360`, creó un NetCDF seleccionado de 3.60 GiB en 29.68 min. `INVENTORY` tomó 1.51 min y `CONVERT` 27.97 min. | Frente al benchmark GFS completo previo de 5.01 GiB y 39.90 min, la selección redujo 28.2% el tamaño, 25.6% el tiempo total y 24.7% la etapa `CONVERT`; el inventario WGRIB2 sigue completo. La evidencia queda en `data/standardized/benchmark/gfs_selection_full/`. |
| 2026-09-23 | Acordado | La selección de variables finales y los atributos de procedencia se integran como ampliación de la fase 4; no constituyen una fase independiente. | La fase 4 queda verificada con las corridas completas GFS y ECMWF. |

## Protocolo entre conversaciones

Al iniciar un nuevo chat que continúe esta implementación:

1. Leer `AGENTS.md`, este plan, `docs/data-standard.md`,
   `docs/grib2-parameter-reference.md` y `docs/analysis/`.
2. Identificar en la tabla de estado la fase activa y limitar el trabajo a su
   objetivo y decisiones pendientes.
3. No implementar una fase posterior por anticipación; primero cerrar el
   criterio verificable de la fase actual.
4. Si aparece una decisión científica o de contrato, documentarla antes de
   codificarla en el registro de este plan. Las decisiones que además cambien
   el alcance, la operación o el contrato de datos del proyecto se registran
   en `context/DECISIONS.md`.

Al cerrar una conversación con avance real:

1. Actualizar el estado de la fase y la fecha de este documento.
2. Añadir al registro una entrada con la decisión, implementación o hallazgo
   verificable, incluyendo ruta de código, prueba o inventario cuando exista.
3. Escribir el siguiente paso concreto en la columna `Próximo paso`.

No debe marcarse una fase como `Verificada` sólo porque exista código: debe
hacerse luego de indicacion explicita

## Acuerdos que guían el diseño

- Los GRIB originales en `data/raw` son de solo lectura.
- Una corrida produce un solo NetCDF final por modelo.
- WGRIB2 se ejecuta con `-names ncep`, sin depender de su configuración de
  compilación.
- El inventario contiene todos los mensajes. La selección opcional usa nombres
  NetCDF finales después de resolver los remapeos YAML y antes de crear el
  NetCDF.
- El nombre inicial de un campo proviene de WGRIB2. Sólo una regla YAML
  explícita puede reemplazarlo para un parámetro local de un centro no NCEP.
- La fase 3 abre sólo el primer GRIB para obtener `latlons()` de su primer
  mensaje. La fase 4 lee los valores de los mensajes una vez por archivo;
  PyGRIB no define el nombre final de las variables.
- La asociación entre una fila de inventario y un mensaje decodificado usa la
  posición dentro del mismo archivo. No se almacena una posición explícita ni
  se realizará una pasada adicional para contar o validar encabezados; la
  lectura única de `latlons()` de fase 3 no lee valores ni cumple ese fin.
- El tiempo válido se toma de WGRIB2 con `-VT`. El eje `time` conserva todos
  los tiempos válidos únicos recibidos, sin exigir cadencia, rango ni intervalos.
  El usuario entrega una lista de GRIB sin plazos faltantes para su uso.
- Los niveles de presión se conservan en su orden nativo descendente, siguiendo
  la lógica de `grib2_to_netcdf.py`: un nivel textual `500mb` forma parte de un
  perfil de presión y se agrupa con los demás niveles de la misma variable. El
  NetCDF usará el eje `lev` con unidades `millibars`.
- El área de recorte es un rectángulo continuo en `-180..180` y `-90..90`; no
  puede cruzar el antimeridiano. WGRIB2 valida su contención. La fase 3
  prepara coordenadas e índices en la convención longitudinal elegida y la
  fase 4 aplica esos índices a los valores, sin interpolación ni alteración de
  sus valores.
- Las únicas transformaciones de valores autorizadas son las declaradas en
  YAML mediante `factor` y `offset`.
- La dimensión `time` es ilimitada y su coordenada se escribe antes de las
  matrices, manteniendo el acceso por bloque temporal durante la escritura.
- Un error detiene la conversión y el NetCDF creado se cierra para que pueda
  analizarse hasta su último dato escrito.

## Flujo objetivo

```text
archivos GRIB2 + YAML + área + variables finales opcionales
                 |
                 v
         inventario completo WGRIB2
                 |
                 v
  plan de nombres, presión, tiempo y remapeos YAML
                 |
                 v
       selección opcional de variables finales
                 |
                 v
       apertura directa del NetCDF final
                 |
                 v
PyGRIB: `latlons()` del primer mensaje
                 |
                 v
coordenadas + subset + variables NetCDF vacías
                 |
                 v
PyGRIB: una lectura secuencial de valores por archivo
                 |
                 v
subset + conversión YAML + escritura de matrices
                 |
                 v
          cierre del NetCDF final
```

La fase 3 abre sólo el primer GRIB para obtener sus coordenadas con
`latlons()`. La fase 4 abre cada archivo para su única pasada de matrices; no
repite lecturas de coordenadas ni cálculos de subset.

## Fase 0 — Definir el contrato de ejecución y el YAML

### Objetivo

Fijar los argumentos públicos, el formato YAML inicial y las decisiones de
datos necesarias antes de leer o escribir archivos.

### Interfaz inicial propuesta

```python
converter = Grib2ToNetCDF(
    grib_files=grib_files,
    model=model,
    center=center,
    configuration_yml="config/grib2-definitions.yaml",
    area=(west, south, east, north),  # opcional
    longitude_convention="0_360",  # opcional
    variables=["tmp2m", "apcpsfc"],  # opcional
)
converter.run_conversion(output_dir)
```

`variables` recibe nombres finales exactos y es opcional: con `None` se
procesan todas las variables. La selección no altera el inventario WGRIB2 ni
el eje `time`; sólo limita las variables NetCDF y las matrices PyGRIB escritas.
El usuario es responsable de indicar los nombres finales correctos, como
`tmp2m` o `apcpsfc`, no nombres base ni códigos locales. `configuration_yml`
usa por defecto `config/grib2-definitions.yaml`; la lista de GRIB no puede
estar vacía y se ordena de forma ascendente antes del inventario. `area` limita
únicamente la extensión geográfica de los valores escritos.

### YAML inicial

El archivo único `config/grib2-definitions.yaml` usa una regla general para
las disciplinas trabajadas 0, 1, 2, 3, 4 y 10. Las disciplinas 20 y 191 quedan
fuera del alcance inicial. Su esquema es:

```yaml
local_definitions_reserved:
  disciplines: [0, 1, 2, 3, 4, 10]
  category_range: [192, 254]
  parameter_range: [192, 254]

remappings:
  ecmwf:
    "0-6-192":
      output:
        name: TCDC
        units: "%"
        long_name: "Total cloud cover"
        factor: 100
    "0-1-193":
      output:
        name: APCP
        units: mm
        long_name: "Total precipitation"
```

`local_definitions_reserved` clasifica códigos; no atribuye por sí solo
significado meteorológico ni cambia un nombre. `remappings` contiene las
equivalencias científicas aprobadas para un centro no NCEP. Su clave es la
firma `disciplina-categoría-parámetro`; `name`, `units` y `long_name` son
obligatorios, y `factor` y `offset` toman 1 y 0 por defecto.

### Decisiones que deben cerrarse en esta fase

Las decisiones 1, 2 y 4 se aprobaron el 2026-09-21 y constan en el registro
acumulativo. La fase 3 implementará el eje vertical acordado `lev`, con
unidades `millibars`; no bloquea este contrato.

### Criterio de cierre

Existe el YAML válido `config/grib2-definitions.yaml`, aplicable a GFS/NCEP y
ECMWF, y se aprobó la firma del constructor y de `run_conversion`.

## Fase 1 — Inventario WGRIB2

### Objetivo

Construir una fila por mensaje GRIB2, en el orden de cada archivo, con toda la
información necesaria para planificar el NetCDF sin decodificar matrices.

### Reglas

- Ejecutar WGRIB2 una vez por archivo con:

  ```text
  wgrib2 -names ncep -T -VT -domain -lev0 -nxny -ctl_inv <archivo>
  ```

- El inventario conserva, por cada mensaje y en el orden del archivo:
  `grib_file`, `short_name`, `parameter_signature`, `var_name`, nivel textual,
  tiempo válido, tiempo de referencia, dominio, `nx`, `ny`, descripción y
  unidades cuando WGRIB2 las entrega. `short_name` conserva la definición NCEP
  entregada por WGRIB2; `var_name` aplica desde el inventario la agrupación
  g2ctl por presión, nivel y promedio, y podrá recibir un remapeo explícito en
  la fase 2.
- La salida se interpreta directamente como ocho segmentos separados por `:`:
  mensaje, byte, fecha de corrida, tiempo válido, dominio, nivel, tamaño de
  grilla y `ctl_inv`. La definición vertical interna de `ctl_inv` no se
  conserva; sus tres primeros códigos forman `parameter_signature` y un cuarto
  código local se ignora. El proceso estadístico se incorpora a `var_name`
  cuando forma parte de la convención g2ctl/NCEP.
- `domain`, `nx` y `ny` registran extensión y tamaño de la malla. La
  fase 2 comprueba que sean únicos dentro de la corrida antes de crear el
  NetCDF.
- El inventario no filtra mensajes y no lee sus matrices de datos.

### Métodos previstos

- `_run_wgrib2_command(grib_file)`
- `_parse_wgrib2_output(grib_file, output)`
- `_build_inventory()`

### Criterio de cierre

Un inventario reproducible enumera todos los mensajes de una muestra GFS y una
ECMWF, conserva el orden de cada archivo y expone los campos necesarios para
las fases siguientes.

## Fase 2 — Plan de variables y nombres finales

### Objetivo

Transformar las filas de inventario en un plan inequívoco de variables,
tiempos, niveles y transformaciones que se aplicará después a las matrices
PyGRIB.

### Reglas de nombres

1. `short_name` conserva el nombre NCEP obtenido de WGRIB2 y `var_name` aplica
   su agrupación g2ctl por presión, nivel y promedio.
2. Si la firma está en un rango local, se consulta el `remappings` del centro
   productor actual; para NCEP no se lee ningún remapeo.
3. Una regla encontrada reemplaza el nombre base por `output.name` y
   registra `units`, `long_name`, `factor` y `offset` para la escritura.
4. Sin regla, no se infiere equivalencia ni conversión. Se emite una
   advertencia con la firma disponible y se conserva la definición NCEP.
5. El remapeo reemplaza `short_name` dentro de `var_name`: presión agrupa como
   `nombreprs`; los otros niveles conservan la convención de la referencia,
   como `tmp2m` o `ugrd10m`.
6. Los identificadores NetCDF se normalizan en minúsculas, por ejemplo
   `TCDC` termina como `tcdcsfc` o `tcdcprs` según su nivel.

La regla ECMWF `0-6-192 -> TCDC` se aplica antes de formar el nombre con el
sufijo de nivel; el remapeo no sustituye ni modifica el nivel del mensaje.

`wgrib2_inventory` conserva `var_name` por mensaje. La tabla
`netcdf_variables` registra una sola vez por `var_name` la variable final,
condición isobárica, unidades, atributos de procedencia, factor, offset y si
recibió remapeo.

Después de construir los nombres finales se aplica la selección opcional. Un
nombre solicitado que no esté en `netcdf_variables` genera una advertencia; el
proceso sólo se detiene si el filtro no conserva ninguna variable. Los
remapeos representan parámetros locales de centros como ECMWF que no entregan
el campo con la codificación meteorológica estandarizada: forman la variable
final común antes de que pueda ser seleccionada.

### Presión y tiempo

- `_match_pressure_level()` reconocerá inicialmente niveles con formato
  `numero + mb`, igual que la referencia.
- Los niveles de las variables seleccionadas se ordenan de mayor a menor y
  forman el eje `lev`; su unidad NetCDF será `millibars`. Si no se seleccionan
  campos isobáricos, no se crea la dimensión ni la coordenada `lev`.
- Los tiempos válidos extraídos con `-VT` se ordenan y forman el eje `time`.
  Se conservan sin validación de cadencia, rango o intervalos; el usuario es
  responsable de proporcionar la secuencia temporal completa que requiera.

### Validación de corrida y área

- Todos los mensajes deben tener una única hora de referencia, dominio y
  tamaño de grilla.
- Si se proporciona `area=(west, south, east, north)`, debe cumplir
  `-180 <= west < east <= 180` y `-90 <= south < north <= 90`.
- WGRIB2 entrega el dominio normalizado a `-180..180`; Shapely comprueba que
  el rectángulo solicitado esté íntegramente contenido en él.
- Las áreas que cruzan el antimeridiano no están definidas en este conversor.

FV3-GFS puede repetir mensajes APCP acumulados. Comparten el mismo destino
NetCDF y la variable se define una sola vez, como en la referencia; la fase 2
no lee ni selecciona sus matrices.

### Métodos previstos

- `_read_grib2_configurations()`
- `_validate_inventory()`
- `_match_pressure_level()`
- `_build_coordinates()`
- `_build_netcdf_variables()`

### Criterio de cierre

Los inventarios completos GFS y ECMWF muestran por mensaje su definición NCEP,
nombre NetCDF final, tiempo y nivel; `netcdf_variables` registra los remapeos y
conversiones declarados. No se leen matrices ni se crea un NetCDF.

## Fase 3 — Estructura NetCDF y subset geográfico

### Objetivo

Crear directamente el único NetCDF final, sus coordenadas y el plan de índices
geográficos que la fase 4 aplicará a las matrices.

### Reglas

- Las dimensiones canónicas son `time`, `latitude` y `longitude`, junto con
  `lev` cuando la selección contiene variables isobáricas.
- Las variables de superficie usan `(time, latitude, longitude)` y las de
  presión `(time, lev, latitude, longitude)`.
- Se crean primero el archivo, el eje `time` del inventario completo, el eje
  `lev` de las variables seleccionadas cuando exista y los atributos globales.
  La dimensión `time` es ilimitada y su coordenada se escribe antes de las
  matrices. El eje `lev` conserva niveles isobáricos descendentes y usa
  unidades `millibars`, igual que la referencia.
- La fase 3 abre sólo el primer GRIB y obtiene `latlons()` de su primer
  mensaje. No lee matrices meteorológicas. Con esas coordenadas crea
  `latitude`, `longitude`, las dimensiones horizontales y las variables del
  plan.
- El constructor recibe `longitude_convention`: `0_360` es el valor
  predeterminado y `-180_180` es una alternativa. PyGRIB puede entregar
  cualquier convención nativa; las longitudes se normalizan y ordenan según la
  salida elegida. El mismo orden de índices se aplicará a las columnas de
  valores durante la fase 4, sin interpolar.
- El área ya validada en fase 2 es un rectángulo continuo que no cruza el
  antimeridiano y se expresa siempre en EPSG:4326 `-180..180`; sus índices se
  calculan sobre la grilla ordenada en la convención de salida.
- Para las fuentes controladas se asume una grilla geográfica rectangular. No
  se repite la comprobación de `nx`/`ny` contra `latlons()` ni se valida la
  rectangularidad durante esta fase.

### Métodos previstos

- `run_conversion(output_dir)`
- `_create_netcdf(netcdf_output)`
- `_prepare_netcdf_grid(grib_file)`

### Criterio de cierre

GFS y ECMWF, con y sin `area` y en las dos convenciones longitudinales,
producen coordenadas e índices de origen correctos. El NetCDF en memoria
contiene las dimensiones, coordenadas y variables acordadas; la fase 4 usará
esos índices para escribir las posiciones correspondientes.

## Fase 4 — Lectura única PyGRIB y escritura

### Objetivo

Recorrer cada GRIB una única vez, leer sus valores, aplicar operaciones
explícitas y escribirlos en el NetCDF final.

### Reglas

- Para cada archivo, PyGRIB se abre una vez y sus mensajes se recorren en
  orden.
- El índice de iteración recupera la fila de inventario del mismo archivo; no
  hay una pasada previa para encabezados ni conteos.
- El constructor admite `variables` con nombres NetCDF finales exactos. La
  selección se resuelve después de los remapeos YAML y antes de crear el
  NetCDF; `None` conserva todas las variables. Un nombre ausente advierte y
  sólo un filtro sin variables disponibles detiene la conversión.
- Los mensajes sin una variable final seleccionada se omiten antes de acceder
  a su matriz `values`; su iteración se conserva para mantener la asociación
  por posición con el inventario completo.
- La malla, las variables NetCDF y los índices geográficos ya fueron creados
  en la fase 3; no se vuelven a calcular durante la lectura de valores.
- Cada matriz se recorta y, cuando corresponda, se reordena mediante los
  índices geográficos definidos.
- Si la fila tiene remapeo, se calcula `values * factor + offset`; no se
  evalúan fórmulas arbitrarias.
- La matriz final se escribe en su índice de tiempo y, para niveles
  isobáricos, en su índice vertical.
- Cada variable NetCDF recibe `long_name`, `parameter_signature` y
  `wgrib2_short_name`. Cuando hay remapeo también recibe
  `remapping_applied`, `remapping_factor` y `remapping_offset`; los
  `long_name` de remapeos proceden de `output.long_name` en YAML.
- Un error de la conversión detiene la corrida. El cierre del NetCDF se ejecuta
  de todos modos para conservar el archivo creado hasta ese punto.

### Métodos implementados

- `_write_grib_messages(dataset)`
- `_write_message(dataset, inventory_row, grib_message)`
- `_create_netcdf(netcdf_output)`

### Criterio de cierre

Las corridas completas GFS y ECMWF escriben un único NetCDF final mediante una
pasada de valores por archivo, conservando el subset y reordenamiento
preparados en la fase 3. La selección usa nombres finales, conserva el
inventario completo, omite matrices no seleccionadas y registra los atributos
acordados. La verificación científica de los valores, incluido el factor 100
de la cobertura nubosa ECMWF, corresponde a la fase 5.

## Fase 5 — Verificación científica y operación

### Objetivo

Probar el conversor contra las fuentes conocidas y documentar decisiones que
pasen a ser contractuales.

### Casos mínimos

1. GFS: nombres WGRIB2 NCEP sin remapeos y perfiles de presión.
2. ECMWF: `0-6-192` convertido a `TCDC` y de fracción a porcentaje.
3. Área parcial: índices y valores idénticos al subconjunto de la fuente.
4. Secuencia temporal entregada por el usuario: eje `time` conservado sin
   relleno ni validación de cadencia.
5. Código local sin regla: advertencia explícita y comportamiento acordado.
6. APCP duplicado de FV3-GFS: una única variable NetCDF con la convención de
   la referencia.

### Entregables

- Ejecuciones manuales reproducibles con inventarios y casos de fuentes
  documentados en este plan.

## Orden de implementación

La verificación científica de la fase 5 continúa con sus casos mínimos.
