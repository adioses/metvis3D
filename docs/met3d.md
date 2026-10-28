# Guía de animaciones con Met.3D

Met.3D mantiene un flujo independiente para explorar y generar videos
meteorológicos desde un NetCDF estandarizado. Cada animación declara su escena,
variables, objetos, cámara, línea de tiempo y salida bajo
`config/met3d/animations/`; las configuraciones temporales se generan en
`met3D/.runtime/` y no se versionan.

## Animaciones disponibles

| Animación | Configuración | Estructura meteorológica |
|---|---|---|
| DANA | `config/met3d/animations/south_america_dana.yaml` | Isosuperficie de PV baroclínica de -5 PVU entre 500 y 250 hPa, con `pressfc` como topografía de la coordenada presión. |
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
