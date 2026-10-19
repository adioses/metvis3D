# Decisiones del proyecto

Este archivo registra decisiones vigentes que afectan el alcance, la operación
o el contrato de datos del proyecto. No es un diario de desarrollo.

## D-001 — Entorno local y despliegue HPC

**Fecha:** 2026-09-15, actualizada 2026-09-29
**Decisión:** el desarrollo local se realiza con Docker Compose y Micromamba.
El despliegue en HPC se realizará con Conda usando el mismo `environment.yml`,
sin depender de Docker.

**Impacto:** la lógica operativa no depende de rutas o servicios exclusivos del
contenedor; Docker reproduce el entorno local y Conda permite ejecutarlo en el
HPC.

## D-002 — Un NetCDF final por corrida

**Fecha:** 2026-09-15, actualizada 2026-09-23
**Decisión:** una corrida homogénea de un modelo produce un único NetCDF final.
No se generan NetCDF parciales por variable o tiempo, y la salida no
sobrescribe un archivo existente.

**Impacto:** los GRIB2 de entrada pertenecen a una sola corrida, con la misma
hora de referencia, dominio y grilla. El nombre de salida es
`{center}-{model}_{YYYYmmdd}_{HH}Z.nc`.

## D-003 — Estructura canónica del NetCDF

**Fecha:** 2026-09-23
**Decisión:** las dimensiones canónicas son `time`, `lev`, `latitude` y
`longitude`. Los campos de superficie usan `(time, latitude, longitude)` y los
isobáricos `(time, lev, latitude, longitude)`.

**Impacto:** `lev` conserva niveles nativos descendentes en `millibars`; las
coordenadas horizontales usan `degrees_north` y `degrees_east`.

## D-004 — Lectura y trazabilidad de GRIB2

**Fecha:** 2026-09-23, actualizada 2026-10-05
**Decisión:** el conversor se especializa en corridas con un archivo por tiempo
válido, una grilla común y una sola hora de referencia. WGRIB2 valida los
metadatos e inventaría mensajes; PyGRIB lee las matrices; NetCDF4 escribe la
salida.

**Impacto:** el esquema se define desde el primer, segundo y último archivo;
cada mensaje conserva procedencia suficiente para revisar variable, superficie,
proceso estadístico y remapeo.

## D-005 — Remapeo y selección de variables

**Fecha:** 2026-09-23, actualizada 2026-10-08
**Decisión:** los parámetros locales sólo se remapean mediante reglas explícitas
en `config/grib2-definitions.yaml`. La selección opcional usa los nombres
finales resultantes.

**Impacto:** una regla define nombre, unidades, `factor`, `offset` y
`long_name`; una regla incompleta o no aplicable detiene la conversión.

## D-006 — Coordenadas, recorte y conservación de valores

**Fecha:** 2026-09-23
**Decisión:** el área de recorte se expresa como `(west, south, east, north)`
en `-180..180`, debe estar dentro del dominio y no puede cruzar el
antimeridiano. La salida puede usar longitudes `0_360` o `-180_180`.

**Impacto:** se reordenan coordenadas y columnas de matriz de forma conjunta;
no se interpola ni remuestrea. Sólo se aplican `factor` y `offset` de un
remapeo aprobado.

## D-007 — Escritura y atributos del NetCDF

**Fecha:** 2026-09-23
**Decisión:** las variables meteorológicas se escriben como `float32`, con
compresión `zlib` y `least_significant_digit=2`.

**Impacto:** el NetCDF registra modelo, centro, dominio, hora de referencia,
convención longitudinal y metadatos de procedencia. Las verificaciones
científicas consideran la cuantización decimal declarada.

## D-009 — Metadatos CF para NetCDF de pronóstico

**Fecha:** 2026-10-13
**Decisión:** los NetCDF generados declaran `Conventions=CF-1.10`. Las
coordenadas `time`, `lev`, `latitude` y `longitude` incluyen nombres estándar
CF; `lev` declara `standard_name=air_pressure` y `positive=down`.

**Impacto:** el tiempo se expresa en horas desde la inicialización de la
corrida y los consumidores recuperan los mismos tiempos válidos sin transformar
campos, niveles ni grilla.

## D-010 — Flujo actual de animaciones con Met.3D

**Fecha:** 2026-10-19
**Decisión:** Met.3D opera de forma independiente bajo `config/met3d/`, con
escenas, animaciones, sesiones y runtime propios. DANA y jet usan el motor
común `src/visualize/met3d_animation.py`; sus lanzadores reciben un NetCDF
estandarizado y materializan configuraciones temporales por corrida.

**Impacto:** el runtime se limita a `met3D/.runtime/`; los MP4 históricos se
guardan bajo `outputs/met3d/`. Las cámaras, objetos, intervalos de presión y
salida se mantienen en los YAML de cada animación, sin intervenir en ParaView.

## D-011 — Flujo actual de animaciones con ParaView

**Fecha:** 2026-10-19
**Decisión:** ParaView opera de forma independiente bajo `config/paraview/`.
Una escena define geografía, proyección, DEM y estilo; una animación define
capas, variables, intervalos verticales, cámara, línea de tiempo y salida. La
lógica científica se organiza en `src/visualize/paraview/`.

**Impacto:** los temporales se organizan por escena y capa en
`paraview/render_data/`; los fotogramas transitorios de una escena se guardan
en `paraview/render_cache/`; los MP4 históricos se almacenan en
`outputs/paraview/`. La capa jet construye su geometría desde `hgtprs` y puede
completar únicamente huecos aislados declarados en su YAML, sin alterar el
NetCDF estandarizado.
