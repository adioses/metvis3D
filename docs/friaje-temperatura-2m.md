# Diagnóstico 2D del descenso de temperatura a 2 m

Este diagnóstico cuantifica el enfriamiento simulado en una corrida y permite
revisar su coherencia espacial y temporal antes de interpretar una animación
de friaje. Se conserva el NetCDF estandarizado, sin interpolación ni relleno
de valores. Los resultados son de modelo, no observaciones de estaciones.

## Ejecución reproducible

```bash
conda run -n metvis3d python scripts/analyze_friaje_tmp2m.py \
  --netcdf data/standardized/ncep-gfs_20261014_00Z.nc
```

La lógica reside en `src/visualize/temperature_drop_maps.py` y los parámetros
en `config/analysis/friaje_tmp2m.yaml`. `--configuration` permite utilizar otro
YAML. El dominio inicial es 85–50° W, 30° S–5° N, con costas y fronteras
nacionales locales de Natural Earth, sin descargas durante la ejecución.

Las entradas principales son `tmp2m` en K y las componentes del viento a 10 m
en m/s, con dimensiones `(time, latitude, longitude)`. La temperatura absoluta
se expresa en °C. Al ser una variable a 2 m sobre el suelo, no se aplica la
máscara de niveles isobáricos bajo superficie utilizada en los mapas de TPE.

## Comparación temporal

Se utiliza:

**Descenso(t) = T₂m(t − 24 h) − T₂m(t)**

- Positivo, azul: enfriamiento respecto de la misma hora del día anterior.
- Negativo, rojo: calentamiento.
- Gris: comparación no disponible o dato ausente.

El intervalo se declara en `analysis.lag_hours`; las dos horas deben existir
exactamente en la coordenada temporal. No se interpola en el tiempo ni se
selecciona una hora cercana. Las primeras 24 horas sin referencia anterior
se conservan con temperatura absoluta y un aviso de comparación no disponible.
Si falta una de las temperaturas de un par, la diferencia queda ausente.
Si falta una hora requerida dentro de la cobertura, el proceso se detiene con
el modelo, archivo y tiempos involucrados.

Comparar la misma hora reduce la contribución del ciclo diurno. No aísla por
sí solo la advección de aire frío: la temperatura superficial también cambia
con nubosidad, lluvia y otros procesos. El análisis no aplica un umbral de
descenso para declarar automáticamente un friaje.

## Productos

Se guardan en `outputs/analysis/friaje-tmp2m/<centro>-<modelo>/<YYYYmmdd_HHZ>/`:

- `temperature_*.png`: temperatura absoluta y descenso, con escalas fijas,
  viento a 10 m, fronteras y referencias geográficas.
- `maximum_cooling_24h.png`: máximo de la diferencia por celda y final de la
  ventana en que ocurre. Cada celda puede corresponder a una fecha distinta;
  el mapa no describe un único instante. Los empates conservan la primera
  ventana. El panel de fechas sólo muestra enfriamientos positivos; los
  máximos negativos permanecen en el CSV como evidencia de calentamiento.
- `reference_series.png`: temperatura y descenso en celdas próximas a Puerto
  Maldonado, Pucallpa e Iquitos, sin interpolación. Las coordenadas solicitadas
  son aproximadas y las efectivamente utilizadas aparecen en los gráficos y CSV.
- `temperature_analysis_*.pdf`: las mismas láminas y los dos resúmenes.
- `reference_series.csv`, `reference_summary.csv`, `regional_statistics.csv`
  y `maximum_cooling_by_cell.csv`: temperaturas, diferencias, ventanas,
  coordenadas y cantidades de pares válidos. La mínima de la serie se calcula
  sobre los tiempos disponibles; no equivale a una mínima diaria observada.
- `analysis_summary.md`: resumen numérico de los puntos y comparación con TPE.

### Comparación nocturna a hora fija

`analysis.nighttime` activa dos láminas adicionales en el PDF y sus PNG:
`nighttime_reference_series.png` y `nighttime_maximum_cooling_24h.png`.
Los CSV `nighttime_reference_series.csv`, `nighttime_reference_summary.csv`
y `nighttime_cooling_by_cell.csv` conservan temperaturas, diferencias,
coordenadas, ventanas y cantidades de pares válidos.

La configuración inicial selecciona las **01:00 de Perú (06 UTC)**,
con `local_hour: 1` y `local_utc_offset_hours: -5`. Esta hora está presente
tanto en los plazos de 3 h como en los de 6 h de IFS. Se compara exactamente
la misma hora de días distintos, sin sustituir muestras ni interpolar.
Se exige que exista esa hora en todos los días entre la primera y última
muestra seleccionadas. Con `nighttime: null` se conserva el diagnóstico
general sin este complemento.

El menor valor a esa hora **no es la mínima de toda la noche**. Tampoco
conviene calcular mínimas diarias mezclando sin advertencia días con
muestreos distintos: una salida cada 6 h puede omitir temperaturas que sí
captura una salida cada 3 h. Los mapas generales mantienen todos los tiempos
nativos para revisar las demás horas. El resumen nocturno por celda tampoco
representa un único instante.

Las flechas se submuestrean sólo para el dibujo y mantienen una escala común;
los colores conservan todas las celdas nativas. Las escalas son editables en
YAML y los extremos fuera de escala se indican mediante las extensiones de
las barras de color, sin recortar los valores numéricos.

La comparación opcional de TPE reutiliza las variables, niveles, umbral y
ecuación de `config/analysis/friaje_tpe.yaml`. Se configura mediante
`analysis.tpe_comparison_configuration`; con `null`, el diagnóstico requiere
sólo las entradas de superficie. Cuando está habilitada, se respetan las
máscaras originales y la presión superficial de cada referencia, y se genera
`reference_tpe_comparison.csv`.

## Resultados de la corrida GFS de 2026-10-14 00 UTC

Se analizaron 41 tiempos cada 3 h, hasta 2026-10-19 00 UTC. Hay 33 ventanas
de 24 horas, desde el par 14–15 de octubre a las 00 UTC hasta el par 18–19
de octubre a las 00 UTC. Se generaron 41 mapas, dos resúmenes y un PDF de
43 páginas.

| Referencia | Celda lat/lon | Mayor descenso en 24 h | Final de la ventana UTC | T anterior → final |
|---|---|---:|---|---|
| Puerto Maldonado | −12.50°, −69.25° | 12.80 °C | 16/10 15:00 | 36.72 → 23.91 °C |
| Pucallpa | −8.50°, −74.50° | 10.43 °C | 18/10 15:00 | 32.79 → 22.36 °C |
| Iquitos | −3.75°, −73.25° | 12.05 °C | 17/10 18:00 | 37.54 → 25.48 °C |

Son diferencias entre la misma hora de dos días consecutivos. Los máximos
ocurren a las 10:00 o 13:00 hora peruana, por lo que destacan reducciones
diurnas. Las mínimas de las series son 19.59 °C en Puerto Maldonado
(17/10 09 UTC), 22.26 °C en Pucallpa (16/10 09 UTC) y 22.69 °C en Iquitos
(15/10 09 UTC).

En Puerto Maldonado, a las 09 UTC, la temperatura baja de 24.25 °C el día 15
a 23.08 °C el 16 y a 19.59 °C el 17; luego vuelve a 22.85 °C el 18. En
Iquitos, las temperaturas a esa hora permanecen aproximadamente entre 22.7
y 23.9 °C durante el período, sin un descenso nocturno comparable al gran
cambio diurno del día 17. Los máximos de las tres referencias tampoco siguen
por sí solos una secuencia simple de sur a norte.

La corrida **sí contiene enfriamiento superficial simulado**. Estos datos
permiten revisar un posible ingreso, pero aún no demuestran que todas las
caídas correspondan al mismo friaje ni que éste haya ocurrido realmente.
La coherencia espacial de los mapas de los días 16–18 y el viento deben
contrastarse con documentación u observaciones del evento.

### Relación con el umbral de TPE

| Referencia | TPE mínima a 925 hPa | TPE mínima a 850 hPa |
|---|---:|---:|
| Puerto Maldonado | 331.48 K | 337.34 K |
| Pucallpa | 338.32 K | 337.65 K |
| Iquitos | 344.16 K | 341.77 K |

En los 41 tiempos, la TPE a 925, 850 y 700 hPa de estas referencias permanece
por encima de 320 K. Por tanto, el descenso a 2 m no viene acompañado de un
cruce de ese umbral isobárico en esas celdas. **La ausencia de la isosuperficie
de 320 K sobre estas referencias no permite descartar la fecha por falta de
enfriamiento.** Antes de cambiar la corrida conviene revisar también la
pertinencia del umbral para la estructura que se pretende mostrar. No se ha
cambiado el valor de 320 K ni la animación.

## Verificación manual del 2026-11-03

- Comparación directa de `tmp2m[:-8] − tmp2m[8:]` con los máximos registrados:
  19 881 celdas del dominio, todas con 33 pares válidos y diferencias exactas.
- Comprobación de 41 mapas temporales, PDF de 43 páginas, 33 filas de
  estadística regional, 123 registros de series y nueve comparaciones de TPE.
- Caso sintético con temperaturas lineales cada 3 h: diferencias exactas de
  +6 y −6 °C a 24 h, ocho tiempos iniciales sin referencia y unión correcta
  de máscaras. Se verificó la elección del primer máximo en empates.
- Detención contextual ante tiempos duplicados, ausencia de la hora anterior
  requerida y cobertura inferior al intervalo de comparación.
- Ejecución integral sobre una grilla 5×5 con tiempos 0/24/48 h y temperaturas
  280/277/276 K: máximos de 3 °C en la primera ventana. Una celda con
  280/281/282 K conserva un máximo negativo de −1 °C; una celda completamente
  ausente no recibe máximo ni fecha; otra con referencia inicial ausente
  conserva sólo la comparación válida de 1 °C. Se generaron los tres mapas.
- El NetCDF original conserva el SHA-256 registrado en las verificaciones
  anteriores: `c55829ced9e3ab59da6328af51b8566f868e1a09be119fab67639dd89290b164`.

Una comprobación de los máximos puede repetirse después de la ejecución:

```bash
conda run --no-capture-output -n metvis3d python - <<'PY'
import csv
from pathlib import Path
import numpy as np
from netCDF4 import Dataset

directory = Path('outputs/analysis/friaje-tmp2m/ncep-gfs/20261014_00Z')
with Dataset('data/standardized/ncep-gfs_20261014_00Z.nc') as source:
    lat = np.flatnonzero((source['latitude'][:] >= -30) & (source['latitude'][:] <= 5))
    lon = np.flatnonzero((source['longitude'][:] >= -85) & (source['longitude'][:] <= -50))
    temperature = np.asarray(source['tmp2m'][:, lat[0]:lat[-1]+1, lon[0]:lon[-1]+1], dtype=float)
    expected = (temperature[:-8] - temperature[8:]).max(axis=0)
with (directory / 'maximum_cooling_by_cell.csv').open() as file:
    rows = list(csv.DictReader(file))
actual = np.array([float(row['maximum_drop_c']) for row in rows]).reshape(expected.shape)
np.testing.assert_array_equal(actual, expected)
assert all(row['valid_pairs'] == '33' for row in rows)
print('Máximos de las 19 881 celdas comprobados.')
PY
```

## Resultados de la corrida IFS de 2026-06-20 00 UTC

```bash
conda run -n metvis3d python scripts/analyze_friaje_tmp2m.py \
  --netcdf data/standardized/ecmwf-ifs_20260620_00Z.nc
```

Se analizaron 65 tiempos hasta el 30 de junio a las 00 UTC: cada 3 h hasta
F+144 y cada 6 h desde F+150. Las 57 ventanas de 24 h tienen ambas horas
exactas. Se generaron 65 mapas regionales, cuatro láminas de resumen y un
PDF de 69 páginas, bajo
`outputs/analysis/friaje-tmp2m/ecmwf-ifs/20260620_00Z/`.

### Descensos considerando todas las horas

| Referencia | Mayor descenso en 24 h | Final de la ventana en Perú | T anterior → final |
|---|---:|---|---|
| Puerto Maldonado | 6.64 °C | 23/06 13:00 | 30.26 → 23.62 °C |
| Pucallpa | 3.96 °C | 24/06 10:00 | 28.31 → 24.35 °C |
| Iquitos | 3.51 °C | 20/06 19:00 | 27.83 → 24.32 °C |

Estos máximos no caracterizan por sí solos el enfriamiento de madrugada.

### Temperaturas nocturnas

Hay diez muestras a la 01:00, del 20 al 29 de junio, y nueve comparaciones
entre noches consecutivas. Las coordenadas nativas son las mismas de las
referencias GFS anteriores.

| Referencia | Mayor descenso entre noches a la 01:00 | Fechas locales del par | Menor T a la 01:00 | Fecha local |
|---|---:|---|---:|---|
| Puerto Maldonado | 2.66 °C | 23 → 24/06 | 17.43 °C | 27/06 |
| Pucallpa | 0.97 °C | 24 → 25/06 | 21.48 °C | 28/06 |
| Iquitos | 1.89 °C | 20 → 21/06 | 22.62 °C | 29/06 |

La señal nocturna más clara está en Puerto Maldonado: a la 01:00 pasa de
21.92 °C el día 23 a 19.26 °C el 24 y 18.17 °C el 25. A las 04:00, también
disponibles durante esa parte de la corrida, pasa de 21.80 a 18.48 y
17.91 °C; el descenso del 23 al 24 a esa hora es 3.32 °C. Las 04:00 dejan de
estar disponibles al pasar a plazos de 6 h y no se completan artificialmente.

Pucallpa presenta una disminución gradual a la 01:00, de 23.98 °C el día 23
a 21.48 °C el 28. Iquitos pasa de 24.30 °C el 24 a 22.71 °C el 26;
su mayor descenso nocturno de 24 h corresponde a un episodio anterior,
del 20 al 21. No deben confundirse esos máximos de fechas distintas como
si describieran automáticamente un único ingreso frío.

Los mapas del 24–25 a las 06 UTC muestran enfriamiento sobre Bolivia y el
entorno de Madre de Dios, con cambios menores hacia la selva central y norte.
**Hay enfriamiento nocturno simulado, especialmente al sur, pero la señal
es más débil y gradual hacia Pucallpa e Iquitos.** Este archivo permite
examinar el ingreso; todavía no se clasifica como un friaje validado ni se
adopta como evento definitivo de la animación. Las temperaturas absolutas de
junio tampoco constituyen por sí solas una anomalía climatológica ni deben
compararse con las de octubre como si sólo cambiara la intensidad del evento.

En las tres referencias, TPE permanece por encima de 320 K a 925, 850 y
700 hPa. Puerto Maldonado se aproxima al umbral a 925 hPa, con un mínimo
de 320.41 K. Esto se limita a esas celdas y niveles, no al dominio completo.

### Verificación manual del caso IFS

- Relectura independiente del NetCDF y asociación por fecha exacta:
  máximos y fechas de 19 881 celdas coinciden exactamente, tanto para las
  57 ventanas generales como para las nueve nocturnas. También coinciden
  los mínimos a la 01:00. **En IFS no se debe utilizar el desplazamiento fijo
  de ocho registros del ejemplo GFS:** el calendario cambia a 6 h.
- Los 30 registros nocturnos coinciden directamente con el NetCDF; las tres
  diferencias iniciales permanecen ausentes. Hay 195 filas de series
  generales, 57 de estadística regional y nueve comparaciones de TPE.
- Caso manual de calendario mixto 3/6 h con descenso lineal de 0.25 K/h:
  los 57 pares dan exactamente 6 °C y los ocho tiempos iniciales quedan
  sin comparación. Se verificó que todos los pares estén separados 24 h.
- Ejecución del complemento nocturno sobre una grilla sintética 5×5 con ese
  calendario: una celda completamente ausente conserva vacíos; la ausencia
  de la primera temperatura nocturna reduce los pares de nueve a ocho;
  una celda con calentamiento conserva un máximo de −6 °C. La eliminación
  de una hora nocturna intermedia detiene el proceso con la fecha local.
- Se revisaron visualmente las series nocturnas, su mapa resumen y los mapas
  regionales del 24, 25 y 26 de junio a las 06 UTC; PDF comprobado de 69 páginas.
- SHA-256 del origen idéntico antes y después:
  `096af2f951404be98c9b095e821c1e3be9e47b12f3fe72b4bc8a7bc8f8de5799`.
