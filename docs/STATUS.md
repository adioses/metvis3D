# Estado del proyecto

Última actualización: 2026-09-15.

## Resumen

La base de desarrollo local está operativa. Se validó la lectura de GRIB2 con
WGRIB2/PyGRIB y una escritura temporal con NetCDF4. Aún no se ha implementado
el conversor operativo ni se han definido los productos audiovisuales finales.

## Avance frente al objetivo contractual

| Objetivo | Estado | Evidencia / pendiente |
|---|---|---|
| A. Preparar y estandarizar datos | En definición | Se acordaron dimensiones y niveles nativos; falta definir variables y diseñar el primer conversor. |
| B. Visualizaciones 3D y animaciones | Pendiente | Herramientas y carpetas preparadas; faltan productos, plantillas y pruebas visuales. |
| C. Plataforma web piloto | En espera | Se definirá después de conocer las restricciones reales del servidor y los productos a publicar. |
| D. Flujo integrado y documentación | En curso inicial | Estructura modular, entorno y documentación de seguimiento creados; faltan automatización y operación integral. |

## Hechos verificados

- Imagen local `metvis3d:dev` construida con Micromamba, Python 3.11,
  WGRIB2 3.8.0, PyGRIB 2.1.8 y NetCDF4 1.7.4.
- Docker Compose monta `../source` en `data/raw` como solo lectura.
- Prueba GRIB → NetCDF4: temperatura GFS a 500 hPa, matriz 401×553, unidades
  Kelvin. El archivo de prueba fue temporal, fuera del proyecto.
- GFS regional (`GFS27/COM`): 553×401, 0.25°, 26 niveles de presión, 129
  archivos completos de 0 a 384 h.
- ECMWF global: 1440×721, 0.25°, 13 niveles de presión. ECMWF/SUD: 761×401,
  0.25°, 13 niveles. Sus CTL corresponden a dichas mallas.
- ECMWF global y SUD comparten plazos faltantes entre 147 y 237 h cada 3 h;
  corresponden a una descarga incompleta conocida.

## Riesgos y decisiones abiertas

- El cliente todavía no define los productos meteorológicos ni sus criterios
  de aceptación visual.
- La capacidad exacta del HPC, disponibilidad de FFmpeg y posibilidad de
  ejecutar ParaView/Blender por lote deben verificarse antes de diseñar el
  procesamiento masivo.
- Debe definirse el tratamiento de tiempos y archivos faltantes durante el
  diseño del conversor.
- La plataforma web queda en espera para no depender prematuramente de Node,
  una base de datos o servicios no disponibles.

## Siguiente actividad propuesta

Definir las variables y el primer producto piloto. Con ello se podrá diseñar el
conversor inicial y acordar las comprobaciones que correspondan a ese flujo.
