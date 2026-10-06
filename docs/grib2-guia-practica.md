# Guía GRIB2: lectura, inventario y estandarización a NetCDF

## Propósito y alcance

Esta es la guía de referencia de MetVis3D para comprender archivos GRIB2,
inspeccionar sus mensajes y convertir una corrida homogénea a NetCDF. Sirve
tanto a quien incorpora una fuente como a quien mantiene el inventario, los
remapeos y el conversor.

No sustituye la especificación GRIB2 ni reproduce catálogos completos de
parámetros. Explica qué metadatos deben conservarse, qué tablas se requieren
para interpretarlos y cuáles son convenciones del proyecto. Los catálogos
vigentes se consultan en sus fuentes oficiales.

## 1. Archivo, mensaje y campo

Un archivo GRIB2 es una secuencia de **mensajes**, no necesariamente una sola
variable, hora o nivel. Cada mensaje contiene un campo completo en una grilla:
por ejemplo, temperatura a 500 hPa válida a las 06:00 UTC.

| Pregunta | Metadatos que la responden |
|---|---|
| ¿Qué cantidad física es? | Disciplina, categoría y número de parámetro. |
| ¿Quién le asignó significado? | Centro, subcentro y versiones de tabla. |
| ¿A qué superficie o capa corresponde? | Tipo(s) de superficie vertical y valor(es). |
| ¿Es instantáneo o estadístico? | Plantilla de producto y procesamiento estadístico. |
| ¿Cuándo es válido? | Hora de referencia, plazo e instante o intervalo válido. |
| ¿Dónde están los valores? | Grilla, proyección, dimensiones y coordenadas. |

Un nombre breve no identifica completamente un campo. Dos mensajes con la
misma cantidad pueden ser distintos si cambia su nivel, intervalo estadístico,
tiempo válido o grilla.

### Consideraciones de los archivos GRIB2

La descripción anterior corresponde al formato GRIB2 general. Trabaja 
con las salidas de modelos numéricos seleccionadas por el proyecto, 
que cumplen estas propiedades de origen:

- cada archivo contiene todos los campos de un único tiempo válido y todos sus
  mensajes comparten la misma grilla;
- una corrida entrega un archivo por tiempo válido, con una sola hora de
  referencia, dominio y grilla; se requieren al menos tres archivos;
- los niveles y las variables permanecen durante toda la corrida. Los campos
  persistentes aparecen en todos los tiempos; los acumulados pueden aparecer
  desde el segundo tiempo y algunos campos sólo aparecen en el primero;
- `short_name`, obtenido con `-names ncep`, es único para la terna
  disciplina-categoría-parámetro. Las diferencias entre campos con un mismo
  nombre breve sólo pueden corresponder a superficie vertical o proceso
  estadístico.

Estas propiedades permiten inspeccionar el primer mensaje de cada archivo para
validar su tiempo y grilla, sin repetir consultas equivalentes para sus demás
mensajes. También permiten definir el esquema de salida con el primer, segundo
y último archivo de la corrida: representan respectivamente los campos
iniciales, los acumulados y persistentes, y el horizonte final. No se admite
una fuente cuyos niveles o variables aparezcan sólo en tiempos intermedios.

## 2. Secciones de un mensaje GRIB2

| Sección | Contenido | Uso en el proyecto |
|---:|---|---|
| 0 | Indicador: edición GRIB y disciplina. | Aporta la disciplina. |
| 1 | Identificación: centro, subcentro, tablas y hora de referencia. | Define origen y versiones de tablas. |
| 2 | Uso local opcional. | Sólo se interpreta con documentación del productor. |
| 3 | Definición de grilla. | Define geometría y proyección. |
| 4 | Definición del producto. | Parámetro, superficie(s), tiempo y estadística. |
| 5 | Representación de datos. | Describe la codificación de valores. |
| 6 | Mapa de bits. | Indica puntos con datos, si existe. |
| 7 | Datos codificados. | Contiene los valores. |
| 8 | Fin del mensaje. | Cierra el mensaje. |

Las secciones 1, 3 y 4 son las principales para el inventario. Las secciones 5
a 7 permiten decodificar las matrices, pero no reemplazan la interpretación
semántica de las primeras secciones.

## 3. Los códigos se interpretan con tablas

GRIB2 guarda muchos metadatos como números. El número debe leerse con la tabla
que corresponde y con la versión de tabla declarada por el mensaje.

| Código | Tabla o contexto | Ejemplo |
|---|---|---|
| Centro y subcentro | Tabla de centros WMO/NCEP. | 7 es NCEP; 98 es ECMWF. |
| Disciplina, categoría y parámetro | Tablas de parámetros GRIB2. | 0-0-0 es temperatura meteorológica. |
| Tipo de superficie | Tabla 4.5. | 100 es isobárica; 103 es altura sobre el suelo. |
| Procesamiento estadístico | Tabla 4.10. | 0 promedio; 1 acumulación; 2 máximo; 3 mínimo. |

El inventario conserva el código original además de etiquetas legibles como
500mb, 2 m above ground o acc. La etiqueta ayuda a leer, pero no sustituye al
código ni a la tabla.

## 4. Centro productor, subcentro y tablas locales

La sección 1 incluye centro originador, subcentro, versión de tabla maestra y
versión de tabla local. El centro es indispensable cuando aparece una
definición reservada para uso local.

| Fuente | Centro GRIB2 | Nombre | Subcentro |
|---|---:|---|---:|
| ETA | 7 | US National Weather Service – NCEP | 0 |
| GFS | 7 | US National Weather Service – NCEP | 0 |
| IFS | 98 | European Centre for Medium-Range Weather Forecasts (ECMWF) | 0 |

Los valores 192 a 254 de categoría o parámetro suelen estar reservados para uso
local. No son errores: su significado depende del centro y, cuando aplica, de
la tabla local. Por ejemplo, el significado de 0-1-193 de ECMWF no puede
deducirse de una definición NCEP con los mismos números.

La opción -names ncep de WGRIB2 es útil para presentar nombres conocidos por la
herramienta; no transforma una definición local de ECMWF en una definición
NCEP. Los valores locales de centros distintos de NCEP requieren la
documentación del centro antes de remapearse.

## 5. Identidad de una cantidad y del campo completo

La cantidad física base se expresa mediante una firma:

~~~
disciplina-categoría-parámetro
~~~

Por ejemplo, 0-0-0 identifica temperatura meteorológica. La terna es necesaria,
pero no basta para seleccionar un campo ni para definir una variable NetCDF.

La identidad completa necesita, como mínimo:

~~~
centro + subcentro + tabla maestra + tabla local
+ disciplina + categoría + parámetro
+ definición vertical + procesamiento estadístico
+ referencia temporal + tiempo/intervalo válido + grilla
~~~

No se deben mezclar temperatura a 2 m y a 500 hPa, precipitación instantánea y
acumulada, ni parámetros locales de centros distintos que compartan una firma.

Al revisar tablas se distingue entre definido, reservado, reservado para uso
local y ausente (255). Un valor reservado no debe recibir significado por
inferencia.

## 6. Niveles, superficies y composición vertical

La definición vertical está en la sección 4 y no es sólo un sufijo. La Tabla
4.5 asocia el tipo de superficie con unidades y significado.

| Tipo | Significado resumido | Presentación frecuente |
|---:|---|---|
| 1 | Superficie terrestre o de agua. | surface / sfc |
| 8 | Tope nominal de la atmósfera. | atmos col / clm |
| 100 | Superficie isobárica, en Pa. | 500mb |
| 101 | Nivel medio del mar. | mean sea level / msl |
| 103 | Altura especificada sobre el suelo, en m. | 2 m above ground |
| 151 | Profundidad bajo tierra, en m. | nivel de suelo |

La salida de g2ctl/WGRIB2 puede representar una o dos superficies. El bloque
vertical crudo se debe conservar. El patrón habitual tipo,valor aparece, por
ejemplo, como 103,2: altura de 2 m sobre el suelo. Hay excepciones válidas:

- 1 representa una superficie única sin valor escalar.
- 1,,,8 representa dos superficies: suelo/agua y tope nominal de la atmósfera.
  Es una columna o capa, no un simple código-valor.
- Una capa de suelo puede expresarse con dos valores, como 151,0,1.

La exploración de IFS confirmó mensajes 1,,,8, incluso para parámetros locales.
Por eso clm no basta para recuperar la semántica vertical; el inventario debe
guardar el bloque vertical completo.

El conversor actual reconoce niveles isobáricos por textos como 500mb y los
agrupa sobre lev. Las demás superficies se mantienen como campos de superficie
hasta que una regla explícita justifique otra estructura.

## 7. Tiempo y procesamiento estadístico

Un mensaje tiene hora de referencia y datos que definen su validez temporal.
En variables estadísticas no basta con el instante final: también importan el
intervalo y la operación aplicada.

| Código | Etiqueta frecuente | Significado |
|---:|---|---|
| 0 | ave | Promedio. |
| 1 | acc | Acumulación. |
| 2 | max | Máximo. |
| 3 | min | Mínimo. |

-ctl_inv expresa con frecuencia este dato de dos maneras: el cuarto componente
de la definición de parámetro, por ejemplo 0,1,193,1, y una etiqueta como acc.
Ese cuarto componente es el **tipo de procesamiento estadístico**, no el
indicador de tabla local. Cuando no hay procesamiento se observa none y el
cuarto componente puede no existir.

Se conservan none, ave, acc, max y min para no confundir campos instantáneos
con campos que sintetizan un periodo.

## 8. Herramientas empleadas

### WGRIB2: inventario de cabeceras

WGRIB2 recorre mensajes sin leer sus matrices en Python. Sirve para inspeccionar
nombres, tiempos, nivel, grilla, metadatos de parámetro y centro.

~~~bash
wgrib2 archivo.grib2 -s
wgrib2 archivo.grib2 -grid
wgrib2 archivo.grib2 -center -subcenter
~~~

El resultado es texto de inventario. Sus campos deben parsearse según los
argumentos usados: cambiar argumentos cambia la posición y contenido de los
bloques separados por dos puntos. El stdout crudo es evidencia y debe
conservarse en investigaciones de datos locales o comparaciones de comandos.

### PyGRIB: coordenadas y matrices

PyGRIB abre el GRIB2 para obtener coordenadas y valores. Después del inventario
WGRIB2, el proyecto usa PyGRIB para leer la grilla con latlons() y las matrices
con values.

~~~python
import pygrib

with pygrib.open("archivo.grib2") as source:
    message = source.message(1)
    latitude, longitude = message.latlons()
    values = message.values
~~~

values tiene forma (ny, nx). Las coordenadas devueltas tienen la misma
geometría y son la referencia espacial: no se deduce una proyección sólo desde
nx por ny.

### ecCodes: parámetros ECMWF

scripts/inspect_ecmwf_parameter.py consulta las definiciones locales instaladas
por ecCodes y busca candidatos de paramId desde disciplina-categoría-parámetro.
Es una herramienta de investigación: no abre GRIB2 ni aprueba remapeos.

Para validar un candidato ECMWF se requieren condiciones adicionales, como
localTablesVersion, typeOfStatisticalProcessing, definición vertical, plantilla
de producto y otras claves ecCodes. Un paramId queda identificado sólo si esas
condiciones coinciden con el mensaje real.

## 9. Inventario de MetVis3D

El inventario de diagnóstico tiene una fila por mensaje y conserva datos
suficientes para repetir una revisión sin inferir semántica desde abreviaturas.
El conversor usa el contrato de las salidas de modelo para separar esa tarea de
la escritura: valida metadatos con el primer mensaje de cada archivo, define
las variables con el primer, segundo y último archivo, y vuelve a consultar el
inventario de cada archivo al asociar sus mensajes con PyGRIB.

| Grupo | Datos que se deben preservar |
|---|---|
| Procedencia | Archivo, posición de mensaje y stdout crudo o referencia reproducible. |
| Tiempo | Referencia, tiempo válido e intervalo cuando exista. |
| Grilla | Tamaño y datos para validar homogeneidad de la corrida. |
| Nivel | Nivel textual, sufijo y bloque vertical crudo de ctl_inv. |
| Parámetro | Nombre WGRIB2, definición completa, firma y cuarto componente. |
| Estadística | Etiqueta y código de procesamiento. |
| Tablas y origen | Disciplina, tabla maestra, tabla local, centro y subcentro. |
| Normalización | Firma, nombre final, estado local y remapeo aplicado. |

La representación con `-lev`, `-lev0`, `-varX` y `-ctl_inv` reúne nivel
legible, bloque vertical, tablas, centro y estadística en una línea. Durante la
escritura, su número de mensaje asocia esa línea con `pygrib.message(...)`.

WGRIB2 entrega siempre una descripción con unidades en estas fuentes. Cuando
la unidad es `[-]`, se conserva como el indicador explícito de una cantidad sin
unidad física, no como falta de metadato.

Los inventarios exploratorios, CSV, tiempos y stdout crudo viven en
outputs/grib2-analysis/. Son evidencia de una ejecución, no una definición
normativa.

## 10. Parámetros locales y remapeos

El proyecto trata como potencialmente locales categorías o números entre 192 y
254 en las disciplinas trabajadas. Esta detección indica que debe investigarse;
no traduce automáticamente el parámetro.

Para proponer o revisar un remapeo se requiere:

1. Centro y subcentro originadores.
2. Versión de tabla maestra y localTablesVersion.
3. Disciplina, categoría y número de parámetro.
4. Definición vertical completa, incluida segunda superficie si existe.
5. Plantilla de producto, intervalo válido y typeOfStatisticalProcessing.
6. Nombre, unidades, descripción y paramId del centro cuando corresponda.
7. Nombre final, factor y desplazamiento aprobados.

config/grib2-definitions.yaml es el único lugar donde el conversor actual
aplica remapeos. Hoy las reglas ECMWF se identifican por centro y firma. El
inventario enriquecido permitirá evaluar si una regla necesita tabla local,
estadística o definición vertical. Sin regla aprobada, se conserva procedencia,
se advierte y no se atribuye significado por analogía.

## 11. De mensaje GRIB2 a nombre NetCDF

El flujo actual de `Grib2ToNetCDF` es:

~~~
archivos GRIB2 homogéneos
  -> WGRIB2: primer mensaje de cada archivo para tiempo y grilla
  -> WGRIB2: primer, segundo y último archivo para definir variables
  -> identidad, nivel, superficie, estadística y reglas YAML
  -> WGRIB2 + PyGRIB: asociación por número de mensaje al escribir cada archivo
  -> NetCDF: un archivo final por corrida
~~~

La nomenclatura inicial procede de `-names ncep`. El conversor agrupa primero
los mensajes por firma, superficie y proceso estadístico, y sólo después
construye el nombre final. En la implementación vigente:

- los niveles isobáricos se agrupan como `short_name + prs`; por ejemplo,
  `TMPprs` antes de normalizar;
- otros niveles forman parte del nombre; por ejemplo, tmp2m;
- el proceso estadístico se incorpora sólo cuando es necesario para evitar una
  colisión de nombres;
- un remapeo sustituye el nombre breve inicial y conserva la diferenciación por
  nivel y proceso estadístico;
- los nombres finales se pasan a minúsculas al terminar la desambiguación. Los
  nombres estándar NCEP se reciben en mayúsculas y las definiciones locales
  pueden recibirse en minúsculas; la normalización final permite detectar una
  definición local incorrecta que colisione con otra variable.

Estas convencions se tomaron del script g2ctl de NCEP, no nombres universales GRIB2. 
Una colisión quepersista tras estas reglas detiene la conversión. La semántica 
temporal de losacumulados, promedios, máximos y mínimos se conserva como viene 
de la fuente; el conversor no la redefine.

## 12. Contrato de salida NetCDF

Una corrida homogénea genera un único NetCDF. No se crean productos parciales
por variable o por tiempo, ni se sobrescribe una salida existente.

~~~
time                         tiempos válidos
lev                          niveles isobáricos nativos, si existen
latitude, longitude          coordenadas de la grilla

superficie:  (time, latitude, longitude)
presión:     (time, lev, latitude, longitude)
~~~

lev conserva niveles isobáricos nativos en orden descendente, con unidades
millibars. Las coordenadas horizontales usan degrees_north y degrees_east. Las
variables se escriben como float32 con compresión zlib y
least_significant_digit=2; las verificaciones numéricas consideran esa
cuantización.

El NetCDF conserva `parameter_signature`, información de centro y tablas,
superficie y proceso estadístico. El nombre de variable y sus atributos
describen el resultado final del remapeo. Cuando corresponde, se registra la aplicación
del remapeo y su transformación. Hora de referencia, centro, modelo, dominio y
convención longitudinal quedan como atributos.

## 13. Grilla, longitudes y recorte

Cada mensaje declara su grilla. Por el contrato de las salidas de modelo, el
primer mensaje representa la grilla del archivo; WGRIB2 comprueba entre
archivos la hora de referencia, el dominio, las dimensiones y la plantilla de
grilla. PyGRIB obtiene las coordenadas reales. Las fuentes actuales se tratan
como grillas geográficas rectangulares; otra proyección o geometría exige
revisión previa.

El recorte se expresa como (west, south, east, north) en -180..180, debe estar
dentro de la fuente y no puede cruzar el antimeridiano. La salida puede ordenar
longitudes en 0_360 o -180_180. Se seleccionan puntos existentes: no hay
interpolación ni remuestreo.

## 14. Protocolo para una fuente o parámetro nuevo

1. Guardar inventario WGRIB2 crudo y registrar centro, tablas, grilla, tiempos,
   nivel y estadísticas.
2. Confirmar una sola corrida con hora de referencia, dominio y grilla comunes.
3. Para cada firma local, consultar el centro y contrastar todas las
   condiciones, no sólo la terna.
4. Proponer nombre, unidades, descripción y transformación trazables; validarlo
   científicamente antes de incorporarlo al YAML.
5. Comparar un NetCDF de prueba con el GRIB2: identidad, unidades, tiempo,
   nivel, orientación espacial, recorte y valores.
6. Documentar faltantes y ambigüedades. Una advertencia no es definición
   científica.

## 15. Referencias primarias

- [Documentación GRIB2 de NCEP/NOAA](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/): índice de secciones, tablas y plantillas.
- [Sección 1 — Identificación](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_sect1.shtml): centro, subcentro y versiones de tablas.
- [Tabla de centros WMO/NCEP](https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html): códigos de centros productores.
- [Tabla 4.5 — tipos de superficies fijas](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-5.shtml): niveles y unidades verticales.
- [Tabla 4.10 — procesamiento estadístico](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-10.shtml): promedio, acumulación, máximo y mínimo.
- [Tabla 4.2 — parámetros por disciplina y categoría](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2.shtml): entrada a tablas de parámetros NCEP.
- [Base de parámetros ECMWF](https://codes.ecmwf.int/grib/param-db/): referencia para parámetros y paramId de ECMWF.

## 16. Límites y mantenimiento

La guía registra decisiones estables y el estado conocido de la lectura GRIB2.
Los experimentos de rendimiento, reportes fechados y planes históricos no son
parte de su contrato.

La sección de inventario se actualizará junto con Grib2ToNetCDF, los reportes y
los scripts que dependan de sus columnas. Hasta que ese cambio sea verificado,
la implementación vigente sigue siendo la fuente operativa para el comando y
su parser.
