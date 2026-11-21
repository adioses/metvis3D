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
assets/       DEM, límites, paletas meteorológicas y recursos institucionales.
data/         Datos de trabajo no versionados.
outputs/      PNG, videos y productos publicados no versionados.
website/      Biblioteca web local y ambiente Conda independiente.
docs/         Especificaciones técnicas.
```

Docker Compose monta los GRIB2 originales desde `../source` como `data/raw` en
modo de sólo lectura. No deben copiarse, moverse ni modificarse desde los
procesos del proyecto. Los índices `.idx` de cfgrib se crean junto a cada GRIB
original.

La raíz del proyecto puede ubicarse en cualquier ruta de la workstation o del
HPC. En esos ambientes, los GRIB2 deben estar disponibles bajo `data/raw/` con
la jerarquía definida por los YAML de `config/models/`, preferiblemente mediante
un montaje de sólo lectura. Las configuraciones no contienen rutas de usuario
ni rutas absolutas de una máquina.

`paraview/render_data/` contiene datos temporales preparados exclusivamente
para ParaView. `paraview/render_cache/` contiene los fotogramas de trabajo.
Ambos directorios son descartables; los videos aprobados se escriben en
`outputs/`.

Las guías operativas para generar videos y ajustar cámaras están en:

- `docs/met3d.md`
- `docs/paraview.md`

La composición aprobada de anticiclones en Met.3D combina presión al nivel del
mar por rangos con partículas de viento y rastros de seis horas en todo el
dominio disponible de Sudamérica. La referencia es IFS del 2026-09-03 00 UTC,
de +0 a +120 h. La configuración está en
`config/met3d/animations/south_america_anticyclones.yaml` y la paleta en
`assets/colormaps/mean_sea_level_pressure.yaml`.

```bash
conda run -n metvis3d python scripts/run_met3d_anticyclones.py \
  --netcdf data/standardized/ecmwf-ifs_20260903_00Z.nc \
  --render
```

Las opciones de apertura, reutilización del temporal y las verificaciones se
describen en [la guía Met.3D](docs/met3d.md#anticiclones).

## Conversión GRIB2 a NetCDF

El lanzador operativo recibe modelo, fecha de inicialización, ciclo y horizonte
de una única corrida. Lee de la configuración versionada el centro productor,
las rutas y nombres de los GRIB2, las variables seleccionadas y la convención
longitudinal; produce un único NetCDF bajo `data/standardized/`.

```bash
conda run -n metvis3d python scripts/convert_grib2_to_netcdf.py \
  --model gfs \
  --date 20260816 \
  --cycle-hour 00 \
  --forecast-hours 120 \
  --area -130 -56 -10 30
```

El directorio `data/raw/` debe contener la jerarquía de datos indicada en el
YAML del modelo. El recorte es opcional; omita `--area` para conservar el
dominio completo. El proceso se detiene si falta un GRIB2 previsto, los GRIB2
no corresponden a una misma corrida o el NetCDF final ya existe.

Los modelos operativos disponibles son `gfs` e `ifs`. Los argumentos
`--dia`, `--hh` y `--horas` son equivalentes a `--date`, `--cycle-hour` y
`--forecast-hours`, respectivamente.

## Entorno

El entorno de referencia es Conda:

```bash
conda env create -f environment.yml
conda activate metvis3d
pip install -e .
```

El entorno unificado requiere Linux y OpenGL para las visualizaciones 3D. El
archivo incluye Met.3D, ParaView y FFmpeg, por lo que el HPC usa el mismo
`environment.yml` directamente mediante Conda, sin instalaciones externas de
esos programas.

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

## Visualizaciones 3D

La biblioteca web consulta videos ya generados, con Flask, Jinja y Gunicorn.
El usuario aprobó el recorrido visual y funcional y confirmó acceso desde la
red local el 2026-11-21. La máquina de desarrollo se utiliza con arranque manual;
el servicio automático se reserva para la máquina final.

La instalación inicial utiliza un ambiente separado del científico:

```bash
conda env create -f website/environment.yml
cd website
conda run -n metvis3d-web python -m pip install --no-build-isolation --no-deps -e .
cd ..
```

Desde la raíz del proyecto, iniciar la web con:

```bash
conda run --no-capture-output -n metvis3d-web python website/scripts/run_website.py
```

Abrir `http://127.0.0.1:8050/` en esta computadora o
`http://<IP_LOCAL>:8050/` desde otro equipo de la misma red. La dirección y el
puerto se configuran en `website/config/website.yaml`; actualmente escucha en
`0.0.0.0:8050`. Detener con **Ctrl+C**. Si cambia esa configuración, detener y
volver a iniciar el proceso para aplicarla.

La preparación manual de contenido se ejecuta con:

```bash
conda run --no-capture-output -n metvis3d-web python website/scripts/publish_videos.py
```

`website/config/publication.yaml` limita el origen a la referencia acordada.
El proceso copia los MP4 sin recodificarlos, comprueba SHA-256 y genera sus JPG
y metadatos de reproducción. La web sólo lee `website/video/recent/` y
`website/video/historical/`; refleja los cambios al recargar. Si un MP4 se
incorpora directamente, el JPG del mismo nombre base es opcional: su ausencia
muestra una imagen neutra y conserva la reproducción. Las variables y periodos
meteorológicos sólo se muestran cuando se conocen y se declaran explícitamente.

La plantilla de servicio está en `website/deploy/metvis3d-web.service.in`.
En la máquina final, `website/scripts/prepare_service.py`, ejecutado con su
ambiente `metvis3d-web`, generará `website/.local/metvis3d-web.service` con las
rutas de esa instalación. Su instalación y arranque tras reiniciar siguen
pendientes para ese equipo. No instalar el servicio automático en desarrollo.

El contrato de archivos, alcance y comprobaciones está en
[el plan de implementación](docs/website-plan-implementacion.md). Los registros
locales de comprobación se conservan en `website/validation/` y no se versionan.
