# Registro de decisiones técnicas

Este archivo es acumulativo. Registrar decisiones que cambien la arquitectura,
el contrato de datos, el alcance o la forma de operación. No usarlo como diario
de actividades; el estado diario pertenece a `STATUS.md`.

## Formato

Cada decisión incluye fecha, contexto, decisión, motivo e impacto. No se
reescriben decisiones históricas: si cambia una, agregar una nueva entrada que
la sustituya o matice.

## D-001 — Estructura de datos canónica

**Fecha:** 2026-09-15  
**Decisión:** usar `time`, `pressure`, `latitude` y `longitude` como nombres de
dimensión. Campos de superficie: `(time, latitude, longitude)`; campos en
presión: `(time, pressure, latitude, longitude)`.

**Motivo:** permite una interfaz homogénea para ECMWF, GFS y futuros modelos
sin ocultar las diferencias físicas de cada fuente.

**Impacto:** todos los adaptadores deben mapear sus coordenadas y metadatos a
este contrato.

## D-002 — Niveles verticales nativos

**Fecha:** 2026-09-15  
**Decisión:** conservar los niveles de presión nativos de cada modelo.

**Motivo:** evita pérdida de detalle en modelos con más niveles y evita una
interpolación no solicitada.

**Impacto:** GFS y ECMWF pueden tener tamaños distintos en `pressure`; las
plantillas de visualización deben soportarlo.

## D-003 — Un NetCDF final por modelo y corrida

**Fecha:** 2026-09-15  
**Decisión:** consolidar superficie y campos en presión seleccionados en un
único NetCDF final. No crear NetCDF parciales por variable o tiempo.

**Motivo:** simplifica la organización y el consumo por Jupyter, ParaView,
Blender y la futura publicación.

**Impacto:** la estrategia de escritura, publicación y comprobaciones se
definirá al implementar el conversor.

## D-004 — Entorno local y de producción

**Fecha:** 2026-09-15  
**Decisión:** desarrollo local con Docker Compose y Micromamba; operación en
HPC con Miniconda/Conda y el mismo `environment.yml`.

**Motivo:** aislar el Mac de desarrollo y respetar que el servidor final no
dispone de Docker.

**Impacto:** no usar dependencias exclusivas de contenedor en el código
operativo.

## D-005 — Visualización y configuración

**Fecha:** 2026-09-15  
**Decisión:** Jupyter se utilizará para exploración y ajuste; las plantillas de
ParaView/Blender y sus parámetros se conservarán como scripts/configuraciones
reproducibles.

**Motivo:** permite al especialista meteorológico ajustar productos sin que la
lógica de producción quede encerrada en un notebook.

**Impacto:** el grado de automatización de cada plantilla se definirá cuando se
seleccionen los productos audiovisuales.

