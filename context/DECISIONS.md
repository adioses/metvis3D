# Decisiones del proyecto

Este archivo registra decisiones confirmadas que afectan el alcance, la
operación o el contrato de datos del proyecto. No es un diario de desarrollo.

## D-001 — Entorno local y despliegue HPC

**Fecha:** 2026-09-15, actualizada 2026-09-29  
**Decisión:** el desarrollo local se realiza con Docker Compose y Micromamba.
El despliegue en el HPC se realizará con Conda usando el mismo
`environment.yml`, sin depender de Docker.

**Motivo:** el contenedor ofrece un entorno Linux reproducible en desarrollo,
mientras que el HPC no requiere ni presupone disponibilidad de Docker.

**Impacto:** la lógica operativa no depende de servicios o rutas exclusivas del
contenedor. Las versiones de las dependencias de ejecución se fijan en
`environment.yml`; Docker sólo crea el entorno local equivalente.

## D-002 — Un NetCDF final por corrida

**Fecha:** 2026-09-15, actualizada 2026-09-23  
**Decisión:** una corrida homogénea de un modelo produce un único NetCDF final.
No se generan NetCDF parciales por variable ni por tiempo, y la salida no
sobrescribe un archivo existente.

**Motivo:** concentrar los campos de una corrida facilita el consumo posterior
y preserva una unidad de trabajo identificable por centro, modelo y hora de
inicialización.

**Impacto:** los archivos GRIB2 de entrada deben pertenecer a una sola corrida,
con la misma hora de referencia, dominio y tamaño de grilla. El nombre de
salida es `{center}-{model}_{YYYYmmdd}_{HH}Z.nc`.

## D-003 — Estructura canónica del NetCDF

**Fecha:** 2026-09-23  
**Decisión:** las dimensiones canónicas son `time`, `lev`, `latitude` y
`longitude`. Los campos de un solo nivel usan `(time, latitude, longitude)`; 
los campos isobáricos usan `(time, lev, latitude, longitude)`.

**Motivo:** establecer una estructura común para GFS, ECMWF, ETA y fuentes futuras
sin alterar la naturaleza vertical de los datos de origen.

**Impacto:** `time` es ilimitada y contiene tiempos válidos. `lev` sólo se crea
cuando hay campos isobáricos; conserva los niveles nativos en orden
descendente, con unidades `millibars`. Las coordenadas horizontales usan
`degrees_north` y `degrees_east`.

## D-004 — Lectura y trazabilidad de GRIB2

**Fecha:** 2026-09-23, actualizada 2026-10-05

**Decisión:** el conversor se especializa en las salidas de modelos numéricos
seleccionadas por el proyecto. Cada archivo aporta un único tiempo válido y una
misma grilla para todos sus mensajes; una corrida tiene un archivo por tiempo
válido, al menos tres archivos y una sola hora de referencia, dominio y grilla.
WGRIB2 consulta el primer mensaje de cada archivo para validar esos metadatos y
el primer, segundo y último archivo para definir variables y niveles. PyGRIB
lee las matrices y WGRIB2 asocia cada mensaje mediante su número explícito.
NetCDF4 escribe el producto final.

**Motivo:** las variables y niveles de estas salidas se mantienen en toda la
corrida. Los únicos campos no persistentes son los acumulados desde el segundo
tiempo y algunos campos exclusivos del primero. El muestreo de tres archivos
cubre esas variantes sin inventariar repetidamente metadatos idénticos. WGRIB2
resuelve la nomenclatura NCEP y proporciona siempre unidades; `[-]` indica una
cantidad sin unidad física.

**Impacto:** `short_name` es único por disciplina-categoría-parámetro en estas
fuentes; superficie y proceso estadístico completan la desambiguación de los
nombres NetCDF. El conversor aplica remapeos, resuelve colisiones y sólo al
final normaliza los nombres a minúsculas; una colisión restante detiene la
conversión. El NetCDF conserva `parameter_signature`, centro, tabla maestra y
tabla local, superficie, proceso estadístico y atributos de remapeo. No conserva el
`wgrib2_short_name` anterior al remapeo. El eje temporal reúne los tiempos
válidos de los archivos, sin completar ni inferir plazos faltantes.

## D-005 — Remapeo y selección de variables

**Fecha:** 2026-09-23, actualizada 2026-10-08
**Decisión:** los parámetros locales se remapean únicamente mediante reglas
explícitas de `config/grib2-definitions.yaml`. La selección opcional usa los
nombres finales resultantes de esos remapeos y se configura por modelo.

**Motivo:** los códigos locales no son homogéneos entre centros productores;
las transformaciones deben ser explícitas y rastreables.

**Impacto:** cada regla define obligatoriamente nombre, unidades, `factor`,
`offset` y `long_name`. Los atributos de remapeo se escriben en el NetCDF. Una
regla incompleta o que no pueda aplicarse detiene la conversión. Un parámetro
local sin regla conserva su definición NCEP y emite una advertencia.

## D-006 — Coordenadas, recorte y conservación de valores

**Fecha:** 2026-09-23  
**Decisión:** el área de recorte se expresa como `(west, south, east, north)`
en `-180..180`, debe estar contenida en el dominio y no puede cruzar el
antimeridiano. La salida permite las convenciones longitudinales `0_360` o
`-180_180`.

**Motivo:** el recorte debe ser consistente entre modelos y conservar los
valores de la grilla fuente.

**Impacto:** se reordenan coordenadas y columnas de las matrices de forma
conjunta. No se interpola ni remuestrea; las únicas transformaciones de valores
son `factor` y `offset` definidos en un remapeo aprobado.

## D-007 — Escritura y atributos del NetCDF

**Fecha:** 2026-09-23  
**Decisión:** las variables meteorológicas se escriben como `float32` con
compresión `zlib` y `least_significant_digit=2`. El NetCDF registra modelo,
centro, dominio, hora de referencia y convención longitudinal.

**Motivo:** reducir volumen de almacenamiento y mantener procedencia suficiente
para revisar una conversión sin perder la estructura científica del producto.

**Impacto:** los valores están sujetos a la cuantización decimal configurada.
Cada variable conserva unidades, `long_name` y metadatos de procedencia; las
verificaciones científicas deben considerar dicha cuantización.
