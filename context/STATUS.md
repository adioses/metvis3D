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
| b) Visualizaciones y animaciones | Pendiente | Se abordará después de cerrar la estandarización y definir los productos piloto. |
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

## Siguiente actividad

Acordar el protocolo de verificación científica y aplicar primero casos
representativos de GFS y ECMWF. Con los resultados documentados se podrá
declarar cerrado el ítem a) e iniciar la definición del primer producto de
visualización.
