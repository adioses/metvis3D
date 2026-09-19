# metvis3d

Base de desarrollo para estandarizar datos meteorológicos GRIB2 y producir
visualizaciones y animaciones 3D reproducibles.

## Decisiones iniciales

- Un NetCDF CF por modelo y corrida.
- Variables de superficie: `(time, latitude, longitude)`.
- Variables atmosféricas: `(time, pressure, latitude, longitude)`.
- Los niveles de presión se conservan tal como los entrega cada modelo.
- Jupyter Lab sirve para ajustar configuraciones; la ejecución repetible se
  realiza mediante comandos Python y archivos YAML.
- ParaView y Blender son motores externos llamados mediante plantillas.

## Estructura

```text
config/       Configuración versionada de modelos, variables y productos.
src/          Paquete Python `metvis3d`.
notebooks/    Exploración y ajuste visual; no contiene lógica operativa única.
paraview/     Plantillas y scripts de render ParaView.
blender/      Plantillas y scripts de acabado Blender.
assets/       DEM, límites y recursos institucionales.
data/         Datos de trabajo no versionados.
outputs/      PNG, videos y productos publicados no versionados.
tests/        Pruebas automatizadas.
docs/         Especificaciones técnicas.
```

Los datos originales de prueba permanecen en `../dev/source`. No deben
copiarse al repositorio: use enlaces simbólicos o rutas configuradas. Los
índices `.idx` de cfgrib se crearán junto a cada GRIB original.

`paraview/render_data/` contiene datos temporales preparados exclusivamente
para ParaView. `paraview/render_cache/` contiene vistas previas o fotogramas
durante el ajuste de una plantilla. Ambos directorios son descartables; una
plantilla aprobada renderiza directamente hacia `outputs/`.

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
binarios instalados de ParaView, Blender y FFmpeg.

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
