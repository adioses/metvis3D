# Estado del proyecto

**Última actualización:** 2026-10-28

## Resumen

El proyecto se encuentra en el cierre del ítem a) de la sección 6 de los
Términos de Referencia. El conversor `Grib2ToNetCDF` está implementado y
verificado estructuralmente. Los flujos de visualización se validaron
técnicamente en un único ambiente Conda Linux con Met.3D y ParaView; la
siguiente etapa es su validación meteorológica y visual.

## Estado frente al alcance contractual

| Ítem | Estado | Situación actual |
|---|---|---|
| a) Preparación, transformación y estandarización | En cierre | Conversor, configuraciones, reportes y benchmarks implementados; falta validación científica documentada. |
| b) Visualizaciones y animaciones | Implementado técnicamente | Met.3D y ParaView generan animaciones configurables; falta validación meteorológica y de composición visual. |
| c) Plataforma web piloto | En espera | Depende de los productos que se generen y de las condiciones del servidor final. |
| d) Integración, operación y documentación | En desarrollo | Existen flujos reproducibles para conversión y visualización; falta integrar y documentar la operación completa. |

## Implementado y verificado para el ítem a)

- `Grib2ToNetCDF` genera un NetCDF único por corrida desde una colección
  homogénea de al menos tres GRIB2 con variación temporal.
- WGRIB2 consulta el primer mensaje de cada archivo para validar hora de
  referencia, dominio, tamaño y plantilla de grilla. El primer, segundo y
  último archivo definen las variables y los niveles; durante la escritura,
  WGRIB2 vuelve a inventariar cada archivo y asocia sus mensajes con PyGRIB
  mediante el número explícito de mensaje.
- El conversor organiza los tiempos válidos, los niveles isobáricos nativos y
  las variables de superficie o presión; PyGRIB prepara la grilla y NetCDF4
  crea y escribe el producto final.
- Se implementaron remapeos de parámetros locales, selección por nombre final,
  atributos de procedencia, normalización de longitudes y recorte sin
  interpolación.
- El conversor declara el contrato CF-1.10 de las coordenadas: nombres
  estándar, presión isobárica con dirección `down` y tiempo referido a la hora
  de inicialización de la corrida.
- El lanzador de conversión resuelve las corridas configuradas de GFS e IFS a
  partir de modelo, fecha, ciclo y horizonte. Construye únicamente los nombres
  GRIB previstos por cada calendario, por lo que excluye índices y controles y
  detiene la ejecución ante un plazo ausente.
- `scripts/report_grib2_inventory.py` genera reportes de las variables,
  superficies y remapeos presentes. `scripts/benchmark_grib2_to_netcdf.py`
  registra las etapas de validación, preparación de variables y escritura por
  archivo.

## Pendiente para cerrar el ítem a)

- Definir y ejecutar casos de verificación científica para las variables
  seleccionadas de GFS e IFS.
- Comparar cada caso con su GRIB2 de origen: variable y unidades, tiempo
  válido, nivel, orientación espacial, área recortada, valores y remapeos.
- Documentar las tolerancias asociadas a `least_significant_digit=2` y
  confirmar el significado y unidades de los parámetros locales remapeados.
- Resolver o aceptar explícitamente las variables solicitadas que no estén
  disponibles en una corrida, como las advertencias actuales de `prmslmsl` en
  la selección ECMWF.

## Flujos vigentes de visualización

- Met.3D utiliza exclusivamente `config/met3d/scenes/`,
  `config/met3d/animations/`, `src/visualize/met3d_animation.py` y los
  lanzadores `scripts/run_met3d_dana.py` y `scripts/run_met3d_jet.py`. DANA y
  jet preparan un runtime temporal propio y guardan sus MP4 históricos en
  `outputs/met3d/`.
- Los lanzadores Met.3D exponen `--open` para revisar la escena en una estación
  gráfica y `--render` para el batch. Ambas acciones reconstruyen el runtime
  de la corrida; el batch se configuró bajo Xvfb con su contexto OpenGL
  virtual, mientras que la cámara se aplica desde el YAML directamente a la
  copia de sesión. Se eliminó el `camera.conf` que no era consumido por Met.3D
  y se unificó la sesión base de DANA y jet como `south_america_base`.
- ParaView utiliza exclusivamente `config/paraview/scenes/`,
  `config/paraview/animations/`, `src/visualize/paraview/` y
  `scripts/run_paraview_animation.py`. Sus datos temporales se organizan por
  escena y capa en `paraview/render_data/`; los fotogramas de la última
  ejecución de una escena se almacenan en `paraview/render_cache/`.
- La animación ParaView de jet usa `ugrdprs`, `vgrdprs` y `hgtprs` entre 500 y
  50 hPa. La carga interactiva y el render batch se verificaron manualmente
  con la corrida GFS de 2026-08-16.
- La preparación ParaView materializa un PVD con todos los VTS temporales. La
  plantilla interactiva y el batch consumen esa misma colección, por lo que la
  revisión gráfica expone todos los plazos y el render no reemplaza VTS
  manualmente. Se comprobó con EGL la carga y el render de los plazos inicial
  y final de una colección de 41 tiempos.
- El ambiente `metvis3d-test`, creado desde `environment.yml`, reúne Python
  3.14, Met.3D 2.0.0b11, ParaView 6.2.0, FFmpeg y las dependencias de
  estandarización. Importó los módulos científicos y del proyecto sin errores.
- Con ese ambiente se generaron los batch de DANA y jet de Met.3D, y jet de
  ParaView, para `ncep-gfs_20260816_00Z.nc`. Los tres MP4 tienen 81
  fotogramas H.264 de 1920×1080 y 8.1 s. Met.3D obtuvo OpenGL 4.6; ParaView
  aplicó la política YAML para diez huecos aislados de `hgtprs` a 250 hPa.

## Siguiente actividad

Revisar meteorológicamente los videos generados, ajustar desde YAML los
umbrales, intervalos verticales, cámaras y estilo cuando corresponda, acordar
el protocolo de validación científica para GFS y ECMWF, y decidir la promoción
de `metvis3d-test` al ambiente operativo `metvis3d`.
