# Estándar de datos inicial

Cada corrida produce un único NetCDF CF con variables de superficie y presión.

## Dimensiones y coordenadas

- `time`: tiempo válido, representado al final de cada periodo de pronóstico.
- `pressure`: niveles nativos de presión del modelo, en Pa.
- `latitude`, `longitude`: coordenadas geográficas, con longitudes en -180 a 180.
- `forecast_reference_time`: coordenada escalar de inicialización.
- `forecast_period`: lead time asociado a cada `time`.

Las variables de niveles usan `(time, pressure, latitude, longitude)`; las de
superficie usan `(time, latitude, longitude)`. Los campos estáticos, como la
orografía, no requieren `time`.

La conversión lee directamente los GRIB y escribe el NetCDF final. No se
generan NetCDF parciales por variable ni por paso temporal.
