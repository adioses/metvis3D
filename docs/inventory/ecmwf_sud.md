# Inventario GRIB2 — ECMWF_SUD

Este reporte describe una fuente en exploración. No valida su procedencia ni define aún el estándar NetCDF.

Generado: 2026-09-16T17:30:20.922346+00:00

## WGRIB2

- Comando de inventario: `-names ncep -VT -var -lev0 -ftime -s`.
- wgrib2 3.8.0; default WMO names: NCEP.
- Etiquetas NCEP observadas: CAPE, DLWRF, DPT, DSLM, DSWRF, EASTTSS, ESURFWVEL, GP, GUST, HGT, ICETK, LAND, NLWRF, NRTHTSS, NSURFWVEL, NSWRF, PRES, PTYPE, RELD, RELV, RH, SDEN, SDSGSO, SKINT, SOILTMP, SPFH, SSGSO, TCIWV, TCWAT, TMP, TPRATE, UGRD, VGRD, VSOILM, VVEL, asn, mtsfr, ro, sd, tcc, tprate.

## Archivos y plazos

- Archivos: 65
- Mensajes GRIB: 11313; por archivo: 174–177.
- Cobertura: 0–240 h; 65 plazos presentes.
- Plazos faltantes en una secuencia de 3 h: 147, 153, 159, 165, 171, 177, 183, 189, 195, 201, 207, 213, 219, 225, 231, 237

## Procedencia declarada en GRIB

| Centro | Descripción | Subcentro | Tabla maestra | Tabla local | Estado | Tipo | Proceso | Identificador | Mensajes |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| ecmf | European Centre for Medium-Range Weather Forecasts | 0 | 32 | 0 | 0 | fc | 2 | 161 | 10923 |
| ecmf | European Centre for Medium-Range Weather Forecasts | 0 | 32 | 1 | 0 | fc | 2 | 161 | 390 |

## Mallas declaradas en GRIB

| Plantilla | Ni | Nj | Δlon | Δlat | Latitud inicial | Longitud inicial | Latitud final | Longitud final | Escaneo | Mensajes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 761 | 401 | 0.25 | 0.25 | -70.0 | 170.0 | 30.0 | 0.0 | 64 | 11313 |

## Catálogo meteorológico PyGRIB

Cada fila agrupa mensajes con la misma identidad física y de producto. Los plazos individuales se resumen para mantener el informe revisable.

| Disciplina-categoría-parámetro | Nombre corto | Nombre | Unidad | Tipo de nivel | Proceso temporal | PDT | Niveles | Cobertura temporal | Mensajes |
|---|---|---|---|---|---|---:|---|---|---:|
| 0-0-0 | 2t | 2 metre temperature | K | heightAboveGround | instant | 0 | 2 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-0-0 | mn2t3 | Minimum temperature at 2 metres in the last 3 hours | K | heightAboveGround | min | 8 | 2 | 48 intervalos; inicio 0–141 h; fin 3–144 h | 49 |
| 0-0-0 | mn2t6 | Minimum temperature at 2 metres in the last 6 hours | K | heightAboveGround | min | 8 | 2 | 16 intervalos; inicio 144–234 h; fin 150–240 h | 16 |
| 0-0-0 | mx2t3 | Maximum temperature at 2 metres in the last 3 hours | K | heightAboveGround | max | 8 | 2 | 48 intervalos; inicio 0–141 h; fin 3–144 h | 49 |
| 0-0-0 | mx2t6 | Maximum temperature at 2 metres in the last 6 hours | K | heightAboveGround | max | 8 | 2 | 16 intervalos; inicio 144–234 h; fin 150–240 h | 16 |
| 0-0-0 | t | Temperature | K | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-0-17 | skt | Skin temperature | K | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-0-6 | 2d | 2 metre dewpoint temperature | K | heightAboveGround | instant | 0 | 2 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-0 | q | Specific humidity | kg kg**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-1-1 | r | Relative humidity | % | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-1-19 | ptype | Precipitation type | (Code table 4.201) | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-193 | tp | Total precipitation | m | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-1-198 | sf | Snowfall | m of water equivalent | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-1-254 | sd | Snow depth | m of water equivalent | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-51 | tcw | Total column water | kg m**-2 | entireAtmosphere | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-52 | tprate | Total precipitation rate | kg m**-2 s**-1 | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-61 | rsn | Snow density | kg m**-3 | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-1-64 | tcwv | Total column vertically-integrated water vapour | kg m**-2 | entireAtmosphere | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-19-192 | asn | Snow albedo | (0 - 1) | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-2-12 | vo | Vorticity (relative) | s**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-2-13 | d | Divergence | s**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-2-2 | 100u | 100 metre U wind component | m s**-1 | heightAboveGround | instant | 0 | 100 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-2-2 | 10u | 10 metre U wind component | m s**-1 | heightAboveGround | instant | 0 | 10 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-2-2 | u | U component of wind | m s**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-2-22 | 10fg | Maximum 10 metre wind gust since previous post-processing | m s**-1 | heightAboveGround | max | 8 | 10 | 47 intervalos; inicio 0–234 h; fin 0–240 h | 47 |
| 0-2-22 | 10fg3 | Maximum 10 metre wind gust in the last 3 hours | m s**-1 | heightAboveGround | max | 8 | 10 | 18 intervalos; inicio 90–141 h; fin 93–144 h | 18 |
| 0-2-3 | 100v | 100 metre V wind component | m s**-1 | heightAboveGround | instant | 0 | 100 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-2-3 | 10v | 10 metre V wind component | m s**-1 | heightAboveGround | instant | 0 | 10 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-2-3 | v | V component of wind | m s**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-2-62 | ewss | Time-integrated eastward turbulent surface stress | N m**-2 s | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-2-63 | nsss | Time-integrated northward turbulent surface stress | N m**-2 s | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-2-8 | w | Vertical velocity | Pa s**-1 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-3-0 | msl | Mean sea level pressure | Pa | meanSea | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-3-0 | sp | Surface pressure | Pa | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-3-20 | sdor | Standard deviation of sub-gridscale orography | m | surface | instant | 0 | 0 | 1 intervalos; inicio 0–0 h; fin 0–0 h | 1 |
| 0-3-22 | slor | Slope of sub-gridscale orography | Numeric | surface | instant | 0 | 0 | 1 intervalos; inicio 0–0 h; fin 0–0 h | 1 |
| 0-3-4 | z | Geopotential | m**2 s**-2 | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-3-4 | z | Geopotential | m**2 s**-2 | surface | instant | 0 | 0 | 1 intervalos; inicio 0–0 h; fin 0–0 h | 1 |
| 0-3-5 | gh | Geopotential height | gpm | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 845 |
| 0-4-7 | ssrd | Surface short-wave (solar) radiation downwards | J m**-2 | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-4-9 | ssr | Surface net short-wave (solar) radiation | J m**-2 | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-5-3 | strd | Surface long-wave (thermal) radiation downwards | J m**-2 | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-5-5 | str | Surface net long-wave (thermal) radiation | J m**-2 | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-5-5 | ttr | Top net long-wave (thermal) radiation | J m**-2 | nominalTop | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 0-6-192 | tcc | Total cloud cover | (0 - 1) | entireAtmosphere | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 0-7-6 | mucape | Most-unstable CAPE | J kg**-1 | mostUnstableParcel | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 10-2-1 | sithick | Sea ice thickness | m | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 10-3-1 | zos | Sea surface height | m | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 10-3-14 | sve | Eastward surface sea water velocity | m s**-1 | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 10-3-15 | svn | Northward surface sea water velocity | m s**-1 | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 2-0-0 | lsm | Land-sea mask | (0 - 1) | surface | instant | 0 | 0 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 65 |
| 2-0-201 | ro | Runoff | m | surface | accum | 8 | 0 | 65 intervalos; inicio 0–0 h; fin 0–240 h | 65 |
| 2-0-25 | vsw | Volumetric soil moisture | m**3 m**-3 | soilLayer | instant | 0 | 1, 2, 3, 4 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 260 |
| 2-3-18 | sot | Soil temperature | K | soilLayer | instant | 0 | 1, 2, 3, 4 | 65 intervalos; inicio 0–240 h; fin 0–240 h | 260 |
