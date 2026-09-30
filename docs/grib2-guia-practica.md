# Guía práctica para leer GRIB2

GRIB2 es un formato binario para intercambiar datos meteorológicos. Un archivo
GRIB2 no equivale a una sola variable ni a una tabla: contiene una secuencia de
**mensajes**. Cada mensaje describe un campo en una hora, nivel y grilla
determinados, por ejemplo, temperatura a 500 hPa para un plazo de pronóstico.

Esta guía explica los elementos necesarios para inspeccionar esos mensajes y
llevarlos al NetCDF usado por este proyecto. Un mensaje puede leerse como la
combinación de *qué se mide*, *dónde*, *cuándo* y *cómo fue calculado*.

## Qué identifica un campo GRIB2

La cantidad física base se identifica con una firma de tres números:

```text
disciplina - categoría - parámetro
```

Por ejemplo, `0-0-0` representa temperatura dentro de la disciplina
meteorológica. Esa firma no basta para identificar una variable lista para
usar: debe combinarse con el centro productor, nivel, proceso estadístico,
tiempo y grilla.

| Metadato | Pregunta que responde | Ejemplo | Uso en la estandarización |
|---|---|---|---|
| Disciplina | ¿Qué familia general de productos es? | `0`: meteorología | Primera parte de la firma. |
| Categoría | ¿Qué tipo de cantidad es? | `0`: temperatura; `1`: humedad | Segunda parte de la firma. |
| Parámetro | ¿Cuál es la cantidad específica? | `0-0-0`: temperatura | Tercera parte de la firma. |
| Centro productor | ¿Quién definió el mensaje? | NCEP, ECMWF | Necesario para interpretar códigos locales. |
| Nivel | ¿A qué altura, presión o superficie corresponde? | `500mb`, `2 m above ground` | Define la estructura de salida. |
| Proceso estadístico | ¿Es instantáneo, promedio, acumulado, máximo o mínimo? | `ave` | Evita mezclar significados temporales. |
| Tiempos | ¿Cuándo inició y para qué hora vale? | inicio 00Z, válido 06Z | Construye el eje `time`. |
| Grilla | ¿Dónde se ubica cada valor? | dominio, `nx × ny`, coordenadas | Define la salida espacial. |

La [referencia de parámetros GRIB2](grib2-parameter-reference.md) contiene el
detalle de disciplinas, categorías y rangos reservados para uso local.

## La firma no identifica el campo completo

La misma temperatura puede aparecer a 2 m sobre el suelo y a 500 hPa. Aunque
compartan firma, son campos distintos porque su nivel es distinto. De forma
parecida, una precipitación acumulada y una tasa de precipitación no deben
tratarse como la misma variable: el proceso estadístico y su intervalo temporal
cambian su interpretación.

Los códigos `192` a `254` de categoría o parámetro suelen estar reservados para
uso local. Su significado depende del centro productor. Por eso, un código
local de ECMWF no se interpreta automáticamente con una tabla de NCEP: requiere
una regla explícita y revisada.

## Inventario con WGRIB2

WGRIB2 es la herramienta de línea de comandos usada para leer las cabeceras de
los mensajes sin cargar todas sus matrices en memoria.

```bash
# Lista breve de mensajes.
wgrib2 archivo.grib2 -s

# Inventario usado por el conversor.
wgrib2 archivo.grib2 -names ncep -T -VT -domain -lev0 -nxny -ctl_inv

# Descripción de la grilla y su proyección declarada por el GRIB.
wgrib2 archivo.grib2 -grid
```

El inventario del conversor obtiene `D=` (hora de referencia), `vt=` (tiempo
válido), dominio, tamaño de grilla, nivel textual, nombre NCEP, firma,
proceso estadístico, descripción y unidades. El nombre de `-names ncep` ayuda
a leer un mensaje, pero no sustituye la firma completa ni la documentación del
centro productor.

Para generar un resumen Markdown de una corrida sin leer matrices:

```bash
python scripts/report_grib2_inventory.py "data/raw/ECMWF/*.grib2" \
  --center ecmwf --model ifs \
  --output outputs/grib2-analysis/ecmwf-inventory.md
```

El reporte toma los tres primeros archivos ordenados, muestra variables,
niveles y remapeos, y advierte parámetros locales sin una regla aprobada.

## Grilla y proyecciones

Cada mensaje GRIB2 declara cómo se distribuyen sus valores en el espacio. Una
grilla puede ser geográfica regular —latitud y longitud— o usar otra proyección
cartográfica. `wgrib2 -grid` permite inspeccionar esa definición; no se debe
deducir una proyección sólo por el tamaño `nx × ny`.

Las fuentes trabajadas actualmente se manejan como grillas geográficas
rectangulares. PyGRIB obtiene sus coordenadas reales con `latlons()`, y el
conversor escribe los ejes `latitude` y `longitude`. Si se solicita un área,
se seleccionan puntos existentes: no hay interpolación ni remuestreo.

La salida puede ordenar longitudes en `0_360` o `-180_180`. El área se expresa
como `(west, south, east, north)` en `-180..180`, debe estar contenida en el
dominio y no puede cruzar el antimeridiano.

Una fuente con proyección no geográfica o geometría distinta requiere revisión
antes de usarla con el conversor actual. La opción opcional `-proj4` de WGRIB2
no forma parte del flujo del proyecto ni debe asumirse disponible en la
instalación estándar.

## Lectura de valores con PyGRIB

PyGRIB permite abrir un mensaje, consultar metadatos y acceder a su matriz de
valores junto con las coordenadas:

```python
import pygrib

with pygrib.open("archivo.grib2") as grib_file:
    message = grib_file.message(1)
    print(message.name, message.typeOfLevel, message.level, message.validDate)
    latitude, longitude = message.latlons()
    values = message.values
```

`values` tiene forma `(ny, nx)`. `latitude` y `longitude` comparten su
geometría y permiten ubicar cada valor. El proyecto usa WGRIB2 como inventario
común y PyGRIB para las coordenadas y las matrices.

## Cómo se forman las variables NetCDF

`Grib2ToNetCDF` sigue este flujo:

```text
GRIB2
  -> WGRIB2: inventario completo de mensajes
  -> firma + centro + nivel + proceso estadístico + tiempo + grilla
  -> reglas YAML para parámetros locales
  -> PyGRIB: coordenadas y matrices
  -> NetCDF final por corrida
```

La nomenclatura inicial procede de WGRIB2. Los mensajes isobáricos, como
`500mb` y `700mb`, se agrupan en una variable con eje `lev`, por ejemplo
`tmpprs`. Los de superficie conservan el nivel en el nombre, como `tmp2m`.
Cuando el proceso es un promedio (`ave`), se incorpora para no confundirlo con
un campo instantáneo del mismo nivel. Son convenciones de este proyecto, no
significados universales de GRIB2.

Las reglas de `config/grib2-definitions.yaml` son la única vía para remapear un
parámetro local. Una regla puede cambiar nombre final, unidades, descripción,
factor y desplazamiento. El NetCDF conserva la firma, el nombre WGRIB2 y los
atributos del remapeo para mantener trazabilidad.

## Estructura de salida

Una corrida genera un NetCDF. Sus coordenadas y dimensiones son:

```text
time                         tiempos válidos
lev                          niveles isobáricos nativos, si existen
latitude, longitude          coordenadas de la grilla

superficie:  (time, latitude, longitude)
presión:     (time, lev, latitude, longitude)
```

Las variables se escriben con compresión y cuantización decimal. Al comparar un
valor NetCDF con el GRIB2 original debe considerarse la tolerancia asociada a
`least_significant_digit=2`.

## Antes de convertir una nueva fuente

1. Inventariar algunos archivos con WGRIB2 y revisar centro, firma, nivel,
   proceso estadístico, tiempos y grilla.
2. Confirmar que los archivos pertenecen a una sola corrida y comparten dominio
   y tamaño de grilla.
3. Revisar parámetros locales y crear un remapeo sólo con documentación del
   centro productor y validación científica.
4. Verificar que la grilla sea compatible con el tratamiento actual o acordar
   el manejo de su proyección antes de convertirla.
5. Comparar el NetCDF generado con los mensajes GRIB2 de origen antes de usarlo
   en un producto posterior.
