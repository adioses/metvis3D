# Inventario GRIB2 — GFS_COM

Este reporte describe una fuente en exploración. No valida su procedencia ni define aún el estándar NetCDF.

Generado: 2026-09-16T17:27:44.528323+00:00

## WGRIB2

- Comando de inventario: `-names ncep -VT -var -lev0 -ftime -s`.
- wgrib2 3.8.0; default WMO names: NCEP.
- Etiquetas NCEP observadas: APCP, CAPE, DPT, HCDC, HGT, HPBL, ICEC, LAND, LCDC, LFTX, MCDC, MSLET, PRES, PRMSL, PWAT, RH, SNOD, SOILW, SPFH, SUNSD, TCDC, TMP, TSOIL, UGRD, VGRD, VVEL, WEASD.

## Archivos y plazos

- Archivos: 129
- Mensajes GRIB: 32631; por archivo: 247–253.
- Cobertura: 0–384 h; 129 plazos presentes.
- Plazos faltantes en una secuencia de 3 h: ninguno

## Procedencia declarada en GRIB

| Centro | Descripción | Subcentro | Tabla maestra | Tabla local | Estado | Tipo | Proceso | Identificador | Mensajes |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| kwbc | US National Weather Service - NCEP | 0 | 2 | 1 | 0 | fc | 2 | 81 | 247 |
| kwbc | US National Weather Service - NCEP | 0 | 2 | 1 | 0 | fc | 2 | 96 | 32384 |

## Mallas declaradas en GRIB

| Plantilla | Ni | Nj | Δlon | Δlat | Latitud inicial | Longitud inicial | Latitud final | Longitud final | Escaneo | Mensajes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 553 | 401 | 0.25 | 0.25 | -70.0 | 216.0 | 30.0 | 354.0 | 64 | 32631 |

## Catálogo meteorológico PyGRIB

Cada fila agrupa mensajes con la misma identidad física y de producto. Los plazos individuales se resumen para mantener el informe revisable.

| Disciplina-categoría-parámetro | Nombre corto | Nombre | Unidad | Tipo de nivel | Proceso temporal | PDT | Niveles | Cobertura temporal | Mensajes |
|---|---|---|---|---|---|---:|---|---|---:|
| 0-0-0 | 2t | 2 metre temperature | K | heightAboveGround | instant | 0 | 2 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-0-0 | t | Temperature | K | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-0-0 | t | Temperature | K | maxWind | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-0-0 | t | Temperature | K | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-0-0 | t | Temperature | K | tropopause | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-0-6 | 2d | 2 metre dewpoint temperature | K | heightAboveGround | instant | 0 | 2 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-0 | 2sh | 2 metre specific humidity | kg kg**-1 | heightAboveGround | instant | 0 | 2 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-0 | q | Specific humidity | kg kg**-1 | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-1-1 | 2r | 2 metre relative humidity | % | heightAboveGround | instant | 0 | 2 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-1 | r | Relative humidity | % | atmosphereSingleLayer | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-1 | r | Relative humidity | % | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-1-11 | sde | Snow depth | m | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-13 | sdwe | Water equivalent of accumulated snow depth (deprecated) | kg m**-2 | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-3 | pwat | Precipitable water | kg m**-2 | atmosphereSingleLayer | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-1-8 | tp | Total Precipitation | kg m**-2 | surface | accum | 8 | 0 | 254 intervalos; inicio 0–378 h; fin 3–384 h | 256 |
| 0-2-2 | 10u | 10 metre U wind component | m s**-1 | heightAboveGround | instant | 0 | 10 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-2 | u | U component of wind | m s**-1 | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-2-2 | u | U component of wind | m s**-1 | maxWind | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-2 | u | U component of wind | m s**-1 | tropopause | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-3 | 10v | 10 metre V wind component | m s**-1 | heightAboveGround | instant | 0 | 10 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-3 | v | V component of wind | m s**-1 | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-2-3 | v | V component of wind | m s**-1 | maxWind | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-3 | v | V component of wind | m s**-1 | tropopause | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-2-8 | w | Vertical velocity | Pa s**-1 | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-3-0 | pres | Pressure | Pa | maxWind | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-0 | sp | Surface pressure | Pa | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-0 | trpp | Tropopause pressure | Pa | tropopause | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-1 | prmsl | Pressure reduced to MSL | Pa | meanSea | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-192 | mslet | MSLP (Eta model reduction) | Pa | meanSea | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-196 | unknown | unknown | unknown | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-5 | gh | Geopotential height | gpm | isobaricInhPa | instant | 0 | 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 3354 |
| 0-3-5 | gh | Geopotential height | gpm | maxWind | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-5 | gh | Geopotential height | gpm | tropopause | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-3-5 | orog | Orography | m | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-6-1 | tcc | Total Cloud Cover | % | atmosphere | avg | 8 | 0 | 128 intervalos; inicio 0–378 h; fin 3–384 h | 128 |
| 0-6-1 | tcc | Total Cloud Cover | % | atmosphere | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-6-1 | tcc | Total Cloud Cover | % | isobaricInhPa | instant | 0 | 50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 2838 |
| 0-6-201 | SUNSD | Sunshine Duration | s | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-6-3 | avg_lcc | Time-mean low cloud cover | % | lowCloudLayer | avg | 8 | 0 | 128 intervalos; inicio 0–378 h; fin 3–384 h | 128 |
| 0-6-3 | lcc | Low cloud cover | % | lowCloudLayer | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-6-4 | avg_mcc | Time-mean medium cloud cover | % | middleCloudLayer | avg | 8 | 0 | 128 intervalos; inicio 0–378 h; fin 3–384 h | 128 |
| 0-6-4 | mcc | Medium cloud cover | % | middleCloudLayer | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-6-5 | avg_hcc | Time-mean high cloud cover | % | highCloudLayer | avg | 8 | 0 | 128 intervalos; inicio 0–378 h; fin 3–384 h | 128 |
| 0-6-5 | hcc | High cloud cover | % | highCloudLayer | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-7-192 | lftx | Surface lifted index | K | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 0-7-6 | cape | Convective available potential energy | J kg**-1 | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 10-2-0 | ci | Sea ice area fraction | (0 - 1) | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 2-0-0 | lsm | Land-sea mask | (0 - 1) | surface | instant | 0 | 0 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 129 |
| 2-0-192 | soilw | Volumetric soil moisture content | Proportion | depthBelowLandLayer | instant | 0 | 0, 1 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 516 |
| 2-0-2 | st | Soil temperature | K | depthBelowLandLayer | instant | 0 | 0, 1 | 129 intervalos; inicio 0–384 h; fin 0–384 h | 516 |
