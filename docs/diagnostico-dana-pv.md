# Diagnóstico exploratorio de PV para una DANA

Este diagnóstico es previo a la visualización 3D: permite elegir un plazo, un
dominio y una isosuperficie fundamentados en el campo meteorológico. Calcula la
vorticidad potencial (PV) baroclínica con temperatura y viento del NetCDF en
niveles de presión; no reescribe ni interpola el archivo de entrada.

La configuración versionada es
`config/analysis/dana_pv_diagnostic.yaml`. Se ejecuta desde la raíz:

```bash
conda env update -n metvis3d -f environment.yml
conda run -n metvis3d python scripts/analyze_dana_pv.py
```

Los resultados no versionados se guardan bajo `outputs/dana-pv-diagnostic/`:

- `pv_statistics.csv`: rango y percentiles de PV por plazo y nivel, además del
  número de puntos con umbrales negativos.
- `pv_350hpa_all_times.png`, `pv_300hpa_all_times.png`,
  `pv_250hpa_all_times.png` y `pv_200hpa_all_times.png`: evolución temporal
  con PV coloreada, los contornos de PV elegidos, altura geopotencial a 500 hPa
  y viento a 300 hPa.
- `pv_vertical_f*.png`: comparación de 500 a 150 hPa para los plazos elegidos.

La configuración inicial emplea una proyección Plate Carrée de Cartopy y no
utiliza Lambert ni exageración vertical. La conversión de longitudes de
`0..360` a `-180..180` se hace sólo para dibujar: los cálculos usan la malla
nativa del NetCDF.

## Criterio para identificar la DANA

En el hemisferio sur, una intrusión ciclónica de PV suele tener signo negativo.
No debe invertirse el signo para que parezca un caso del hemisferio norte. Se
debe buscar una anomalía compacta o contornos cerrados de PV negativa, coherente
con una baja cerrada de geopotencial a 500 hPa y con el viento de niveles altos.
Su rasgo vertical útil es que la anomalía se prolongue desde 250--200 hPa hacia
300--350 hPa.

Un contorno de -5 PVU aplicado a todo el intervalo 500--50 hPa puede describir
una gran parte de la estratosfera o de la tropopausa, no necesariamente la
DANA. Por eso, antes de cargar una isosuperficie 3D conviene escoger el plazo
con las figuras y recortar la caja horizontal al entorno de la anomalía. El
umbral 3D se decidirá entonces con los contornos que resulten cerrados; no hay
garantía física de que una DANA deba parecer una esfera perfecta.
