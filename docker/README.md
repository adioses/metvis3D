# Docker local

La imagen reproduce el entorno Conda Linux definido en `../environment.yml`.
Los GRIB y resultados se montarán como volúmenes; no se copian a la imagen.

El Dockerfile no se desplegará en el HPC. Allí se instalará directamente el
mismo `environment.yml` con Conda.
