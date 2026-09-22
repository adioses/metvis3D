# Plan de implementación: conversión GRIB2 a NetCDF

## Propósito y uso continuo

Implementar una clase que convierta todos los mensajes de una corrida y modelo
GRIB2 en un único NetCDF final. La clase no interpola, no rellena vacíos y no
crea productos parciales por variable ni por tiempo.

WGRIB2 inventaría los mensajes, resuelve la codificación que interesa al flujo
y determina su nomenclatura NCEP. PyGRIB se usa una sola vez por archivo para
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

**Última actualización:** 2026-09-22
**Fase activa:** 3. Estructura NetCDF y subset geográfico.
**Estado global:** contrato de ejecución, inventario WGRIB2 y consolidación de
variables verificados; falta crear la estructura NetCDF y preparar el subset.

| Fase | Estado | Resultado verificable | Próximo paso |
|---|---|---|---|
| 0. Contrato de ejecución y YAML | Verificada | Interfaz y YAML inicial aprobados | Iniciar la fase 1 con el inventario WGRIB2. |
| 1. Inventario WGRIB2 | Verificada | Inventario completo de GFS y ECMWF, en orden por archivo | Consolidar variables, tiempos y niveles. |
| 2. Plan de variables y nombres | Verificada | Nombres finales, remapeos, tiempos y niveles de GFS y ECMWF | Crear la estructura NetCDF y preparar el subset. |
| 3. NetCDF y subset | En definición | Estructura y recorte verificables | Implementar `lev`, grilla normalizada y subset. |
| 4. Escritura con PyGRIB | Pendiente | Una pasada PyGRIB y NetCDF completo | Implementar sólo después de las fases 0–3. |
| 5. Verificación científica | Pendiente | Casos GFS y ECMWF documentados | Ejecutar al disponer del conversor. |

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

## Protocolo entre conversaciones

Al iniciar un nuevo chat que continúe esta implementación:

1. Leer `AGENTS.md`, este plan, `docs/data-standard.md`,
   `docs/grib2-parameter-reference.md` y `docs/analysis/`.
2. Identificar en la tabla de estado la fase activa y limitar el trabajo a su
   objetivo y decisiones pendientes.
3. No implementar una fase posterior por anticipación; primero cerrar el
   criterio verificable de la fase actual.
4. Si aparece una decisión científica o de contrato, documentarla antes de
   codificarla en el registro de este plan. Las decisiones de este conversor no
   se añaden a `docs/DECISIONS.md` ni a `docs/STATUS.md`.

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
- El inventario contiene todos los mensajes; no hay una selección de
  variables previa a la conversión.
- El nombre inicial de un campo proviene de WGRIB2. Sólo una regla YAML
  explícita puede reemplazarlo para un parámetro local de un centro no NCEP.
- PyGRIB lee los valores de los mensajes. Las coordenadas necesarias para el
  subset se obtienen del primer mensaje de esa misma pasada. PyGRIB no define
  el nombre final de las variables.
- La asociación entre una fila de inventario y un mensaje PyGRIB es el orden de
  las filas dentro del mismo archivo. No se almacena una posición explícita ni
  se realizará una pasada PyGRIB adicional para contar o validar encabezados.
- El tiempo válido se toma de WGRIB2 con `-VT`. El eje `time` conserva todos
  los tiempos válidos únicos recibidos, sin exigir cadencia, rango ni intervalos.
  El usuario entrega una lista de GRIB sin plazos faltantes para su uso.
- Los niveles de presión se conservan en su orden nativo descendente, siguiendo
  la lógica de `grib2_to_netcdf.py`: un nivel textual `500mb` forma parte de un
  perfil de presión y se agrupa con los demás niveles de la misma variable. El
  NetCDF usará el eje `lev` con unidades `millibars`.
- El área de recorte es un rectángulo continuo en `-180..180` y `-90..90`; no
  puede cruzar el antimeridiano. WGRIB2 valida su contención y, antes del
  recorte, PyGRIB normaliza y reordena la malla fuente junto con los valores.
  El recorte no implica interpolación ni alteración de los valores.
- Las únicas transformaciones de valores autorizadas son las declaradas en
  YAML mediante `factor` y `offset`.
- Los errores se informan con el modelo, corrida, archivo y mensaje afectados,
  y detienen la conversión.

## Flujo objetivo

```text
archivos GRIB2 + YAML + área opcional
                 |
                 v
         inventario completo WGRIB2
                 |
                 v
  plan de nombres, presión, tiempo y remapeos YAML
                 |
                 v
       apertura directa del NetCDF final
                 |
                 v
PyGRIB: una lectura secuencial de valores por archivo
                 |
                 v
 coordenadas + subset + conversión YAML + escritura
                 |
                 v
          cierre del NetCDF final
```

La apertura del NetCDF no obliga a una segunda lectura PyGRIB. El primer
mensaje de la pasada de escritura aporta las coordenadas necesarias para
calcular el recorte y terminar de crear las dimensiones horizontales y las
variables NetCDF.

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
)
converter.run_conversion(output_dir)
```

No se recibe una lista de variables: todos los mensajes inventariados se
procesan. `configuration_yml` usa por defecto
`config/grib2-definitions.yaml`. La lista no puede estar vacía y se ordena de
forma ascendente antes del inventario. `area` limita únicamente la extensión
geográfica de los valores escritos.

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
        factor: 100
    "0-1-193":
      output:
        name: APCP
        units: mm
```

`local_definitions_reserved` clasifica códigos; no atribuye por sí solo
significado meteorológico ni cambia un nombre. `remappings` contiene las
equivalencias científicas aprobadas para un centro no NCEP. Su clave es la
firma `disciplina-categoría-parámetro`; `name` y `units` son obligatorios, y
`factor` y `offset` toman 1 y 0 por defecto.

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
   registra `units`, `factor` y `offset` para la escritura.
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
condición isobárica, unidades, factor, offset y si recibió remapeo.

### Presión y tiempo

- `_match_pressure_level()` reconocerá inicialmente niveles con formato
  `numero + mb`, igual que la referencia.
- Los niveles encontrados se ordenan de mayor a menor y forman un único eje
  `lev` por corrida; su unidad NetCDF será `millibars` en la fase 3.
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

Crear directamente el único NetCDF final y definir su estructura sin requerir
una lectura PyGRIB previa de los archivos.

### Reglas

- Las dimensiones canónicas son `time`, `lev`, `latitude` y `longitude`.
- Las variables de superficie usan `(time, latitude, longitude)` y las de
  presión `(time, lev, latitude, longitude)`.
- Se crean primero el archivo, los ejes de tiempo y `lev` conocidos por el
  inventario y los atributos globales. El eje `lev` conserva niveles
  isobáricos descendentes y usa unidades `millibars`, igual que la referencia.
- Al recibir el primer mensaje PyGRIB de la fase 4, `latlons()` aporta la
  malla: entonces se calculan los índices de `area`, se crean `latitude` y
  `longitude`, las dimensiones horizontales y las variables del plan.
- PyGRIB puede entregar longitudes nativas en `0..360`. Antes del subset se
  normalizan a `-180..180` y se reordenan con los mismos índices las
  longitudes, coordenadas y columnas de valores, sin interpolar.
- El área ya validada en fase 2 es un rectángulo continuo que no cruza el
  antimeridiano; sus índices se calculan sobre la grilla reordenada.
- La malla debe ser compatible con coordenadas geográficas rectangulares.
  Una malla no compatible debe informarse y detener la corrida hasta definir
  su tratamiento.

### Métodos previstos

- `_initialize_netcdf_time_and_lev(output_path)`
- `_initialize_netcdf_grid(first_grib_message)`
- `_prepare_area_subset(latitude, longitude)`
- `_create_netcdf_variables()`

### Criterio de cierre

Una muestra con y sin `area` produce la estructura dimensional acordada y
coordenadas que corresponden exactamente a las posiciones escritas.

## Fase 4 — Lectura única PyGRIB y escritura

### Objetivo

Recorrer cada GRIB una única vez, leer sus valores, aplicar operaciones
explícitas y escribirlos en el NetCDF final.

### Reglas

- Para cada archivo, PyGRIB se abre una vez y sus mensajes se recorren en
  orden.
- El índice de iteración se usa para recuperar la fila WGRIB2 del mismo
  archivo; no hay una pasada previa de PyGRIB para encabezados ni conteos.
- El primer mensaje inicializa la malla y las variables NetCDF, como se
  describe en la fase 3.
- Cada matriz se recorta mediante los índices geográficos definidos.
- Si la fila tiene remapeo, se calcula `values * factor + offset`; no se
  evalúan fórmulas arbitrarias.
- La matriz final se escribe en su índice de tiempo y, para niveles
  isobáricos, en su índice vertical.
- Cualquier error de lectura, índice, malla, conversión o escritura se informa
  con el contexto meteorológico y detiene la corrida.

### Métodos previstos

- `_write_grib_messages(netcdf_dataset)`
- `_write_message(netcdf_dataset, inventory_row, grib_message)`
- `_apply_value_conversion(values, conversion)`

### Criterio de cierre

Una corrida de prueba escribe un solo NetCDF, conserva el subset solicitado y
demuestra el factor 100 de la cobertura nubosa ECMWF sin alterar los demás
campos.

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

La próxima conversación debe comenzar por la fase 3. No se implementará una
fase posterior mientras sus decisiones pendientes no estén definidas y su
criterio de cierre no pueda verificarse.
