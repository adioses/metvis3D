# Guía de animaciones con ParaView

ParaView mantiene un flujo independiente de Met.3D. La escena geográfica se
define en `config/paraview/scenes/` y cada animación en
`config/paraview/animations/`. La animación selecciona sus capas, intervalos
verticales, variables, estilo, cámara y salida; el NetCDF se entrega en la
línea de comandos.

## Animación disponible

`config/paraview/animations/south_america_jet.yaml` genera una escena de jet
sobre Sudamérica con estas capas:

- `terrain`: DEM GMTED2010 proyectado a Lambert Conformal Conic.
- `jet`: rapidez de viento derivada de `ugrdprs` y `vgrdprs`, entre 500 y
  50 hPa, ubicada verticalmente mediante `hgtprs` y representada con una
  isosuperficie de 50 m s-1.

La exageración vertical es 60 y se aplica por igual al terreno y al volumen
atmosférico. La altura geopotencial ya expresa la separación no lineal de los
niveles isobáricos; no se aplica una transformación logarítmica adicional.

## Preparación

Desde la raíz del proyecto, prepare los VTS y la configuración transitoria:

```bash
conda run -n metvis3d python scripts/run_paraview_animation.py \
  --animation config/paraview/animations/south_america_jet.yaml \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --prepare-only
```

Los datos temporales se sobrescriben por capa bajo:

```text
paraview/render_data/south_america/terrain/
paraview/render_data/south_america/jet/
```

La configuración transitoria y los fotogramas de la última ejecución de la
escena se guardan en `paraview/render_cache/south_america/`.

## Revisión interactiva y ajuste de cámara

Abra ParaView, defina en su Python Shell la configuración preparada y ejecute
la plantilla `paraview/templates/open_prepared_animation.py` mediante
**View > Python Shell > Run Script**:

```python
import os

os.environ["METVIS3D_PARAVIEW_CONFIGURATION"] = (
    "/home/alen/Documents/Senamhi/metvis3D/"
    "paraview/render_cache/south_america/render_configuration.json"
)
```

La plantilla carga el primer plazo de las capas preparadas y aplica la misma
cámara del batch. Ajuste la vista en ParaView y obtenga sus valores desde la
Python Shell:

```python
view = GetActiveView()
print(list(view.CameraPosition))
print(list(view.CameraFocalPoint))
print(list(view.CameraViewUp))
```

Copie los tres vectores a `camera.position`, `camera.focal_point` y
`camera.view_up` en el YAML de la animación. Mantenga además el tipo de
proyección, `parallel_scale` y `view_angle_degrees` que correspondan a la toma.
Prepare de nuevo la animación antes de ejecutar el render batch.

## Render batch

Para renderizar todos los plazos con `pvpython` instalado en el ambiente Conda:

```bash
conda run -n metvis3d python scripts/run_paraview_animation.py \
  --animation config/paraview/animations/south_america_jet.yaml \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --render
```

El render batch usa EGL explícitamente junto con el modo offscreen, por lo que
no depende de `DISPLAY`, de una sesión gráfica ni del reenvío X11 de SSH.

El MP4 histórico queda en
`outputs/paraview/south_america_jet/<centro>-<modelo>/`.

## Ausencias de altura geopotencial

La capa jet permite completar exclusivamente huecos aislados de `hgtprs` en
los VTS temporales. La política se declara en el YAML y usa el promedio de los
vecinos ortogonales válidos. No modifica el NetCDF. Una ausencia contigua, una
ausencia en viento u otro campo requerido, o un número de plazos o niveles
afectados mayor que los límites configurados detiene la preparación.
