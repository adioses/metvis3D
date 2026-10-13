# Prueba estática: topografía y corriente de chorro

La prueba combina el terreno sudamericano y la envolvente de rapidez de viento
de 30 m/s. No representa tres superficies anidadas ni planos de presión de
referencia: muestra una sola isosuperficie, que es la frontera del volumen donde
`wind_speed > 30 m/s`.

## Datos y geometría

- Fuente: `ncep-gfs_20260903_00Z.nc`, primer tiempo disponible.
- Variables: `ugrdprs`, `vgrdprs` y `hgtprs`.
- Niveles: 500 a 50 hPa, inclusive.
- Rapidez: `hypot(ugrdprs, vgrdprs)`.
- Coordenadas: Lambert Conformal Conic de la escena sudamericana.
- Coordenada vertical: `hgtprs × 18`.
- Muestreo horizontal: cada dos puntos.

## Preparación

Primero debe existir el terreno actualizado con la misma exageración vertical.
Luego ejecute:

```bash
python scripts/prepare_static_scene.py --overwrite
python scripts/prepare_jet_scene.py
```

Para reemplazar una preparación del chorro existente, use:

```bash
python scripts/prepare_jet_scene.py --overwrite
```

## Visualización en ParaView

En `View > Python Shell > Run Script`, ejecute:

```text
paraview/templates/render_terrain_and_jet.py
```

La superficie naranja es el límite de rapidez de 30 m/s. Su interior es el
volumen atmosférico que supera ese umbral; no se rellena mediante transparencia
en esta primera prueba.
