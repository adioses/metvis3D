# Contraste de variables GRIB2: WGRIB2 y PyGRIB

## Alcance

Se revisaron los plazos 0, 3 y 6 h de GFS/COM y ECMWF global. En ECMWF/SUD se confirmó a 3 h que los metadatos de precipitación y cobertura nubosa coinciden con el archivo global. WGRIB2 fue el inventario primario, con `-names ncep -VT -var -lev0 -ftime -s`; PyGRIB se usó sólo para contrastar claves y nombres que resuelve ecCodes.

Los mensajes se compararon por propiedades meteorológicas: parámetro, nivel, proceso e intervalo temporal. No se seleccionaron por su posición en el archivo.

## Variables cuya identidad coincide en ambas fuentes

En 500 hPa y 3 h, temperatura, humedad específica, humedad relativa, viento U, viento V y velocidad vertical tienen el mismo código disciplina-categoría-parámetro, el mismo identificador de parámetro de ecCodes, unidad y nombre PyGRIB. WGRIB2 también entrega las mismas etiquetas NCEP: `TMP`, `SPFH`, `RH`, `UGRD`, `VGRD` y `VVEL`.

La altura geopotencial coincide como `HGT` / `gh`, código `0-3-5`, identificador de parámetro 156 y unidad `gpm`. ECMWF entrega además geopotencial como `GP` / `z`, código `0-3-4`, identificador 129 y unidad `m**2 s**-2`. No son el mismo campo ni deben unificarse sin una decisión física y una conversión explícita.

## Casos donde WGRIB2 y PyGRIB no expresan la misma distinción

| Campo candidato | GFS: WGRIB2 / identidad / PyGRIB | ECMWF: WGRIB2 / identidad / PyGRIB | Diferencia que requiere decisión |
|---|---|---|---|
| Precipitación | `APCP`; `0-1-8`; `tp`, identificador 228228, `kg m**-2` | `tprate`; `0-1-193`; `tp`, identificador 228, `m` | Código, etiqueta WGRIB2, identificador y unidad distintos. |
| Cobertura nubosa total | `TCDC`; `0-6-1`; `tcc`, identificador 228164, `%` | `tcc`; `0-6-192`; `tcc`, identificador 164, fracción `0–1` | Código y unidad distintos, aunque PyGRIB usa `tcc` en ambos. |

En GFS, la cobertura nubosa total aparece como producto instantáneo a 3 h y también como promedio 0–3 h. En el ECMWF examinado aparece como producto instantáneo a 3 h. Un nombre común no basta para escoger uno de esos productos. La lectura completa del campo instantáneo a 3 h confirmó que GFS usa 0–100 (mínimo 0, máximo 100, media 63.06) y ECMWF usa 0–1 (mínimo 0, máximo 1, media 0.648). Por tanto, son escalas de porcentaje y fracción, respectivamente; la conversión entre ambas es multiplicar o dividir por 100, una vez decidida la equivalencia física del producto.

## Precipitación: detalle temporal y ambigüedad adicional

| Fuente y plazo | Lo que declara WGRIB2 | Lo que declara PyGRIB |
|---|---|---|
| GFS, 0 h | No hay `APCP` | No hay `tp` acumulada. |
| GFS, 3 h | Dos mensajes `APCP`, superficie, acumulado 0–3 h, `kg/m^2` | Dos mensajes `tp`, `0-1-8`, acumulado 0–3 h. Sus propiedades revisadas y estadísticas WGRIB2 son iguales. |
| GFS, 6 h | Dos mensajes `APCP`, superficie, acumulado 0–6 h | Dos mensajes `tp`, `0-1-8`, acumulado 0–6 h. |
| ECMWF, 0 h | `tprate`, acumulado 0–0, valor nulo | `tp`, `0-1-193`, acumulado 0, unidad `m`. |
| ECMWF, 3 y 6 h | `tprate`, acumulado desde 0; WGRIB2 lo describe como tasa media de precipitación total en `m/s` | `tp`, `0-1-193`, acumulado 0–3 o 0–6, unidad `m`. |

La duplicación GFS es un caso previsto por FV3-GFS: el archivo conserva acumulados de estilo nuevo y estilo antiguo para compatibilidad. La documentación de WGRIB2 indica que esos acumulados pueden tener el mismo nombre y que `-unmerge_fcst` permite obtener la serie temporal correcta; no se debe resolver escogiendo por posición. En 0–3 y 0–6 h ambos productos coinciden, por eso aparecen duplicados en esta muestra. [Documentación oficial de `-unmerge_fcst`](https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/unmerge_fcst.html).

ECMWF también contiene, a 3 h, un segundo campo distinto: `TPRATE` en WGRIB2, código `0-1-52`, identificador 260048, `shortName=tprate`, tasa instantánea en `kg m**-2 s**-1`. El registro oficial WMO identifica `0-1-52` como tasa de precipitación total. Por tanto, `tprate` y `TPRATE` no pueden identificarse sólo ignorando mayúsculas/minúsculas.

La base oficial de parámetros de ECMWF identifica específicamente `0-1-193`, con tabla local 1 y procesamiento de acumulación, como parámetro 228: precipitación total, `tp`, en metros. En consecuencia, la etiqueta y unidad de tasa que WGRIB2 muestra como `tprate` para ese mensaje son inconsistentes con la definición ecCodes/ECMWF y con sus valores (media de 0.000299813 en el archivo de 3 h, coherente con metros acumulados y no con metros por segundo). Esto debe tratarse como una discrepancia de nomenclatura/interpretación de WGRIB2 para ese parámetro local, no como prueba de que el campo ECMWF sea una tasa.

## Conclusiones de esta muestra

1. La salida de WGRIB2 no es por sí sola una nomenclatura común completa entre estas dos fuentes: difiere en precipitación y nubosidad.
2. El `shortName` de PyGRIB tampoco es una identidad suficiente entre fuentes: `tp` y `tcc` ocultan diferencias observables de código, unidad y producto temporal.
3. No se propone aún equivalencia entre `APCP` y el campo ECMWF `0-1-193`. Primero debe decidirse si representan la misma magnitud y cómo se normalizará la unidad `kg m**-2` frente a `m`.
4. La duplicación de `APCP` de GFS está documentada y tiene un tratamiento WGRIB2: conservar la lógica de `-unmerge_fcst`, no seleccionar uno de los mensajes por posición.
