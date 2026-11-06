# Guía de animaciones con Met.3D

Met.3D mantiene un flujo independiente para explorar y generar videos
meteorológicos desde un NetCDF estandarizado. Cada animación declara su escena,
variables, objetos, cámara, línea de tiempo y salida bajo
`config/met3d/animations/`; las configuraciones temporales se generan en
`met3D/.runtime/` y no se versionan. La copia runtime asigna su directorio de
fotogramas a la sesión, por lo que la sesión base no contiene rutas de usuario.

## Animaciones disponibles

| Animación | Configuración | Estructura meteorológica |
|---|---|---|
| DANA | `config/met3d/animations/south_america_dana.yaml` | Isosuperficie de PV baroclínica de -5 PVU entre 500 y 250 hPa y sección horizontal de PV, viento y altura geopotencial; `pressfc` proporciona topografía de presión. |
| Jet | `config/met3d/animations/south_america_jet.yaml` | Isosuperficie de rapidez derivada de `ugrdprs` y `vgrdprs`, entre 500 y 100 hPa, con umbral inicial de 50 m s-1. |
| Friaje | `config/met3d/animations/south_america_friaje.yaml` | DVR multivariable de TPE < 320 K y humedad relativa > 70 %, ambos entre 1000 y 700 hPa, con topografía de presión. |

Las animaciones usan exclusivamente la escena de Met.3D
`config/met3d/scenes/south_america.yaml`. La escena define el dominio
horizontal y el contexto vertical; cada objeto declara el intervalo de presión
que necesita.

## Requisitos

- Un NetCDF estandarizado de una corrida completa.
- Un ambiente Conda Linux creado desde `environment.yml`, con el binario
  `Met3D` instalado. El ambiente operativo se denomina `metvis3d`.
- La sesión base `met3D/sessions/south_america_base.session.config`.
- Para el render batch sin interfaz gráfica, `xvfb-run`. Met.3D requiere un
  contexto OpenGL funcional y no tiene un modo alternativo de render solo con
  CPU.

Los comandos siguientes se ejecutan desde la raíz del proyecto.

## DANA

Abrir la escena en una estación de trabajo con interfaz gráfica para revisar
los objetos y ajustar la cámara:

```bash
conda run -n metvis3d python scripts/run_met3d_dana.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --open
```

Renderizar todos los plazos y codificar el MP4, incluso por SSH, cron u otro
servicio sin interfaz gráfica:

```bash
conda run -n metvis3d python scripts/run_met3d_dana.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --render
```

El video se conserva bajo `outputs/met3d/dana/<centro>-<modelo>/`.
`objects.potential_vorticity.opacity` controla la opacidad de la isosuperficie
3D: 0 es transparente y 1 es opaca; inicialmente se usa 0.65. Este parámetro
no altera los colores de la sección horizontal.

### Sección horizontal de DANA

`objects.horizontal_section` configura una sección en un nivel de presión
común para PV baroclínica, viento y altura geopotencial. `pressure_hpa` solicita
350 hPa inicialmente. Si ese nivel no existe, se utiliza el nivel nativo más
próximo; en caso de empate se elige el de mayor presión. El lanzador informa el
nivel solicitado y el utilizado, que también aparece en el nombre y etiqueta
del actor. No se interpola para seleccionar el nivel.

La PV se muestra con contornos rellenos violetas de -10 a -2 PVU; por encima de
-2 PVU es transparente y por debajo de -10 PVU se extiende el color más intenso.
Los límites y el estilo están en `potential_vorticity`. El viento se representa
con barbas individuales: `wind.spacing_degrees` regula su separación,
`min_length_degrees` y `max_length_degrees` su tamaño, y `line_width` su grosor.
Met.3D convierte las componentes del viento de m/s a nudos para las barbas.
`geopotential_height.enabled`
activa los contornos de `hgtprs`, cuyo intervalo inicial es 120 gpm. Si se
activa, la variable debe existir y declarar unidades `gpm`.

El proceso detiene la ejecución si una variable requerida no existe o no tiene
datos en el nivel efectivo para un plazo seleccionado. La sección describe la
PV en ese plano; no define por sí sola toda la extensión vertical de la DANA.
Las barbas y el color deben revisarse meteorológicamente junto con
la isosuperficie y los contornos de geopotencial.

Ambas acciones preparan el runtime transitorio antes de iniciar Met.3D. No hay
una acción pública de preparación aislada: el runtime debe corresponder al
NetCDF y a la configuración de la ejecución actual.

## Jet

Abrir el jet para su revisión visual:

```bash
conda run -n metvis3d python scripts/run_met3d_jet.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --open
```

Renderizarlo en batch:

```bash
conda run -n metvis3d python scripts/run_met3d_jet.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --render
```

El video se conserva bajo `outputs/met3d/jet/<centro>-<modelo>/`.

Durante `--render`, el lanzador crea automáticamente la pantalla virtual con:

```bash
xvfb-run -a --server-args="-screen 0 1920x1080x24 +extension GLX +render -noreset"
```

La pantalla virtual sólo se usa para el render batch. `--open` conserva la
interfaz nativa y debe ejecutarse en una máquina gráfica.

Para validar un ambiente con otro nombre, conserve el ambiente que ejecuta
Python y especifique el mismo nombre para Met.3D. Por ejemplo, para
`metvis3d-test` agregue `--met3d-environment metvis3d-test` a cada comando.

## Friaje

Abrir la animación con una corrida que contenga `tmpprs` en K, `spfhprs` en
kg/kg, `rhprs` en % y `pressfc` en Pa:

```bash
conda run -n metvis3d python scripts/run_met3d_friaje.py \
  --netcdf data/standardized/ncep-gfs_20260620_00Z.nc \
  --open
```

Generar el video con todos los tiempos disponibles:

```bash
conda run -n metvis3d python scripts/run_met3d_friaje.py \
  --netcdf data/standardized/ncep-gfs_20260620_00Z.nc \
  --render
```

La composición de TPE y humedad relativa fue aceptada por el usuario el
2026-11-06. La corrida de referencia de esta revisión es GFS del
2026-06-20 00 UTC; el producto admite otras corridas compatibles y no detecta
automáticamente un evento. El MP4 se conserva en
`outputs/met3d/friaje/<centro>-<modelo>/`. La aprobación visual no constituye
una validación meteorológica del evento ni de los umbrales como criterios
universales de friaje.

### Temperatura potencial equivalente y humedad relativa

Met.3D deriva `equivalent_potential_temperature` con Bolton (1980) desde
temperatura, humedad específica y presión de los niveles nativos. Python no
escribe un campo TPE en el temporal. El DVR representa los valores
**estrictamente inferiores** al umbral configurado, incluso cuando toda una
región está por debajo y no hay un cruce de 320 K en su interior.

La humedad relativa se lee directamente de `rhprs`. Su función de
transferencia representa únicamente **RH > 70 %**; RH igual a 70 % queda
transparente. Los límites se ajustan al float32 inmediato anterior o posterior
al umbral para conservar ambas desigualdades estrictas en Met.3D.

Configuración aceptada, registrada el 2026-11-06:

| Parámetro | TPE, `objects.cold_air` | RH, `objects.relative_humidity` |
|---|---|---|
| Región visible | TPE < 320 K | RH > 70 % |
| Intervalo de presión | 1000–700 hPa | 1000–700 hPa |
| Intervalo de la paleta | 250–320 K; se extiende el color por debajo de 250 K | 70–100 %; se extiende el color por encima de 100 % |
| `colourmap` | `YlGnBu` | `hot_wind` |
| `reverse_colourmap` | `true` | `true` |
| `opacity` | 0.6 | 0.2 |
| `colour_steps` | 256 | 256 |
| `ray_step_size` | 0.1 | 0.1 |

Cuando ambos campos están habilitados se utiliza **un único actor DVR
multivariable**, con una función de color y opacidad por campo. Esto evita la
advertencia de Met.3D sobre artefactos al superponer dos actores DVR. La
plantilla `relative_humidity.actor.conf.j2` incorpora RH y la TPE derivada;
sus leyendas provienen de `relative_humidity_colourbar.actor.conf.j2` y
`cold_air_colourbar.actor.conf.j2`. No se requiere cobertura nubosa `tcdcprs`.

`enabled: false` permite retirar cualquiera de los dos campos y su leyenda.
Con sólo TPE se usa `cold_air.actor.conf.j2`; con sólo RH se conserva su actor
individual. Al compartir actor, la caja gráfica es la de RH: debe contener la
capa de TPE para visualizarla completa. `relative_humidity.pressure` admite
un mapa con `bottom_hpa`/`top_hpa` o `all_available`, que conserva todos los
niveles y limita la caja visible al intervalo de la escena.

Las paletas y su dirección se seleccionan con `colourmap` y
`reverse_colourmap`. Para RH, `grey` usa la paleta nativa de grises; `HCL`
recupera el color definido por `hue`, `chroma` y `luminance`, actualmente
uniforme. `colour_steps` controla la discretización gráfica y
`ray_step_size` el muestreo del render; con ambos campos se utiliza el menor
paso de los dos. Estos ajustes no cambian la resolución de los datos.

La opacidad es un valor de referencia que se acumula a lo largo de la línea
de visión; 0.2 no implica una opacidad final del 20 % para todo el volumen.
La mezcla de colores, el espesor visible y el fondo intervienen en cada píxel.
TPE combina temperatura y humedad, mientras RH mide cercanía a saturación:
el volumen de RH alta no representa directamente nubosidad ni demuestra por
sí solo el desplazamiento de una masa de aire.

### Datos ausentes y niveles bajo superficie

Por defecto, cada ejecución crea un único archivo temporal de visualización
`met3D/.runtime/<centro>-<modelo>-friaje/above_surface.nc`, con las coordenadas
nativas y los tiempos seleccionados. `data_preparation.variables` declara
los campos, unidades y aplicación de máscaras; los nombres se resuelven desde
`variables`. El módulo `src/visualize/met3D/netcdf.py` contiene
`prepare_visualization_data` y `pressure_level_mask`, reutilizables para otros
campos isobáricos o de superficie. La configuración actual copia `tmpprs`,
`spfhprs`, `rhprs` y `pressfc`, conservando valores válidos sin remuestreo ni
cuantización adicional. El NetCDF estandarizado se abre sólo para lectura.

La escritura utiliza NetCDF4, campos float32 con compresión zlib y `time`
ilimitado. Las dimensiones espaciales se declaran con su tamaño nativo antes
de escribir los campos por tiempo. Se conservan todos los niveles de `lev`.

En cada plazo se marcan como ausentes las celdas donde `lev * 100 > pressfc`.
Si falta presión superficial, se excluye la columna correspondiente. Se
conservan las máscaras originales y los valores no finitos se representan como
ausentes. No se completan huecos ni se sustituyen por cero; se admiten niveles
enteramente ausentes. El cálculo nativo de TPE de Met.3D propaga la
ausencia de temperatura o humedad. El render omite esas celdas.

En el DVR conjunto, las entradas de TPE, `tmpprs` y `spfhprs`, se enmascaran
también fuera de `objects.cold_air.pressure`. Así se limita TPE a su capa
física aunque comparta caja con RH. Esta máscara admite la clave `pressure`
por variable en el preparador genérico. RH conserva todos sus niveles en el
temporal y su intervalo visible lo delimita la caja gráfica. Los umbrales
de TPE y RH se aplican mediante las funciones de transferencia, sin recortar
los valores de los campos por dichos umbrales.

La copia temporal es necesaria porque el cálculo nativo de TPE no compara la
presión isobárica con `pressfc`; la topografía dibujada no sustituye esa máscara.
El runtime del friaje está separado del utilizado por DANA y jet.

### Reutilización del temporal durante las pruebas

Sin opciones adicionales, `--open` y `--render` reconstruyen el runtime y
generan nuevamente el temporal. Para cambiar el aspecto gráfico sin repetir
la escritura de datos, el lanzador de friaje admite:

```bash
conda run -n metvis3d python scripts/run_met3d_friaje.py \
  --netcdf data/standardized/ncep-gfs_20260620_00Z.nc \
  --open --reuse-temporal
```

También se puede combinar `--reuse-temporal` con `--render`. `--netcdf` sigue
identificando el archivo estandarizado de entrada; la bandera reutiliza
exclusivamente `above_surface.nc` del runtime correspondiente.

Antes de limpiar la escena se comprueban:

- Origen: ruta, tamaño, fecha de modificación, modelo, centro y corrida.
- Variables, unidades, precisión, dimensiones y máscaras solicitadas.
- Coordenadas horizontales, niveles y selección temporal exacta.
- Registro de preparación y `visualization_complete=1`, escrito al finalizar.

La validación lee metadatos y coordenadas, sin recorrer todos los volúmenes.
Si falta el temporal o es incompatible, el proceso se detiene sin generarlo ni
eliminar la escena anterior. Si es válido, conserva el NetCDF y renueva las
configuraciones y los fotogramas. Los temporales anteriores a estos metadatos
requieren una ejecución sin `--reuse-temporal` para quedar registrados.

Cambiar paleta, opacidad, cámara o umbrales gráficos permite reutilizar los
datos. Modificar variables, tiempos o máscaras exige regenerarlos; por
ejemplo, cambiar la capa de TPE en el DVR conjunto altera las máscaras de
temperatura y humedad específica. Activar o desactivar campos también puede
cambiar la preparación requerida. El runtime no se organiza por fecha: una
ejecución normal del mismo centro/modelo/producto sustituye el temporal previo.

### Verificación manual del friaje

La comprobación de datos se puede repetir después de preparar la escena con
`--open` o `--render`. Para el temporal actual, el registro de preparación
permite recuperar las máscaras y asociar cada tiempo con el origen:

```bash
conda run --no-capture-output -n metvis3d python - <<'PY'
import json
import numpy as np
from netCDF4 import Dataset, num2date

source_file = 'data/standardized/ncep-gfs_20260620_00Z.nc'
render_file = 'met3D/.runtime/ncep-gfs-friaje/above_surface.nc'
with Dataset(source_file) as source, Dataset(render_file) as rendered:
    assert rendered.visualization_complete == 1
    definitions = json.loads(rendered.visualization_preparation)['variables']
    levels = np.asarray(source['lev'][:], dtype=float)[:, None, None]
    for name in ('lev', 'latitude', 'longitude'):
        np.testing.assert_array_equal(source[name][:], rendered[name][:])
    source_times = list(num2date(source['time'][:], source['time'].units))
    render_times = list(num2date(rendered['time'][:], rendered['time'].units))
    source_indexes = [source_times.index(value) for value in render_times]
    for time_index in range(len(rendered.dimensions['time'])):
        source_index = source_indexes[time_index]
        surface = np.ma.masked_invalid(source['pressfc'][source_index])
        below_surface = ((levels * 100 > surface.filled(np.nan)[None, :, :])
                         | np.ma.getmaskarray(surface)[None, :, :])
        for name, definition in definitions.items():
            original = np.ma.masked_invalid(source[name][source_index])
            actual = rendered[name][time_index]
            expected_mask = np.ma.getmaskarray(original)
            if definition['mask_below_surface']:
                expected_mask = expected_mask | below_surface
            if 'pressure' in definition:
                pressure = definition['pressure']
                expected_mask = (expected_mask
                                 | (levels > pressure['bottom_hpa'])
                                 | (levels < pressure['top_hpa']))
            np.testing.assert_array_equal(np.ma.getmaskarray(actual), expected_mask)
            np.testing.assert_array_equal(actual.data[~expected_mask],
                                          original.data[~expected_mask])
    print('Coordenadas, máscaras y valores válidos comprobados.')
PY
```

La integridad del NetCDF original puede comprobarse guardando su SHA-256 antes
de la ejecución y comparándolo después. Los fotogramas se inspeccionan en el
runtime y el video se puede comprobar con:

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,nb_frames,r_frame_rate,duration \
  -of default=noprint_wrappers=1 \
  outputs/met3d/friaje/ncep-gfs/friaje_ncep-gfs_20260620_00Z.mp4
```

Comprobaciones manuales realizadas durante el desarrollo del DVR
multivariable y la reutilización del temporal, el 2026-11-05:

- Fotogramas de GFS del 2026-06-20, tiempo válido 2026-06-25 12 UTC, y
  casos sintéticos con cada campo visible por separado y ambos juntos. Un
  único DVR combinó las contribuciones sin la advertencia de dos raycasters
  superpuestos. Se comprobaron la transparencia de RH igual o inferior a
  70 % y la visibilidad del float32 inmediatamente superior; para TPE se
  comprobaron 320 K transparente y valores inferiores visibles.
- Conservación de niveles nativos y de valores válidos de RH; igualdad de
  máscaras superficiales y de las máscaras verticales de las entradas de
  TPE. Un caso con humedad sólo por encima de 700 hPa verificó la variante
  de RH en toda la columna; la configuración aceptada usa 1000–700 hPa.
- Reutilización de una selección real de dos tiempos: contenido, tamaño,
  fecha de modificación e identidad del archivo temporal permanecieron
  iguales al renovar la escena. Se admitieron cambios gráficos y se
  rechazaron cambios de origen, tiempos, máscaras, unidades, coordenadas,
  variables, archivos incompletos, antiguos sin registro, ilegibles o ausentes.
  Los rechazos conservaron los archivos de la escena anterior. También se
  comprobó la reutilización genérica de un campo sólo de superficie.
- La ejecución sin bandera volvió a generar el temporal existente. Un render
  con RH en `grey`, opacidad 0.2 y capa 1000–700 hPa confirmó la rampa de
  grises y la conservación del temporal durante la reutilización. Se
  comprobaron las configuraciones `HCL` y `grey`, y la preparación de DANA y
  jet. La opción pública vigente se denomina `--reuse-temporal`.

Estas verificaciones acreditan casos concretos y variantes de paleta. La
configuración visual aceptada el 2026-11-06 utiliza RH en `hot_wind`; antes
de publicar una animación se debe conservar evidencia del video completo con
esa configuración, corrida y tiempos. Los fotogramas de prueba de otras
paletas no sustituyen esa evidencia ni la validación meteorológica del evento.

### Antecedente: isosuperficie de TPE y cobertura nubosa

La siguiente verificación, ejecutada el 2026-11-02 con Met.3D 2.0.0b11,
corresponde a la versión anterior del producto. Se conserva como antecedente;
la composición vigente utiliza DVR de TPE y RH:

- Corrida GFS de 2026-10-14, 41 tiempos cada 3 h hasta 2026-10-19 00 UTC:
  MP4 H.264 de 1920×1080, 41 fotogramas a 6 fps y duración de 6.833333 s.
  Se inspeccionaron los fotogramas inicial e intermedio; esa composición fue
  sustituida por el DVR multivariable aceptado el 2026-11-06.
- Comparación de los 123 volúmenes temporales de temperatura, humedad y
  nubosidad: máscaras exactamente iguales a la unión de las originales y los
  puntos bajo superficie; valores válidos idénticos al origen. Coordenadas
  idénticas y SHA-256 del NetCDF original conservado:
  `c55829ced9e3ab59da6328af51b8566f868e1a09be119fab67639dd89290b164`.
- Casos manuales de variable requerida ausente y humedad con unidades `g/kg`:
  detención con mensaje contextual. Un caso pequeño con niveles 1000, 925,
  850 y 700 hPa y presiones superficiales de 950 y 800 hPa confirmó la
  exclusión de niveles bajo tierra, de una columna sin presión superficial
  y la conservación de un hueco original en los tres campos volumétricos.
- Caso sintético constante con tres tiempos (0, 3 y 6 h), temperatura de
  240 K, humedad de 0.001 kg/kg y cobertura nubosa nula: sin cruces de TPE de
  320 K en la caja 1000–700 hPa, se generaron los tres fotogramas y un MP4;
  las imágenes de los campos constantes fueron idénticas.
- Preparación de DANA y jet con dos tiempos, en un directorio de comprobación
  separado: se conservaron sus actores y la lectura directa del NetCDF.

El caso sintético con un hueco en `pressfc` mostró un artefacto en la malla del
actor nativo de topografía de Met.3D, aunque las columnas atmosféricas sí
quedaron excluidas correctamente. Esta limitación del contexto de terreno
queda pendiente para archivos con huecos de presión superficial; la corrida
utilizada para el video tiene `pressfc` completo.

## Ajuste de cámara

La cámara pertenece al YAML de cada animación, no a la sesión base. Sus nueve
componentes se encuentran en `camera.origin`, `camera.y_axis` y
`camera.z_axis`. Para ajustar una toma:

1. Abra la animación con `--open` en una estación de trabajo gráfica.
2. Ajuste la vista en Met.3D y obtenga los nueve valores de su cámara.
3. Copie esos valores al bloque `camera` del YAML de la animación.
4. Ejecute otra vez `--open` para comprobar la toma y finalmente `--render`
   para generar el video.

La sesión base no debe editarse para cambiar una cámara. El flujo copia la
sesión al runtime de la corrida y aplica allí la cámara, resolución y captura
de imágenes.

### Trayectoria de cámara

La trayectoria es opcional y se configura en `camera.trajectory`. Para usar
una cámara fija, indique `enabled: false` o no incluya esa sección. Con una
trayectoria habilitada, `type: orbit` es el único tipo disponible actualmente.
La órbita comienza desde la cámara del YAML, se acerca al centro horizontal de
la escena, completa un giro y mantiene brevemente la vista final. El centro
proviene de los límites geográficos de la escena, sin detectar automáticamente
el fenómeno. `--open` carga la secuencia en Met.3D para revisarla en el editor
de cámara; `--render` la utiliza en modo batch.

En el YAML de DANA se pueden ajustar:

- `minimum_frames`: cantidad mínima de fotogramas del video con trayectoria.
- `frames_per_interval`: cantidad de fotogramas por tiempo usada para planificar
  la captura; el proceso puede aumentarla para cumplir el mínimo total. La
  captura final de Met.3D puede variar en un fotograma.
- `keyframes`: posiciones que definen la curva de cámara, al menos cinco; son
  distintas de los fotogramas que se generan para el video.
- `zoom_factor`: factor de acercamiento respecto a la distancia inicial;
  `0.94` la reduce al 94 %. `zoom_fraction` define la fracción de la
  trayectoria usada para el acercamiento.
- `target_world_z`: coordenada vertical gráfica del centro de referencia;
  no se expresa en hPa. `tension` controla la interpolación de la trayectoria.
- `end_hold_fraction`: fracción de la secuencia reservada para mantener la
  vista final.

La cámara se desplaza alrededor de la escena; al mantenerla enfocada hacia el
centro, la órbita puede percibirse como un giro del mapa. La composición y el
recorrido siguen sujetos a revisión visual y meteorológica.

### Tiempos y fotogramas

El proceso lee los tiempos válidos del NetCDF. `timeline.selection` acepta
`all_available` o `first_hours`; en este último caso, `max_forecast_hours`
limita la selección a partir del primer tiempo disponible. Antes de seleccionar
el intervalo, se comprueba toda la coordenada temporal del archivo: debe tener
al menos un tiempo, estar ordenada, no contener valores ausentes o duplicados
y, cuando hay varios tiempos, conservar un intervalo regular de segundos
enteros. Un archivo con intervalos irregulares se rechaza aunque la selección
solicitada abarque sólo una parte regular.

Esta exigencia pertenece al motor actual de animación y a su configuración
batch de paso temporal único; no es una condición del contrato del NetCDF
estandarizado. El IFS del 2026-06-20 tiene 65 tiempos válidos, ordenados y sin
duplicados: F+0 a F+144 cada 3 h y F+150 a F+240 cada 6 h, exactamente como
declara `config/models/ifs.yaml`. `build_timeline` lo rechaza al pasar del
2026-06-26 00 UTC al 2026-06-26 06 UTC. La corrida contiene las variables
requeridas por el nuevo producto, pero su apertura/render completo sigue
pendiente de admitir el calendario mixto sin interpolar datos. Limitar
`first_hours` a 144 h no evita actualmente la validación del archivo completo.

Con cámara fija se genera un fotograma por tiempo seleccionado. Con trayectoria,
se calculan fotogramas adicionales para mover la cámara mientras cada campo
meteorológico permanece en su tiempo válido; se comprueba que todos los
tiempos seleccionados estén presentes y en orden. Si sólo hay un tiempo, la
cámara recorre la trayectoria sobre ese mismo campo. El número real de
fotogramas puede variar en uno respecto al previsto por la captura de Met.3D,
siempre que cumpla el mínimo y las comprobaciones de tiempo.

`output.frames_per_second` define la velocidad de reproducción del MP4 y,
junto con la cantidad de fotogramas, determina su duración. Los nombres de
los PNG temporales incluyen el tiempo válido, pero el video no incorpora
actualmente una etiqueta visible con fecha y hora.
