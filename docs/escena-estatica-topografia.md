# Escena estática de topografía: Sudamérica

La primera escena de contexto geográfico usa el GeoTIFF continuo
`assets/dem/gmted2010/geotiff/gmted2010_mn30_global.tif`. El DEM fuente no se
modifica; la preparación genera productos descartables para ParaView.

## Configuración aprobada para la primera prueba

- Dominio geográfico: `west=-130`, `south=-56`, `east=-10`, `north=30`.
- Proyección: Lambert Conformal Conic centrada en Sudamérica.
- Malla de renderizado: 10 km.
- Exageración vertical: 12 veces.
- Océano: plano a 0 m, coloreado en azul.
- Terreno: paleta hipsométrica configurable en
  `config/scenes/south_america.yaml`.

## Preparación

Actualice el entorno Conda después de incorporar GDAL y ejecute:

```bash
conda env update -f environment.yml --prune
conda activate metvis3d
python scripts/prepare_static_scene.py
```

El proceso escribe los siguientes productos no versionados:

```text
paraview/render_data/static/south_america/
  terrain_lcc_10km.tif
  terrain.vts
  terrain_metadata.json
```

## Visualización en ParaView

1. Abra ParaView y cree una vista `Render View`.
2. Abra `View > Python Shell`.
3. Pulse `Run Script` y seleccione
   `paraview/templates/render_static_terrain.py`.

La plantilla abre el VTS, aplica la paleta hipsométrica de la configuración y
encuadra el relieve con una cámara oblicua. No genera aún imágenes ni video.

Si se modifica la configuración y se comprobó que se desea reemplazar la
escena generada, ejecute `python scripts/prepare_static_scene.py --overwrite`.
