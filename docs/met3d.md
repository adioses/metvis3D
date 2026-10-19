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
- El ambiente Conda `met3d`, con el binario `Met3D` instalado.
- La sesión base `met3D/sessions/south_america_dana_base.session.config`.

Los comandos siguientes se ejecutan desde la raíz del proyecto.

## DANA

Preparar los archivos temporales sin abrir Met.3D:

```bash
conda run -n metvis3d python scripts/run_met3d_dana.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --prepare-only
```

Abrir la escena para revisarla:

```bash
conda run -n metvis3d python scripts/run_met3d_dana.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc
```

Renderizar todos los plazos y codificar el MP4:

```bash
conda run -n metvis3d python scripts/run_met3d_dana.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --render
```

El video se conserva bajo `outputs/met3d/dana/<centro>-<modelo>/`.

## Jet

Preparar, abrir o renderizar el jet usa el mismo patrón:

```bash
conda run -n metvis3d python scripts/run_met3d_jet.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --prepare-only
```

```bash
conda run -n metvis3d python scripts/run_met3d_jet.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc
```

```bash
conda run -n metvis3d python scripts/run_met3d_jet.py \
  --netcdf data/standardized/ncep-gfs_20260816_00Z.nc \
  --render
```

El video se conserva bajo `outputs/met3d/jet/<centro>-<modelo>/`.

## Ajuste de cámara

La cámara pertenece al YAML de cada animación, no a la sesión base. Sus nueve
componentes se encuentran en `camera.origin`, `camera.y_axis` y
`camera.z_axis`. Para ajustar una toma:

1. Abra la animación con el comando sin `--render`.
2. Ajuste la vista en Met.3D y guarde los valores aprobados de la cámara en la
   copia runtime de la sesión.
3. Copie esos nueve valores al bloque `camera` del YAML de la animación.
4. Ejecute de nuevo con `--prepare-only` y compruebe la toma antes del batch.

La sesión base no debe editarse para cambiar una cámara. El flujo copia la
sesión al runtime de la corrida y aplica allí la cámara, resolución y captura
de imágenes.
