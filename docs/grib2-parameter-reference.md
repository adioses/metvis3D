# Referencia de identidad de parámetros GRIB2

## Propósito

Este documento explica cómo se identifica la cantidad meteorológica de un
mensaje GRIB2 y reúne los rangos publicados por NCEP para detectar códigos
reservados y códigos reservados para uso local. Es una referencia para el
inventario y para investigar equivalencias entre centros; no define todavía
la configuración YAML ni implementa el conversor.

La fuente del catálogo es la [Code Table 4.2 de NCEP/NOAA](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2.shtml), revisada por NCEP el 18 de septiembre de 2025. Las
tablas de un centro pueden cambiar con el tiempo, por lo que la fecha de la
referencia debe conservarse al derivar una configuración operativa.

## Identidad de una cantidad meteorológica

La cantidad física base se expresa mediante una terna:

~~~text
disciplina - categoría - número de parámetro
~~~

Por ejemplo, 0-0-0 significa productos meteorológicos, categoría de
temperatura y parámetro temperatura. La tabla 4.2 sitúa estos valores en la
Sección 0 (disciplina) y Sección 4 (categoría y número de parámetro) de GRIB2.

La terna no identifica por sí sola un campo que pueda escribirse directamente
en NetCDF. La selección científica completa debe sumar:

1. El centro originador y, para extensiones, la versión de tabla local.
2. El tipo y el valor de nivel: por ejemplo, superficie, 2 m sobre el suelo o
   500 hPa.
3. El procesamiento temporal: instantáneo, promedio, acumulación, máximo o
   mínimo, y su intervalo temporal.

Así, 0-0-0 es la cantidad temperatura, pero temperatura a 2 m y temperatura a
500 hPa son campos distintos. El procesamiento temporal también evita
confundir una cobertura nubosa instantánea con una promediada, o una
acumulación de precipitación con una tasa de precipitación.

WGRIB2 con -names ncep aporta la convención de nombres NCEP para las
definiciones que conoce. Ese nombre es una presentación útil, no reemplaza la
identidad GRIB2 completa. En particular, un código local del mismo número puede
tener un significado diferente cuando proviene de otro centro.

## Estados que debe reconocer el inventario

| Estado | Significado | Tratamiento de análisis futuro |
|---|---|---|
| Definido | La tabla publica la categoría o parámetro. | Puede investigarse y seleccionarse por su firma completa. |
| Reservado | La tabla marca el código como reservado. | Advertir e investigar; no atribuir significado físico. |
| Reservado para uso local | La tabla reserva el código para que cada centro defina su significado. | Para un centro ajeno a NCEP, buscar una regla YAML por centro y firma completa; sin regla, advertir. |
| Ausente (255) | El valor codifica Missing. | No representa una cantidad meteorológica seleccionable. |
| No publicado en el índice | El número no aparece como tabla ni como rango en el índice consultado. | Advertir como categoría no documentada por esta referencia; no inferir su estado. |

La detección debe evaluar tanto la categoría como el número de parámetro. Una
categoría puede ser local aunque su número de parámetro no sea alto: NCEP
publica una tabla de covarianza en la categoría local 0-192.

## Rangos de categorías por disciplina

Las “categorías con tabla” son las que el índice enlaza explícitamente.

| Disciplina | Producto | Categorías con tabla publicadas | Categorías reservadas | Categorías para uso local | Observación |
|---:|---|---|---|---|---|
| 0 | Meteorológicos | 0–7, 13–22, 190, 191 | 23–189 | 192–254 | NCEP también publica 0-192 como asignación local. Las categorías 8–12 no figuran en el índice actual. |
| 1 | Hidrológicos | 0–2 | 3–191 | 192–254 | |
| 2 | Superficie terrestre | 0, 1, 3–7 | 8–191 | 192–254 | La categoría 2 no figura en el índice actual. |
| 3 | Teledetección satelital | 0–6 | 7–191 | 192–254 | NCEP también publica 3-192 como asignación local. |
| 4 | Meteorología espacial | 0–10 | 11–191 | 192–254 | |
| 10 | Oceanográficos | 0–4, 191 | 5–190 | 192–254 | |
| 20 | Impactos sanitarios y socioeconómicos | 0–5 | 6–191 | 192–254 | |
| 191 | Parámetros computacionales | 0 | 1–191 | 192–254 | |

Esta relación no clasifica disciplinas que no aparecen en el índice de NCEP.
Un inventario que las encuentre debe informarlo en vez de asumir que son
meteorológicas o locales.

## Rangos de parámetros por disciplina y categoría

Las tablas siguientes contienen todas las subtablas enlazadas por el índice
consultado. “Uso local base” es el rango marcado como Reserved for Local Use.
“Reservado” reproduce los rangos que la subtabla marca literalmente como
Reserved. Cuando hay reservas dentro del espacio local de NCEP se señala con
un asterisco.

Los valores que NCEP detalla dentro de un rango local son asignaciones de NCEP.
No deben usarse para interpretar automáticamente un mensaje ECMWF u otro
centro.

### Disciplina 0: productos meteorológicos

| Categoría | Tema | Parámetros reservados | Uso local base | Nota NCEP |
|---:|---|---|---|---|
| 0 | Temperatura | 33–191 | 192–254 | |
| 1 | Humedad | 63, 89, 172–191 | 192–254 | El ejemplo ECMWF 0-1-193 pertenece a este rango local. |
| 2 | Momento | 71–191 | 192–254 | |
| 3 | Masa | 47–191 | 192–254 | |
| 4 | Radiación de onda corta | 16–49, 64–191 | 192–254 | |
| 5 | Radiación de onda larga | 14–191 | 192–254 | |
| 6 | Nubes | 41–46, 52–191 | 192–254 | El ejemplo ECMWF 0-6-192 pertenece a este rango local. |
| 7 | Índices de estabilidad termodinámica | 28–191 | 192–254 | |
| 13 | Aerosoles | 1–191 | 192–254 | |
| 14 | Gases traza | 3–191 | 192–254 | |
| 15 | Radar | 21–191 | 192–254 | |
| 16 | Imagen de radar pronosticada | 9–191 | 192–254 | |
| 17 | Electrodinámica | 6–191 | 192–254 | |
| 18 | Nuclear y radiología | 27–191 | 192–254 | |
| 19 | Propiedades físicas atmosféricas | 53–191; 227–231* | 192–254 | *Reserva de NCEP dentro de su espacio local. |
| 20 | Constituyentes químicos atmosféricos | 20–49, 85–99, 114–191 | 192–254 | |
| 21 | Propiedades termodinámicas | 23–191 | 192–254 | |
| 22 | Índices de sequía | 7–191 | 192–254 | |
| 190 | Cadena CCITT IA5 | 1–191 | 192–254 | |
| 191 | Misceláneos | 8–191 | 192–254 | |
| 192 | Covarianza | No publica un rango reservado | Categoría local | NCEP asigna los parámetros 1–14; no hay semántica universal. |

### Disciplina 1: productos hidrológicos

| Categoría | Tema | Parámetros reservados | Uso local base |
|---:|---|---|---|
| 0 | Hidrología básica | 25–191 | 192–254 |
| 1 | Probabilidades hidrológicas | 3–191 | 192–254 |
| 2 | Propiedades de agua continental y sedimentos | 24–191 | 192–254 |

### Disciplina 2: productos de superficie terrestre

| Categoría | Tema | Parámetros reservados | Uso local base |
|---:|---|---|---|
| 0 | Vegetación y biomasa | 64–191 | 192–254 |
| 1 | Productos especiales agrícolas y acuícolas | 0–191 | 192–254 |
| 3 | Productos de suelo | 31–191 | 192–254 |
| 4 | Productos de tiempo para incendios | 45–191 | 192–254 |
| 5 | Glaciares y hielo continental | 2–191 | 192–254 |
| 6 | Áreas urbanas | 9–191 | 192–254 |
| 7 | Propiedades termodinámicas | 3–191 | 192–254 |

### Disciplina 3: productos de teledetección satelital

| Categoría | Tema | Parámetros reservados | Uso local base | Nota NCEP |
|---:|---|---|---|---|
| 0 | Formato de imagen | 10–191 | 192–254 | |
| 1 | Productos cuantitativos | 25–26, 33–97, 100–191 | 192–254 | |
| 2 | Propiedades de nubes | 12–29, 41–191 | 192–254 | |
| 3 | Condiciones de reglas de vuelo | 3–191 | 192–254 | |
| 4 | Ceniza volcánica | 9–191 | 192–254 | |
| 5 | Temperatura de superficie del mar | 6–191 | 192–254 | |
| 6 | Radiación solar | 6–191 | 192–254 | |
| 192 | Imágenes satelitales pronosticadas | 88–191 | 192–254 | Categoría local publicada por NCEP. |

### Disciplina 4: productos de meteorología espacial

| Categoría | Tema | Parámetros reservados | Uso local base |
|---:|---|---|---|
| 0 | Temperatura | 6–191 | 192–254 |
| 1 | Momento | 4–191 | 192–254 |
| 2 | Masa y número de partículas cargadas | 14–191 | 192–254 |
| 3 | Campos eléctricos y magnéticos | 8–191 | 192–254 |
| 4 | Partículas energéticas | 7–191 | 192–254 |
| 5 | Ondas | 4–191 | 192–254 |
| 6 | Emisiones electromagnéticas solares | 7–191 | 192–254 |
| 7 | Emisiones electromagnéticas terrestres | 4–191 | 192–254 |
| 8 | Imágenes | 9–191 | 192–254 |
| 9 | Acoplamiento ion-neutral | 3–191 | 192–254 |
| 10 | Índices de meteorología espacial | 8–191 | 192–254 |

### Disciplina 10: productos oceanográficos

| Categoría | Tema | Parámetros reservados | Uso local base | Nota NCEP |
|---:|---|---|---|---|
| 0 | Olas | 105–191 | 192–254 | |
| 1 | Corrientes | 7–191 | 192–254 | |
| 2 | Hielo | 32–191 | 192–254 | |
| 3 | Propiedades de superficie | 23–191; 211–241* | 192–254 | *Reserva de NCEP dentro de su espacio local. |
| 4 | Propiedades subsuperficiales | 8–10, 59–191 | 192–254 | |
| 191 | Misceláneos | 5–191 | 192–254 | |

### Disciplina 20: impactos sanitarios y socioeconómicos

| Categoría | Tema | Parámetros reservados | Uso local base |
|---:|---|---|---|
| 0 | Indicadores de salud | 13–191 | 192–254 |
| 1 | Epidemiología | 10–191 | 192–254 |
| 2 | Indicadores socioeconómicos | 1–191 | 192–254 |
| 3 | Sector de energía renovable | 10–191 | 192–254 |
| 4 | Índices de peligro meteorológico e hidrológico | 61–190 | 191–254 |
| 5 | Índices de peligro ambiental | 25–190 | 191–254 |

### Disciplina 191: parámetros computacionales

| Categoría | Tema | Parámetros reservados | Uso local base |
|---:|---|---|---|
| 0 | Parametrizaciones estocásticas | 6–191 | 192–254 |

## Lectura correcta de los rangos locales

Un rango de uso local no es un diccionario universal. Significa que la
organización originadora puede asignarle significado propio. Por ello:

- 0-1-193 en la tabla local NCEP no determina el significado de 0-1-193
  producido por ECMWF.
- 0-6-192 tampoco se interpreta mediante una asignación local NCEP cuando el
  mensaje tiene centro originador ECMWF.
- Las filas marcadas con asterisco son reservas de NCEP dentro de su espacio
  local. No anulan el carácter local del rango para otros centros.

Para GFS/NCEP, el inventario con -names ncep puede usar las definiciones que
WGRIB2 conoce de NCEP. Para ECMWF u otro centro, una coincidencia dentro de un
rango local requiere consultar documentación del centro y, sólo después,
registrar una equivalencia explícita en YAML.

## Implicación para las advertencias futuras

La documentación permite definir la siguiente política de inventario, que aún
debe aprobarse al diseñar el conversor:

1. Informar una categoría reservada, local o no publicada.
2. Informar un parámetro reservado o local.
3. Si la firma es local y el centro no es NCEP, buscar una equivalencia
   configurada por centro, versión de tabla local, disciplina, categoría,
   parámetro, nivel y procesamiento temporal.
4. Si no existe esa equivalencia, emitir una advertencia que preserve todos
   esos metadatos y no renombrar ni convertir el campo por inferencia.

La advertencia identifica una necesidad de revisión científica; no demuestra
por sí misma que el mensaje sea erróneo ni que deba recibir una equivalencia.

