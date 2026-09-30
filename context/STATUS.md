# Estado del proyecto

**Última actualización:** 2026-09-29

## Resumen

El proyecto se encuentra principalmente en el cierre del ítem a) de la sección
6 de los Términos de Referencia: preparación, transformación y
estandarización de información meteorológica. La clase `Grib2ToNetCDF` está
implementada y sus fases técnicas fueron verificadas con GFS y ECMWF. El paso
pendiente para cerrar este ítem es la verificación científica de los NetCDF
generados frente a los GRIB2 de origen.

## Estado frente al alcance contractual

| Ítem | Estado | Situación actual |
|---|---|---|
| a) Preparación, transformación y estandarización | En cierre | Conversor, configuraciones, reportes y benchmarks implementados; falta validación científica documentada. |
| b) Visualizaciones y animaciones | Pendiente | Se abordará después de cerrar la estandarización y definir los productos piloto. |
| c) Plataforma web piloto | En espera | Depende de los productos que se generen y de las condiciones del servidor final. |
| d) Integración, operación y documentación | Inicial | Existen el entorno de desarrollo y la organización del proyecto; la integración completa depende de los ítems anteriores. |

## Implementado y verificado para el ítem a)

- `Grib2ToNetCDF` en `src/standardize/grib2_to_netcdf.py` genera un NetCDF
  único por corrida desde una colección homogénea de GRIB2.
- WGRIB2 construye el inventario completo de mensajes; PyGRIB prepara la
  grilla y lee las matrices; NetCDF4 crea la estructura y escribe los campos.
- El conversor valida hora de referencia, dominio y tamaño de grilla comunes;
  organiza tiempos válidos, niveles isobáricos nativos y variables de
  superficie o presión.
- Se implementaron remapeos de parámetros locales, selección por nombre final,
  atributos de procedencia, normalización de longitudes y recorte sin
  interpolación.
- `scripts/report_grib2_inventory.py` genera reportes de inventario y
  remapeos. `scripts/benchmark_gfs_grib2_to_netcdf.py` registra tiempos de
  inventario y conversión por archivo.
- Las corridas completas documentadas el 2026-09-23 produjeron:
  - GFS: 129 GRIB, NetCDF seleccionado de 3.60 GiB en 29.68 min.
  - ECMWF: 65 GRIB, nueve variables seleccionadas, NetCDF de 654 MiB en
    5.51 min.

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
