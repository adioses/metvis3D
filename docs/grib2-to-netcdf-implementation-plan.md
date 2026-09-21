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

Cada fase debe precisarse y aprobarse antes de implementarla. En su estado
actual el documento no introduce código operativo.

## Estado de implementación

**Última actualización:** 2026-09-21
**Fase activa:** 1. Inventario WGRIB2.
**Estado global:** contrato de ejecución y YAML inicial verificados;
implementación del conversor no iniciada.

| Fase | Estado | Resultado verificable | Próximo paso |
|---|---|---|---|
| 0. Contrato de ejecución y YAML | Verificada | Interfaz y YAML inicial aprobados | Iniciar la fase 1 con el inventario WGRIB2. |
| 1. Inventario WGRIB2 | Pendiente | Inventario completo y reproducible | Definir el comando y su formato exacto de salida. |
| 2. Plan de variables y nombres | Pendiente | Plan por mensaje, tiempo y nivel | Resolver colisiones y unidades de presión. |
| 3. NetCDF y subset | Pendiente | Estructura y recorte verificables | Definir límites geográficos y mallas admitidas. |
| 4. Escritura con PyGRIB | Pendiente | Una pasada PyGRIB y NetCDF completo | Implementar sólo después de las fases 0–3. |
| 5. Verificación científica | Pendiente | Casos GFS y ECMWF documentados | Ejecutar al disponer del conversor. |

Estados permitidos: `Pendiente`, `En definición`, `En implementación`,
`Verificada` o `Bloqueada`. Un estado `Verificada` exige el criterio de cierre
de su fase y una evidencia enlazable: prueba, salida reproducible o documento.

## Registro acumulativo de acuerdos

Las entradas se agregan al final de esta tabla; no se reescriben acuerdos
históricos. Si una decisión cambia, se añade una nueva entrada que indique cuál
sustituye. Las decisiones que cambien el contrato del proyecto también se
registran en `docs/DECISIONS.md`.

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

## Protocolo entre conversaciones

Al iniciar un nuevo chat que continúe esta implementación:

1. Leer `AGENTS.md`, este plan, `docs/data-standard.md`,
   `docs/grib2-parameter-reference.md`, `docs/analysis/` y las entradas
   pertinentes de `docs/DECISIONS.md` y `docs/STATUS.md`.
2. Identificar en la tabla de estado la fase activa y limitar el trabajo a su
   objetivo y decisiones pendientes.
3. No implementar una fase posterior por anticipación; primero cerrar el
   criterio verificable de la fase actual.
4. Si aparece una decisión científica o de contrato, documentarla antes de
   codificarla. Si sólo afecta este conversor, añadirla al registro de este
   plan; si afecta al proyecto, añadirla también a `docs/DECISIONS.md`.

Al cerrar una conversación con avance real:

1. Actualizar el estado de la fase y la fecha de este documento.
2. Añadir al registro una entrada con la decisión, implementación o hallazgo
   verificable, incluyendo ruta de código, prueba o inventario cuando exista.
3. Escribir el siguiente paso concreto en la columna `Próximo paso`.
4. Actualizar `docs/STATUS.md` sólo si el avance cambia materialmente el estado
   general del proyecto.

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
- La asociación entre una fila de inventario y un mensaje PyGRIB es posicional
  dentro del mismo archivo. No se realizará una pasada PyGRIB adicional para
  contar o validar encabezados.
- El tiempo válido se toma de WGRIB2 con `-VT` y se conserva tal como llega,
  sin exigir frecuencia regular ni completar plazos ausentes.
- Los niveles de presión se conservan en su orden nativo descendente, siguiendo
  la lógica de `grib2_to_netcdf.py`: un nivel textual `500mb` forma parte de un
  perfil de presión y se agrupa con los demás niveles de la misma variable.
- El recorte geográfico se hace por índices de la malla original. No implica
  interpolación ni alteración de los valores.
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
    area=(west, east, south, north),  # opcional
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
    - match:
        discipline: 0
        category: 6
        parameter: 192
      output:
        name: TCDC
        units: "%"
        factor: 100
    - match:
        discipline: 0
        category: 1
        parameter: 193
      output:
        name: APCP
        units: mm
```

`local_definitions_reserved` clasifica códigos; no atribuye por sí solo
significado meteorológico ni cambia un nombre. `remappings` contiene las
equivalencias científicas aprobadas para un centro. La coincidencia inicial es
por disciplina, categoría y parámetro; `name` y `units` son obligatorios, y
`factor` y `offset` toman 1 y 0 por defecto. Si una fuente futura tiene
variantes de nivel o procesamiento temporal para la misma terna, esos
criterios se añadirán a `match` antes de convertirla.

### Decisiones que deben cerrarse en esta fase

Las decisiones 1, 2 y 4 se aprobaron el 2026-09-21 y constan en el registro
acumulativo. La unidad final de `pressure` se difiere a la fase 3, cuando se
implemente e inspeccione la inicialización NetCDF; no bloquea este contrato.

### Criterio de cierre

Existe el YAML válido `config/grib2-definitions.yaml`, aplicable a GFS/NCEP y
ECMWF, y se aprobó la firma del constructor y de `run_conversion`.

## Fase 1 — Inventario WGRIB2

### Objetivo

Construir una fila por mensaje GRIB2, en el orden de cada archivo, con toda la
información necesaria para planificar el NetCDF sin decodificar matrices.

### Reglas

- Ejecutar WGRIB2 una vez por archivo, siempre con `-names ncep`.
- El comando de inventario deberá producir y el analizador deberá conservar:
  posición de mensaje, archivo, nombre NCEP, disciplina-categoría-parámetro,
  nivel textual y código de nivel, procesamiento temporal, tiempo válido,
  tiempo de referencia, tamaño y dominio de malla, y unidades/descripción si
  WGRIB2 las entrega.
- El formato de salida se analizará por etiquetas, no por posiciones frágiles
  de una lista separada por `:`.
- El inventario no filtra mensajes y no lee sus matrices de datos.

### Métodos previstos

- `_run_wgrib2_inventory(grib_file)`
- `_parse_wgrib2_inventory(grib_file, output)`
- `_build_wgrib2_inventory()`

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

1. El nombre NCEP obtenido de WGRIB2 es el nombre base inicial.
2. Si la terna está en un rango local para el `source.centre`, se consulta
   `remappings`.
3. Una regla encontrada reemplaza el nombre base por `output.ncep_name` y
   registra `units`, `factor` y `offset` para la escritura.
4. Sin regla, no se infiere equivalencia ni conversión. Se emite una
   advertencia con la firma disponible y se conserva el nombre WGRIB2.
5. Después se aplica el sufijo del nivel: presión agrupa como `nombreprs`; los
   otros niveles conservan la convención de la referencia, como `tmp2m` o
   `ugrd10m`.
6. Los identificadores NetCDF se normalizan en minúsculas, por ejemplo
   `TCDC` termina como `tcdcsfc` o `tcdcprs` según su nivel.

La regla ECMWF `0-6-192 -> TCDC` se aplica antes de formar el nombre con el
sufijo de nivel; el remapeo no sustituye ni modifica el nivel del mensaje.

### Presión y tiempo

- `_match_pressure_level()` reconocerá inicialmente niveles con formato
  `numero + mb`, igual que la referencia.
- Los niveles encontrados se ordenan de mayor a menor y forman un único eje
  vertical por corrida.
- Los tiempos válidos extraídos con `-VT` se ordenan y forman el eje `time`.
  No se valida intervalo constante.

### Caso que debe precisarse

Dos mensajes pueden acabar con la misma variable, tiempo y nivel final. Este
caso debe definirse antes de escribir: en particular, los acumulados duplicados
de APCP de GFS no pueden resolverse escogiendo un mensaje por posición ni
sobrescribiendo silenciosamente un valor. Se documentará la lógica WGRIB2
aplicable, incluido `-unmerge_fcst` si corresponde, y su representación en el
plan de variables.

### Métodos previstos

- `_build_variable_plan()`
- `_get_parameter_status(inventory_row)`
- `_apply_local_remapping(inventory_row)`
- `_build_final_variable_name(inventory_row)`
- `_build_time_and_pressure_axes()`

### Criterio de cierre

Para muestras GFS y ECMWF, el plan muestra por cada mensaje su nombre WGRIB2,
remapeo opcional, nombre NetCDF final, tiempo, nivel y conversión declarada.

## Fase 3 — Estructura NetCDF y subset geográfico

### Objetivo

Crear directamente el único NetCDF final y definir su estructura sin requerir
una lectura PyGRIB previa de los archivos.

### Reglas

- Las dimensiones canónicas son `time`, `pressure`, `latitude` y
  `longitude`.
- Las variables de superficie usan `(time, latitude, longitude)` y las de
  presión `(time, pressure, latitude, longitude)`.
- Se crean primero el archivo, los ejes de tiempo y presión conocidos por el
  inventario y los atributos globales.
- Al recibir el primer mensaje PyGRIB de la fase 4, `latlons()` aporta la
  malla: entonces se calculan los índices de `area`, se crean `latitude` y
  `longitude`, las dimensiones horizontales y las variables del plan.
- El subset debe conservar el orden y los valores de la malla fuente. La
  normalización de longitudes a `-180..180`, si se aplica, debe reordenar datos
  y coordenadas con los mismos índices y nunca interpolar.
- La malla debe ser compatible con coordenadas geográficas rectangulares.
  Una malla no compatible debe informarse y detener la corrida hasta definir
  su tratamiento.

### Métodos previstos

- `_initialize_netcdf_time_and_pressure(output_path)`
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
- La matriz final se escribe en su índice de tiempo y, para presión, en su
  índice vertical.
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
4. Tiempos irregulares o plazos ausentes: eje `time` conservado sin relleno.
5. Código local sin regla: advertencia explícita y comportamiento acordado.
6. Colisión de mensajes en una misma celda lógica NetCDF: tratamiento aprobado
   antes de aceptar la corrida como válida.

### Entregables

- Pruebas automatizadas con archivos de muestra o inventarios reproducibles.
- Actualización de `docs/DECISIONS.md` para las decisiones aprobadas.
- Actualización de `docs/STATUS.md` sólo después de una implementación y
  verificación reales.

## Orden de implementación

La próxima conversación debe comenzar por la fase 0. No se implementará una
fase posterior mientras sus decisiones pendientes no estén definidas y su
criterio de cierre no pueda verificarse.
