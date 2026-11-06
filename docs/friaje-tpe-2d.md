# Revisión 2D de TPE para ingresos fríos

El diagnóstico genera mapas de temperatura potencial equivalente (TPE) y
viento horizontal en niveles nativos, para contrastar la región de TPE inferior
a 320 K con la animación de Met.3D. El NetCDF estandarizado se abre sólo para
lectura. No se generan nuevos NetCDF ni se interpola o completa información.

## Ejecución

Desde la raíz del proyecto, con el ambiente de `environment.yml`:

```bash
conda run -n metvis3d python scripts/plot_friaje_tpe.py \
  --netcdf data/standardized/ncep-gfs_20261014_00Z.nc
```

La lógica operativa está en `src/visualize/friaje_maps.py`. Los parámetros se
declaran en `config/analysis/friaje_tpe.yaml`: variables, niveles, umbral,
selección temporal, cartografía, colores, separación de flechas y salida.
El dominio se lee de la escena existente `south_america`, conservando el área
de la animación. Los niveles iniciales son 925, 850 y 700 hPa.

Se escribe una lámina PNG de tres paneles por tiempo válido, un PDF con las
mismas láminas y `statistics.csv`, bajo:

```text
outputs/analysis/friaje-tpe/<centro>-<modelo>/<YYYYmmdd_HHZ>/
```

Cada mapa indica corrida, tiempo válido UTC, plazo de pronóstico y nivel.
El CSV registra por tiempo y nivel las celdas válidas, las de TPE inferior al
umbral, las situadas bajo superficie, los datos ausentes y los extremos de TPE.
Los conteos corresponden a celdas del dominio completo, no a áreas equivalentes
ni a un criterio automático de detección de friajes.

Para seleccionar plazos, el YAML admite una lista en `analysis.forecast_hours`
o se puede proporcionar `--forecast-hours 0 24 48`. Los plazos y niveles deben
existir exactamente en el archivo. Para conservar otra colección temporal o
estilo junto a la colección completa, use una copia del YAML con otro
`output.directory` y pásela mediante `--configuration`. El PDF y CSV de una
ejecución sustituyen los del mismo directorio; no se borran PNG anteriores.

## Interpretación de los mapas

- Azul uniforme: TPE **estrictamente inferior** a 320 K.
- Blanco: TPE igual o superior a 320 K.
- Gris: ausencia de temperatura, humedad específica o presión superficial.
- Marrón claro: el nivel queda bajo superficie, según `nivel_hPa * 100 > pressfc`.
- Línea azul: contorno de 320 K, cuando el campo presenta cruces del umbral.
- Flechas: viento horizontal en m/s, con escala fija entre niveles y tiempos.
  Sólo las flechas se submuestrean para facilitar la lectura; el sombreado
  conserva todas las celdas nativas.

La clasificación usa los valores de cada celda. La línea de contorno es una
representación gráfica de la frontera, no un remuestreo del campo. Los tiempos
completamente por debajo o por encima del umbral se conservan aunque no haya
línea de contorno. Los huecos no se convierten en valores de TPE nula ni en
regiones frías; los niveles bajo tierra no intervienen en el cálculo.

Las costas y fronteras nacionales provienen de los shapefiles Natural Earth
1:50 millones distribuidos con Met.3D. Sus rutas, relativas al ambiente Conda,
se configuran en `cartography`; no se descargan mapas durante la ejecución.

## Coherencia con Met.3D

La función `equivalent_potential_temperature_bolton` reproduce las ecuaciones
15 y 43 de Bolton (1980), utilizadas por
[`equivalentPotentialTemperature_K_Bolton` de Met.3D](https://gitlab.com/wxmetvis/met.3d/-/blob/master/src/util/metroutines.cpp).
Convierte humedad específica a razón de mezcla, calcula presión de vapor,
punto de rocío y temperatura de condensación, y finalmente TPE. Para humedad
nula se utiliza el límite seco de la misma ecuación.

Los cálculos intermedios son `float64` y el resultado se convierte a
`float32`, como el campo derivado de Met.3D, antes de aplicar el umbral.
No se sustituye por otra variante de la aproximación de Bolton. La evaluación
meteorológica del valor de 320 K y de su extensión sigue pendiente de revisión
con el usuario.

## Verificación manual del 2026-11-02

- Corrida GFS de 2026-10-14 00 UTC: 41 PNG de 2880×1020 píxeles, un PDF de
  41 páginas y 123 filas de diagnóstico (tres niveles por tiempo), hasta
  2026-10-19 00 UTC. Se inspeccionaron los mapas F+0 y F+48 h, incluidos los
  límites de países, el viento y la máscara andina.
- Se extrajeron y compilaron temporalmente las tres rutinas C++ originales
  `mixingRatio_kgkg`, `dewPointTemperature_K_Bolton` y
  `equivalentPotentialTemperature_K_Bolton` desde `metroutines.cpp`. Se
  contrastaron 28 904 puntos válidos de los tres niveles en F+0, F+60 y F+120 h
  (uno de cada 53 puntos válidos, siguiendo el orden nativo de la matriz).
  Tras convertir el resultado C++ a `float32`, la diferencia máxima fue
  **0 K**, con **0 diferencias** en la clasificación de TPE < 320 K.
  SHA-256 del archivo C++ consultado:
  `de299730e5089cf55524028e28bd009dffb003e20d58c9d129363684c3bfd26d`.
- Caso sintético de dos tiempos sobre una grilla 19×25 con los mismos límites
  horizontales: T de 240 K y 400 K, humedad nula, niveles 925/850/700 hPa,
  presión superficial de 950 hPa con una celda a 800 hPa. Se introdujeron
  huecos separados de T, humedad y presión superficial. Se conservaron ambos
  mapas, las celdas válidas fueron todas frías en el primero y ninguna en el
  segundo; se verificaron los tres huecos y la celda bajo superficie en
  925/850 hPa, pero no en 700 hPa.
- Se comprobó la detención contextual ante un nivel ausente (900 hPa en el
  caso sintético), plazo ausente (F+1 h) y selección temporal vacía.
- En la corrida real, la suma de celdas válidas, ausentes y bajo superficie
  coincide con las 361×481 celdas del dominio en los 123 planos. El SHA-256
  del NetCDF original permanece sin cambios:
  `c55829ced9e3ab59da6328af51b8566f868e1a09be119fab67639dd89290b164`.

Después de generar la colección, pueden repetirse las comprobaciones de
productos con:

```bash
pdfinfo outputs/analysis/friaje-tpe/ncep-gfs/20261014_00Z/friaje_tpe_ncep-gfs_20261014_00Z.pdf
conda run --no-capture-output -n metvis3d python - <<'PY'
import csv
from pathlib import Path

directory = Path('outputs/analysis/friaje-tpe/ncep-gfs/20261014_00Z')
with (directory / 'statistics.csv').open() as source:
    rows = list(csv.DictReader(source))
assert len(list(directory.glob('tpe_*.png'))) == 41
assert len(rows) == 123
assert len({row['valid_time_utc'] for row in rows}) == 41
for row in rows:
    assert (int(row['valid_cells']) + int(row['missing_cells'])
            + int(row['below_surface_cells'])) == 361 * 481
print('41 mapas y 123 planos comprobados.')
PY
```

## Análisis de IFS del 2026-06-20 00 UTC

Se reutilizó la misma configuración, sin modificar niveles, umbral, dominio
ni código de cálculo:

```bash
conda run -n metvis3d python scripts/plot_friaje_tpe.py \
  --netcdf data/standardized/ecmwf-ifs_20260620_00Z.nc
```

Se generaron **65 PNG, un PDF de 65 páginas y 195 filas de estadística**
en `outputs/analysis/friaje-tpe/ecmwf-ifs/20260620_00Z/`. La cobertura llega
hasta el 30 de junio a las 00 UTC, conservando los tiempos nativos cada 3 h
hasta F+144 y cada 6 h desde F+150. La fórmula y las máscaras son las mismas
del análisis anterior.

### Relación con las referencias del análisis de T2m

Se revisaron las mismas celdas próximas a Puerto Maldonado (−12.50°, −69.25°),
Pucallpa (−8.50°, −74.50°) e Iquitos (−3.75°, −73.25°). Los mínimos de TPE
durante los 65 tiempos son:

| Referencia | 925 hPa | 850 hPa | 700 hPa |
|---|---:|---:|---:|
| Puerto Maldonado | 320.41 K | 333.11 K | 324.96 K |
| Pucallpa | 336.60 K | 337.87 K | 327.46 K |
| Iquitos | 341.54 K | 338.64 K | 333.21 K |

**No hay ningún tiempo con TPE < 320 K en esas nueve series.** Puerto
Maldonado se aproxima más al umbral a 925 hPa, el 25/06 a las 12 UTC
(07:00 de Perú), con 320.412841796875 K. El mínimo de cada columna puede
corresponder a una fecha diferente: la tabla no describe un perfil simultáneo.

En los mapas del 24/06 a las 06 UTC, 25/06 a las 12 UTC y 27/06 a las
06 UTC se observa una extensa región bajo el umbral en latitudes más
australes, incluyendo sectores de Bolivia y el Cono Sur. En las tres
referencias amazónicas no aparece el sombreado azul. La máscara marrón de
los Andes identifica niveles bajo superficie y no debe interpretarse como
aire de TPE baja. La presencia de TPE < 320 K en el dominio completo no
constituye, por sí sola, un ingreso de friaje en la Amazonía peruana.

El diagnóstico T2m de esta corrida sí mostró enfriamiento nocturno, con
mayor señal en Puerto Maldonado durante el 23–25 de junio. Ese descenso
no estuvo acompañado de un cruce de 320 K en los niveles y puntos aquí
revisados. Se conservan el umbral acordado y la selección de niveles; no se
clasifica automáticamente el evento ni se descarta un friaje por este único
criterio. Los tres cortes tampoco permiten excluir cruces en otros niveles
nativos del volumen 1000–700 hPa utilizado por la animación.

### Verificación manual del 2026-11-04

- Se releyeron temperatura, humedad específica y presión superficial del
  NetCDF para los 195 planos. Los conteos de celdas válidas, frías, ausentes
  y bajo superficie, así como los mínimos y máximos de TPE, coinciden
  exactamente con `statistics.csv`.
- En cada plano, las categorías suman las 361×481 celdas del dominio. No hay
  datos ausentes sobre superficie en estos cortes; las celdas bajo tierra
  siguen excluidas. Sus conteos varían con la presión superficial: 5639–6322
  a 925 hPa, 3081–3223 a 850 hPa y 1183–1217 a 700 hPa.
- Los mínimos y cantidades de cruces de las nueve series coinciden
  exactamente con `reference_tpe_comparison.csv` del diagnóstico T2m.
- Se comprobaron 65 PNG y un PDF de 65 páginas y se inspeccionaron los tres
  mapas indicados, con costas, fronteras, viento y máscara andina.
- SHA-256 del origen idéntico antes y después:
  `096af2f951404be98c9b095e821c1e3be9e47b12f3fe72b4bc8a7bc8f8de5799`.

## Análisis de GFS del 2026-06-20 00 UTC

```bash
conda run -n metvis3d python scripts/plot_friaje_tpe.py \
  --netcdf data/standardized/ncep-gfs_20260620_00Z.nc
```

Se reutilizaron los niveles 925/850/700 hPa, el umbral estricto de 320 K,
la escena `south_america` y el cálculo de Bolton. El archivo cubre los mismos
diez días que IFS, hasta el 30/06 a las 00 UTC, pero conserva salidas cada
3 h durante todo el período: **81 PNG, PDF de 81 páginas y 243 filas de
estadística**, en `outputs/analysis/friaje-tpe/ncep-gfs/20260620_00Z/`.

### Referencias amazónicas

Las celdas nativas utilizadas son las mismas del análisis IFS. Los mínimos
durante los 81 tiempos disponibles son:

| Referencia | 925 hPa | 850 hPa | 700 hPa |
|---|---:|---:|---:|
| Puerto Maldonado | 319.00 K | 330.85 K | 327.74 K |
| Pucallpa | 338.18 K | 337.14 K | 328.39 K |
| Iquitos | 340.60 K | 338.05 K | 331.36 K |

**GFS sí cruza el umbral en Puerto Maldonado a 925 hPa**, en dos salidas
consecutivas del 26 de junio:

| Tiempo UTC | Hora de Perú | Plazo | TPE |
|---|---|---:|---:|
| 26/06 12:00 | 26/06 07:00 | F+156 h | 319.8005 K |
| 26/06 15:00 | 26/06 10:00 | F+159 h | 319.0041 K |

Las salidas previas y posteriores próximas están por encima del umbral:
324.47 K a las 09 UTC y 326.91 K a las 18 UTC. Se identifican dos muestras
bajo el umbral, sin interpolar los instantes de entrada y salida ni atribuir
una duración continua exacta. No hay cruces en esa referencia a 850 o
700 hPa, ni en Pucallpa o Iquitos a ninguno de los tres niveles revisados.

El CSV complementario `reference_tpe_series.csv`, elaborado durante la
revisión, conserva las 729 muestras de las tres referencias y tres niveles,
con fechas UTC, coordenadas nativas y disponibilidad de la misma hora en IFS.
Los mínimos de la tabla pueden corresponder a fechas diferentes.

### Comparación con IFS

La diferencia no se debe únicamente al calendario de salidas. Restringiendo
GFS a las **65 horas presentes también en IFS**, Puerto Maldonado mantiene
un cruce a 925 hPa el 26/06 a las 12 UTC, con mínimo de 319.80 K. IFS no
cruza en esa serie y su mínimo durante esas 65 horas es 320.41 K, ocurrido
el 25/06 a las 12 UTC. Se comparan mínimos del período común; no son valores
simultáneos entre modelos. El plazo GFS F+159 no está disponible en IFS y
no se interpola.

La señal del umbral en GFS alcanza la celda próxima a Puerto Maldonado,
pero permanece limitada a 925 hPa y a dos salidas en las referencias
evaluadas. Esto no demuestra un ingreso generalizado hacia la selva central
y norte ni clasifica por sí solo el evento. No se ha efectuado en esta
ejecución un nuevo diagnóstico de T2m, y estos tres cortes no representan
todos los niveles nativos del volumen de la animación.

### Verificación manual del caso GFS de junio, 2026-11-04

- Una relectura independiente confirmó exactamente los conteos, máscaras,
  mínimos y máximos de los 243 planos frente a `statistics.csv`.
- En cada plano, las categorías suman las 361×481 celdas. No hay datos
  ausentes sobre superficie; los conteos bajo tierra varían entre 5828–6334
  a 925 hPa, 3056–3195 a 850 hPa y 1163–1191 a 700 hPa.
- Se comprobaron 81 PNG, PDF de 81 páginas y 729 muestras de referencia.
  Se inspeccionaron los mapas de las dos salidas con cruce en Puerto Maldonado.
- SHA-256 idéntico antes y después:
  `f31a226d196f916ce061c51a9c912274784310db1dc4b2277a8d4c6cdbe72fa0`.
