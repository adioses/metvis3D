# Estado del proyecto

**Última actualización:** 2026-10-08

## Resumen

El proyecto se encuentra principalmente en el cierre del ítem a) de la sección
6 de los Términos de Referencia: preparación, transformación y
estandarización de información meteorológica. El refactor de
`Grib2ToNetCDF` está terminado y verificado.

## Estado frente al alcance contractual

| Ítem | Estado | Situación actual |
|---|---|---|
| a) Preparación, transformación y estandarización | En cierre | Conversor, configuraciones, reportes y benchmarks implementados; falta validación científica documentada. |
| b) Visualizaciones y animaciones | En exploración | Se preparó una primera escena estática de topografía para Sudamérica; falta validarla visualmente e integrar campos atmosféricos VTS. |
| c) Plataforma web piloto | En espera | Depende de los productos que se generen y de las condiciones del servidor final. |
| d) Integración, operación y documentación | Inicial | Existen el entorno de desarrollo y la organización del proyecto; la integración completa depende de los ítems anteriores. |

## Implementado y verificado para el ítem a)

- `Grib2ToNetCDF` genera un NetCDF único por corrida desde una colección
  homogénea de al menos tres GRIB2 con variación temporal.
- WGRIB2 consulta el primer mensaje de cada archivo para validar hora de
  referencia, dominio, tamaño y plantilla de grilla. El primer, segundo y
  último archivo definen las variables y los niveles; durante la escritura,
  WGRIB2 vuelve a inventariar cada archivo y asocia sus mensajes con PyGRIB
  mediante el número explícito de mensaje.
- El conversor organiza los tiempos válidos, los niveles isobáricos nativos y
  las variables de superficie o presión; PyGRIB prepara la grilla y lee las
  matrices, mientras NetCDF4 crea y escribe el producto final.
- Se implementaron remapeos de parámetros locales, selección por nombre final,
  atributos de procedencia, normalización de longitudes y recorte sin
  interpolación.
- `scripts/report_grib2_inventory.py` genera reportes de las variables,
  superficies y remapeos presentes. `scripts/benchmark_grib2_to_netcdf.py`
  registra las etapas de validación, preparación de variables y escritura por
  archivo.
- Los tiempos de benchmarks anteriores se conservan como evidencia histórica,
  pero no representan el flujo de inventario por etapas del refactor.

## Pendiente para cerrar el ítem a)

- Definir y ejecutar casos de verificación científica para las variables
  seleccionadas de GFS y ECMWF.
- Comparar cada caso con su GRIB2 de origen: variable y unidades, tiempo
  válido, nivel, orientación espacial, área recortada, valores y remapeos.
- Documentar las tolerancias asociadas a `least_significant_digit=2` y
  confirmar el significado y unidades de los parámetros locales remapeados.
- Resolver o aceptar explícitamente las variables solicitadas que no estén
  disponibles en una corrida, como las advertencias actuales de `prmslmsl` en
  la selección ECMWF.

## Exploración iniciada para el ítem b)

- Se definió una escena estática inicial para Sudamérica con el GeoTIFF global
  GMTED2010 `mn30`, proyección Lambert Conformal Conic, malla de 10 km,
  océano plano y exageración vertical de 12 veces.
- `scripts/prepare_static_scene.py` prepara el DEM proyectado y una malla VTS
  estática; `paraview/templates/render_static_terrain.py` la abre y colorea
  dentro de ParaView.
- La primera malla generada tiene 1 670 × 1 110 puntos y se conserva como
  producto descartable en `paraview/render_data/static/south_america/`.
- Se generó una primera prueba de chorro para el análisis GFS de 2026-09-03
  00Z: isosuperficie única de 30 m/s entre 500 y 50 hPa, con 241 × 175 × 11
  puntos y la misma Lambert/exageración vertical de la topografía. La plantilla
  combinada fue validada mediante ParaView; queda pendiente ajustar su lectura
  visual antes de convertirla en una plantilla de animación.

## Siguiente actividad

Validar visualmente la escena estática en ParaView y, en paralelo, acordar el
protocolo de verificación científica para GFS y ECMWF. La escena validada será
el contexto común para la primera plantilla atmosférica VTS.
