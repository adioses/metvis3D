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

Ambas animaciones usan exclusivamente la escena de Met.3D
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
