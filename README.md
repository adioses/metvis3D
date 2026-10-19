# metvis3d

Base de desarrollo para estandarizar datos meteorológicos GRIB2 y producir
visualizaciones y animaciones 3D reproducibles.

## Decisiones iniciales

- Un NetCDF CF por modelo y corrida.
- Variables de superficie: `(time, latitude, longitude)`.
- Variables atmosféricas: `(time, lev, latitude, longitude)`.
- Los niveles de presión se conservan tal como los entrega cada modelo.
- Jupyter Lab sirve para ajustar configuraciones; la ejecución repetible se
  realiza mediante comandos Python y archivos YAML.
- ParaView y Met.3D generan videos desde configuraciones y scripts reproducibles.

## Estructura

```text
config/       Configuración versionada de conversión, análisis y animaciones.
src/          Paquetes Python de estandarización y visualización.
notebooks/    Exploración y ajuste visual; no contiene lógica operativa única.
met3D/        Sesión y plantillas nativas de Met.3D.
paraview/     Scripts de render ParaView y datos temporales descartables.
assets/       DEM, límites y recursos institucionales.
data/         Datos de trabajo no versionados.
outputs/      PNG, videos y productos publicados no versionados.
docs/         Especificaciones técnicas.
```

Docker Compose monta los GRIB2 originales desde `../source` como `data/raw` en
modo de sólo lectura. No deben copiarse, moverse ni modificarse desde los
procesos del proyecto. Los índices `.idx` de cfgrib se crean junto a cada GRIB
original.

`paraview/render_data/` contiene datos temporales preparados exclusivamente
para ParaView. `paraview/render_cache/` contiene los fotogramas de trabajo.
Ambos directorios son descartables; los videos aprobados se escriben en
`outputs/`.

Las guías operativas para generar videos y ajustar cámaras están en:

- `docs/met3d.md`
- `docs/paraview.md`

## Conversión GRIB2 a NetCDF

El lanzador operativo recibe los GRIB2 de una única corrida, el YAML del modelo
y el centro productor. Lee de la configuración las variables seleccionadas y
la convención longitudinal, y produce un único NetCDF bajo
`data/standardized/`.

```bash
conda run -n metvis3d python scripts/convert_grib2_to_netcdf.py \
  "data/raw/GFS/*.grib2" \
  --model-configuration config/models/gfs.yaml \
  --center ncep \
  --area -130 -56 -10 30
```

El recorte es opcional; omita `--area` para conservar el dominio completo. El
proceso se detiene si los GRIB2 no corresponden a una misma corrida o si el
NetCDF final ya existe.

## Entorno

El entorno de referencia es Conda:

```bash
conda env create -f environment.yml
conda activate metvis3d
pip install -e .
```

Docker Compose es el entorno local de desarrollo. Ejecuta Conda mediante
Micromamba dentro de una imagen Linux y monta `../source` como `data/raw` en
modo solo lectura. El HPC ejecutará el mismo `environment.yml` con Conda y los
binarios instalados de ParaView, Met.3D y FFmpeg.

## Desarrollo local con Docker

```bash
docker compose up --build
```

Jupyter Lab quedará disponible solo en esta Mac mediante la URL con token que
aparece en los registros del contenedor. Para abrir comandos puntuales dentro
del mismo entorno:

```bash
docker compose run --rm dev wgrib2 -version
docker compose run --rm dev python -c "import pygrib, netCDF4"
```
