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

**Fecha:** 2026-09-23  
**Decisión:** WGRIB2 construye el inventario completo de mensajes y resuelve la
nomenclatura NCEP; PyGRIB obtiene la grilla y lee las matrices; NetCDF4 escribe
el producto final. La asociación entre inventario y matriz se conserva por la
posición del mensaje dentro de cada archivo.

**Motivo:** cada herramienta se utiliza para la parte del formato GRIB2 que
interpreta de forma fiable, sin conversiones intermedias.

**Impacto:** el NetCDF conserva por variable `parameter_signature` y
`wgrib2_short_name`. El eje temporal recoge los tiempos válidos disponibles;
el conversor no completa ni infiere plazos faltantes.

## D-005 — Remapeo y selección de variables

**Fecha:** 2026-09-23  
**Decisión:** los parámetros locales se remapean únicamente mediante reglas
explícitas de `config/grib2-definitions.yaml`. La selección opcional usa los
nombres finales resultantes de esos remapeos y se configura por modelo.

**Motivo:** los códigos locales no son homogéneos entre centros productores;
las transformaciones deben ser explícitas y rastreables.

**Impacto:** una regla puede definir nombre, unidades, `factor`, `offset` y
`long_name`. Los atributos de remapeo se escriben en el NetCDF. Un parámetro
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
