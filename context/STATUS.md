# Estado del proyecto

**Última actualización:** 2026-11-06

## Resumen

El proyecto se encuentra en el cierre del ítem a) de la sección 6 de los
Términos de Referencia. El conversor `Grib2ToNetCDF` está implementado y
verificado estructuralmente. Los flujos de visualización se validaron
técnicamente en un único ambiente Conda Linux con Met.3D y ParaView. La
composición de friaje con DVR multivariable de TPE y humedad relativa fue
aceptada por el usuario el 2026-11-06. Continúan pendientes la validación
meteorológica del evento, las otras composiciones y el soporte del calendario
mixto de IFS para apertura/render en Met.3D.

## Estado frente al alcance contractual

| Ítem | Estado | Situación actual |
|---|---|---|
| a) Preparación, transformación y estandarización | En cierre | Conversor, configuraciones, reportes y benchmarks implementados; falta validación científica documentada. |
| b) Visualizaciones y animaciones | Implementado técnicamente | Composición de friaje TPE/RH aprobada visualmente; siguen pendientes la validación meteorológica, las otras composiciones y el calendario mixto de IFS en Met.3D. |
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
- La precisión NetCDF admite excepciones por variable en
  `standardization.least_significant_digit`: enteros no negativos o `full`,
  con valor 2 por defecto. GFS, IFS, ETA y WRF declaran `spfhprs: full`,
  conservando `float32`, compresión y unidades `kg/kg`. Se verificaron
  manualmente el lanzador operativo y el benchmark con tres GRIB GFS de
  2026-08-16, en los casos `full`, precisión numérica y configuración sin
  excepciones: 702 matrices contrastadas con el origen. El procedimiento y
  los resultados están en `docs/grib2-guia-practica.md`, sección 12.1.

## Pendiente para cerrar el ítem a)

- Definir y ejecutar casos de verificación científica para las variables
  seleccionadas de GFS e IFS.
- Comparar cada caso con su GRIB2 de origen: variable y unidades, tiempo
  válido, nivel, orientación espacial, área recortada, valores y remapeos.
- Documentar las tolerancias de cada variable según su precisión efectiva y
  confirmar el significado y unidades de los parámetros locales remapeados.
- Regenerar desde los GRIB originales los NetCDF existentes que usaban
  `least_significant_digit=2` para humedad específica; la nueva configuración
  no recupera el detalle perdido en esos archivos.
- Resolver o aceptar explícitamente las variables solicitadas que no estén
  disponibles en una corrida, como las advertencias actuales de `prmslmsl` en
  la selección ECMWF.

## Flujos vigentes de visualización

- Met.3D utiliza exclusivamente `config/met3d/scenes/`,
  `config/met3d/animations/`, `src/visualize/met3d_animation.py`, el preparador
  de datos `src/visualize/met3D/netcdf.py` y los
  lanzadores `scripts/run_met3d_dana.py`, `scripts/run_met3d_jet.py` y
  `scripts/run_met3d_friaje.py`. Los productos preparan configuraciones
  temporales y guardan sus MP4 históricos en
  `outputs/met3d/`.
- Los lanzadores Met.3D exponen `--open` para revisar la escena en una estación
  gráfica y `--render` para el batch. Por defecto, ambas acciones reconstruyen
  el runtime; friaje admite `--reuse-temporal` para validar y conservar su
  NetCDF mientras renueva la escena. El batch usa Xvfb con su contexto OpenGL
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
- La preparación ParaView conserva únicamente los temporales vigentes por
  escena y capa. Genera en `paraview/render_cache/<escena>/` un script de
  apertura asociado a su JSON, de modo que la revisión interactiva no requiere
  declarar una variable de entorno ni una ruta absoluta local.
- La sesión base de Met.3D no contiene rutas de usuario; cada runtime dirige
  sus imágenes al directorio temporal que corresponde a la ejecución actual.
- El ambiente `metvis3d-test`, creado desde `environment.yml`, reúne Python
  3.14, Met.3D 2.0.0b11, ParaView 6.2.0, FFmpeg y las dependencias de
  estandarización. Importó los módulos científicos y del proyecto sin errores.
- Con ese ambiente se generaron los batch de DANA y jet de Met.3D, y jet de
  ParaView, para `ncep-gfs_20260816_00Z.nc`. Los tres MP4 tienen 81
  fotogramas H.264 de 1920×1080 y 8.1 s. Met.3D obtuvo OpenGL 4.6; ParaView
  aplicó la política YAML para diez huecos aislados de `hgtprs` a 250 hPa.
- DANA incorpora una sección horizontal configurable con PV, barbas de viento
  y geopotencial opcional. Se comprobó en Met.3D 2.0.0b11 el render de los
  primeros plazos de GFS del 2026-08-16 y la selección de 400 hPa cuando se
  solicitan 375 hPa, equidistantes entre 350 y 400 hPa. Queda pendiente la
  revisión meteorológica y visual de la composición para el evento completo.
- Met.3D admite una trayectoria de cámara configurable de tipo `orbit`,
  sincronizada con los tiempos del NetCDF, y carga la secuencia en `--open`.
  Se comprobaron renders de órbita y cámara fija con uno y tres tiempos;
  también se comprobaron intervalos regulares de 1, 3 y 6 h y el rechazo de
  tiempos duplicados, desordenados o irregulares. La cámara fija conserva un
  fotograma por tiempo; la trayectoria admite varios y un solo tiempo válido.
- Se exploraron videos de DANA con PV coloreada por presión y con renderizado
  directo de volumen de PV, junto con una referencia de cámara fija. Estas
  variantes se generaron con configuraciones temporales y aún no forman parte
  del flujo operativo; su composición requiere evaluación meteorológica y
  visual. Los videos no muestran todavía el tiempo válido como etiqueta.
- La composición vigente de friaje, aceptada el 2026-11-06, utiliza un único
  DVR multivariable de TPE < 320 K y RH > 70 %, ambos entre 1000 y 700 hPa,
  sobre `south_america` con cámara fija. La TPE se deriva con Bolton (1980)
  dentro de Met.3D; RH proviene de `rhprs`. Se conservan funciones de color y
  opacidad separadas: TPE con `YlGnBu` invertida y 0.6; RH con `hot_wind`
  invertida y 0.2. Se retira `tcdcprs` como requisito. La referencia de esta
  revisión es GFS del 2026-06-20 00 UTC; la aprobación visual no confirma
  un friaje observado ni convierte los umbrales en criterios universales.
- El preparador genérico de visualización declara las dimensiones nativas y
  utiliza NetCDF4, float32, compresión y tiempo ilimitado para escribir por
  plazo. Conserva un único `above_surface.nc` con temperatura, humedad
  específica, RH y presión superficial. Respeta huecos y máscaras bajo
  superficie; en el DVR conjunto limita las entradas de TPE a su capa
  declarada. El NetCDF estandarizado permanece intacto y TPE no se escribe
  como campo derivado en el temporal. `--reuse-temporal` valida procedencia,
  variables, coordenadas, tiempos, máscaras y finalización sin recorrer todos
  los volúmenes. Si es incompatible o falta, se detiene sin regenerar ni
  limpiar la escena anterior. Los temporales antiguos requieren generarse
  una vez sin la bandera. La creación sigue siendo la opción predeterminada.
- Durante el desarrollo del 2026-11-05 se verificaron fotogramas de GFS del
  2026-06-25 12 UTC y casos sintéticos: desigualdades estrictas en ambos
  umbrales, campos visibles juntos y por separado en un DVR, conservación de
  niveles y valores válidos, máscaras superficiales y verticales, y RH en
  niveles superiores a 700 hPa en la variante de columna completa. Se
  comprobó reutilización sin modificar el temporal, rechazo de preparaciones
  incompatibles y regeneración predeterminada; un render de RH en grises
  conservó la opacidad 0.2 y la capa 1000–700 hPa. DANA y jet mantuvieron su
  preparación. Los casos y el procedimiento están en `docs/met3d.md`; queda
  conservar evidencia del video completo con la configuración final elegida.
- La versión anterior de friaje usaba isosuperficie de TPE y DVR de nubosidad.
  Su corrida GFS del 2026-10-14 produjo un MP4 H.264 de 1920×1080, 41
  fotogramas a 6 fps y 6.833333 s, con verificación exacta de 123 volúmenes,
  coordenadas y SHA-256 del origen. Es un antecedente técnico y no acredita
  el nuevo producto TPE/RH. En un caso sintético con huecos de `pressfc` se
  observó un artefacto de la topografía nativa; las máscaras atmosféricas sí
  fueron correctas. Esta limitación sigue pendiente para archivos con esos
  huecos; la corrida utilizada para el video histórico no los tiene.
- Se generó la revisión 2D de friaje con Cartopy, costas y límites nacionales
  locales de Natural Earth: TPE < 320 K en azul, viento y máscaras diferenciadas
  en 925, 850 y 700 hPa, conservando el dominio `south_america`. La corrida GFS
  de 2026-10-14 produjo 41 láminas PNG, PDF de 41 páginas y 123 filas de
  estadística bajo `outputs/analysis/friaje-tpe/`. El cálculo reprodujo la
  rutina C++ de Met.3D en 28 904 puntos, con diferencia máxima de 0 K en
  float32 y sin diferencias de clasificación. Pasaron los casos manuales de
  máscaras, ausencia de cruces y nivel/plazo ausente; el NetCDF original
  conserva su SHA-256. Uso y verificaciones en `docs/friaje-tpe-2d.md`.
  La siguiente actividad es revisar la evolución horizontal del umbral con el
  usuario antes de ajustar la interpretación de la animación 3D.
- Se implementó el diagnóstico de T2m con diferencias exactas a 24 h, mapas
  regionales, máximos por celda y series próximas a Puerto Maldonado, Pucallpa
  e Iquitos. La corrida GFS de 2026-10-14 produjo 41 mapas y un PDF de
  43 páginas, con 33 ventanas de comparación. Se verificaron directamente
  los máximos de 19 881 celdas y el SHA-256 del origen; pasaron los casos
  manuales de calentamiento, ausencias, empates y tiempos incompatibles.
  Los mayores descensos de las referencias son 12.80, 10.43 y 12.05 °C,
  respectivamente, principalmente diurnos. La comparación complementaria
  mostró TPE superior a 320 K en las tres referencias a 925/850/700 hPa
  durante todos los tiempos: la falta de esa isosuperficie no implica ausencia
  de enfriamiento superficial. Los resultados son de modelo y no confirman
  por sí solos un friaje observado. Procedimiento y análisis en
  `docs/friaje-temperatura-2m.md`; productos en `outputs/analysis/friaje-tmp2m/`.
  Queda revisar la coherencia del ingreso frío y la pertinencia del umbral
  con el usuario antes de cambiar la corrida o la animación.
- Se repitió el diagnóstico T2m con IFS de 2026-06-20: 65 mapas, 57 ventanas
  exactas a 24 h y PDF de 69 páginas. Se incorporó un complemento nocturno
  configurable a la 01:00 de Perú (06 UTC), común a los calendarios de 3/6 h:
  diez muestras, nueve pares y dos láminas adicionales. Se verificaron
  directamente máximos y fechas de 19 881 celdas en ambos diagnósticos,
  mínimos nocturnos, 30 registros de referencia y SHA-256 intacto del origen.
  Puerto Maldonado baja de 21.92 a 18.17 °C a la 01:00 entre el 23 y el 25;
  Pucallpa e Iquitos muestran descensos menores y graduales. No se equiparan
  esas muestras con mínimas diarias ni se ha validado el archivo como evento
  definitivo de friaje. En las tres referencias no hay TPE < 320 K a
  925/850/700 hPa; Puerto Maldonado alcanza 320.41 K a 925 hPa. Resultados y
  reproducción en `docs/friaje-temperatura-2m.md`; queda revisar los mapas
  nocturnos con el usuario antes de seleccionar el evento para la animación.
- Se generó el análisis TPE 2D para la misma corrida IFS de 2026-06-20,
  conservando `south_america`, los niveles 925/850/700 hPa y TPE < 320 K:
  65 PNG, PDF de 65 páginas y 195 filas de estadística. La relectura del
  NetCDF confirmó exactamente conteos, máscaras y extremos de los 195 planos,
  y el origen conserva su SHA-256. No hay cruces del umbral en las tres
  referencias amazónicas a esos niveles; Puerto Maldonado alcanza 320.41 K
  a 925 hPa el 25/06 a las 12 UTC. Esto no invalida el enfriamiento nocturno
  de T2m ni permite clasificar por sí solo el evento. Resultados y ejecución
  en `docs/friaje-tpe-2d.md`, productos en
  `outputs/analysis/friaje-tpe/ecmwf-ifs/20260620_00Z/`. Queda revisar la
  señal del umbral con el usuario antes de ajustar la animación.
- Se aplicó el mismo análisis TPE a GFS de 2026-06-20: 81 PNG, PDF de
  81 páginas, 243 planos y 729 muestras complementarias de referencia.
  Se verificaron exactamente estadísticas y máscaras frente a una relectura
  del NetCDF, y el SHA-256 del origen permanece intacto. Puerto Maldonado
  cruza 320 K a 925 hPa el 26/06 a las 12 y 15 UTC (319.80 y 319.00 K);
  no hay cruces en las otras ocho series de referencia. Restringiendo GFS
  a las 65 horas comunes con IFS, se conserva el cruce de las 12 UTC,
  mientras IFS permanece sobre el umbral. Resultados en
  `docs/friaje-tpe-2d.md` y `outputs/analysis/friaje-tpe/ncep-gfs/20260620_00Z/`.
  Queda revisar esta señal localizada antes de elegir el evento o ajustar
  la animación; esta ejecución corresponde únicamente al diagnóstico TPE.
- La revisión temporal de IFS del 2026-06-20 confirmó 65 tiempos ordenados y
  sin duplicados, exactamente iguales a `config/models/ifs.yaml`: F+0 a
  F+144 cada 3 h y F+150 a F+240 cada 6 h. El NetCDF contiene las variables
  del nuevo producto; la ausencia de `tcdcprs` ya no es un impedimento.
  `build_timeline` sigue rechazando el cambio de paso entre 2026-06-26 00 y
  06 UTC. Es una limitación del motor de animación, no un defecto del
  calendario estandarizado; también afecta a `--open` y a selecciones
  parciales porque se valida primero la coordenada completa.
- Se actualizaron `docs/met3d.md` y las decisiones D-010/D-014 para reflejar
  el producto aceptado y `--reuse-temporal`. El documento
  `docs/friaje-flujo-calculo-y-visualizacion.md` conserva la descripción
  anterior de isosuperficie/nubosidad y su ciclo de vida del temporal; su
  actualización queda pendiente. Para operar el producto vigente se utiliza
  la guía `docs/met3d.md`.

## Pendientes y siguiente actividad

- Acordar y resolver el recorrido de tiempos nativos con intervalos mixtos de
  IFS en Met.3D, conservando la grilla y sin interpolación temporal.
- Conservar el video completo y su configuración, corrida, tiempos y
  comprobaciones como evidencia reproducible de la composición aceptada.
- Continuar la validación meteorológica del caso mediante TPE, RH, T2m y
  circulación; la aprobación visual no cierra esa evaluación ni todo el
  hito contractual b).
- Actualizar el documento consolidado del flujo cuando se autorice ese
  alcance; mantener disponibles los análisis 2D y antecedentes históricos.
