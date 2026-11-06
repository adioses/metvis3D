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

**Fecha:** 2026-09-23, actualizada 2026-11-02
**Decisión:** las variables meteorológicas se escriben como `float32`, con
compresión `zlib` y `least_significant_digit=2` por defecto. El mapa opcional
`standardization.least_significant_digit` del YAML de cada modelo permite
excepciones por nombre final: un entero no negativo establece la precisión y
`full` desactiva la cuantización adicional. GFS, IFS, ETA y WRF configuran
`spfhprs: full`, conservando la humedad específica en `kg/kg`.

**Impacto:** el NetCDF registra modelo, centro, dominio, hora de referencia,
convención longitudinal y metadatos de procedencia. Las verificaciones
científicas consideran la precisión efectiva de cada variable. `full` mantiene
`float32` y compresión; los NetCDF anteriores deben regenerarse desde los GRIB
originales para recuperar el detalle de humedad perdido por cuantización.

## D-009 — Metadatos CF para NetCDF de pronóstico

**Fecha:** 2026-10-13
**Decisión:** los NetCDF generados declaran `Conventions=CF-1.10`. Las
coordenadas `time`, `lev`, `latitude` y `longitude` incluyen nombres estándar
CF; `lev` declara `standard_name=air_pressure` y `positive=down`.

**Impacto:** el tiempo se expresa en horas desde la inicialización de la
corrida y los consumidores recuperan los mismos tiempos válidos sin transformar
campos, niveles ni grilla.

## D-010 — Flujo actual de animaciones con Met.3D

**Fecha:** 2026-10-19, actualizada 2026-11-06
**Decisión:** Met.3D opera de forma independiente bajo `config/met3d/`, con
escenas, animaciones, sesiones y runtime propios. DANA, jet y friaje usan el motor
común `src/visualize/met3d_animation.py`; sus lanzadores reciben un NetCDF
estandarizado y materializan configuraciones temporales por corrida.

**Impacto:** el runtime se limita a `met3D/.runtime/`; los MP4 históricos se
guardan bajo `outputs/met3d/`. La copia runtime asigna su directorio de
fotogramas a la sesión, por lo que la sesión base no contiene rutas de usuario.
Las cámaras, objetos, intervalos de presión y salida se mantienen en los YAML
de cada animación, sin intervenir en ParaView.

Los productos que declaran `data_preparation` utilizan el preparador genérico
`src/visualize/met3D/netcdf.py` para escribir sus campos y máscaras en un
NetCDF temporal. La creación sigue siendo el comportamiento predeterminado.
El lanzador de friaje admite `--reuse-temporal` para pruebas: valida el origen,
variables, unidades, dimensiones, coordenadas, tiempos, máscaras y registro de
finalización antes de conservar `above_surface.nc` y renovar la escena. Si el
archivo falta o es incompatible, se detiene sin regenerarlo ni limpiar la
escena previa. La reutilización no modifica el contrato del NetCDF
estandarizado ni los datos originales.

La cámara puede permanecer fija o seguir una trayectoria configurable; el
primer tipo disponible es `orbit`, alrededor del centro geográfico de la
escena. Con trayectoria, el número de fotogramas se calcula a partir de los
tiempos disponibles y los mínimos configurados, y un mismo tiempo puede ocupar
varios fotogramas. Un único tiempo válido permite recorrer la trayectoria con
el campo fijo. Sin trayectoria se genera un fotograma por tiempo seleccionado.
El motor actual exige que la coordenada temporal completa esté ordenada y, si
contiene varios tiempos, tenga intervalos regulares; se detiene ante tiempos
ausentes, duplicados, desordenados o cambios de intervalo. Esta última
restricción es una limitación de la implementación de animación, no del
contrato de estandarización. El calendario nativo mixto de IFS descrito en
D-013 es válido; su soporte en apertura/render queda pendiente, sin interpolar
datos ni alterar los plazos del modelo.

## D-011 — Flujo actual de animaciones con ParaView

**Fecha:** 2026-10-19, actualizada 2026-10-28
**Decisión:** ParaView opera de forma independiente bajo `config/paraview/`.
Una escena define geografía, proyección, DEM y estilo; una animación define
capas, variables, intervalos verticales, cámara, línea de tiempo y salida. La
lógica científica se organiza en `src/visualize/paraview/`.

**Impacto:** los temporales se organizan por escena y capa en
`paraview/render_data/`; los fotogramas transitorios de una escena se guardan
en `paraview/render_cache/`; los MP4 históricos se almacenan en
`outputs/paraview/`. La preparación genera un script transitorio junto a su
JSON para abrir la escena en ParaView, sin requerir una variable de entorno ni
una ruta absoluta local. La capa jet construye su geometría desde `hgtprs` y
puede completar únicamente huecos aislados declarados en su YAML, sin alterar
el NetCDF estandarizado.

## D-012 — Ambiente Conda unificado para visualización 3D

**Fecha:** 2026-10-19
**Decisión:** el ambiente Conda de referencia para la visualización 3D se
ejecuta en Linux e incluye Python 3.14, Met.3D, ParaView y FFmpeg junto con las
dependencias de estandarización. No se mantiene compatibilidad con macOS para
este ambiente. La primera comprobación se realiza en `metvis3d-test`; los
ambientes existentes se conservan hasta acordar su reemplazo.

**Impacto:** `environment.yml` declara los canales `conda-forge` y `met3d`,
Met.3D 2.0.0b11, ParaView 6.2.0, PROJ 9.9 y una versión de `cftime` resoluble.
Los lanzadores Met.3D toman `metvis3d` como ambiente predeterminado y aceptan
el nombre de un ambiente de validación mediante `--met3d-environment`.

## D-013 — Selección configurada de corridas GFS e IFS

**Fecha:** 2026-10-19
**Decisión:** el conversor recibe modelo, fecha, ciclo y horizonte de
pronóstico; para GFS e IFS, cada YAML declara el centro, el directorio de la
corrida, la plantilla de archivos y su calendario de plazos. El lanzador
construye los GRIB esperados directamente, sin incorporar índices `.idx` ni
controles `.ctl`.

**Impacto:** GFS usa plazos de 3 h hasta 384 h. IFS usa plazos de 3 h hasta
144 h y de 6 h entre 150 y 240 h. El horizonte solicitado es inclusivo, debe
coincidir con el calendario del modelo y genera un único NetCDF por corrida.

## D-014 — Animación de ingreso frío con DVR de TPE y humedad relativa

**Fecha:** 2026-11-02, actualizada 2026-11-06
**Decisión:** se acepta la composición de friaje con **un único DVR
multivariable de TPE < 320 K y RH > 70 %**, ambos entre 1000 y 700 hPa,
sobre `south_america` con cámara fija. Cada campo conserva su función de
color y opacidad; un actor conjunto evita la advertencia de artefactos de
dos DVR superpuestos. Met.3D deriva TPE mediante Bolton (1980) desde
temperatura y humedad específica; RH se lee directamente de `rhprs` en %.
La cobertura nubosa `tcdcprs` deja de ser requisito del producto.

La configuración aceptada usa `YlGnBu` invertida y opacidad 0.6 para TPE,
y `hot_wind` invertida y opacidad 0.2 para RH. Umbrales, intervalos verticales,
paletas y opacidades se declaran en el YAML. Las desigualdades son estrictas:
TPE igual a 320 K y RH igual a 70 % son transparentes. Una región entera
con TPE inferior al umbral sigue siendo visible aunque no haya un cruce en
su interior. La opacidad acumulada depende también del espesor recorrido.

**Impacto:** el caso de referencia de la revisión actual es GFS del
2026-06-20 00 UTC. La composición visual queda aprobada; la identificación
y validación meteorológica de un evento, y la pertinencia general de los
umbrales, se evalúan por separado. RH alta indica cercanía a saturación y
no se interpreta directamente como nube ni como prueba de desplazamiento
de aire húmedo.

El preparador escribe un único temporal bajo
`met3D/.runtime/<centro>-<modelo>-friaje/`, con temperatura, humedad específica,
RH y presión superficial. Se mantienen coordenadas y niveles nativos,
float32, compresión y tiempo ilimitado; se preservan huecos y se excluyen
las celdas donde `lev * 100 > pressfc` o falta presión superficial. Para el
DVR conjunto se enmascaran también las entradas de TPE fuera de su capa
configurada. El temporal no contiene TPE calculada; su preparación conserva
el NetCDF estandarizado sin alterarlo, interpolar campos ni completar valores.

La variante anterior de isosuperficie de TPE y cobertura nubosa queda como
antecedente, con sus verificaciones históricas en `docs/met3d.md`. El IFS de
junio dispone de las variables del producto actual, pero su calendario mixto
continúa limitado por D-010. La composición aceptada no implica que el render
de todas las corridas y modelos haya sido validado.
