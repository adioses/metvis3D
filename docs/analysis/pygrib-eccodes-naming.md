# Cómo PyGRIB/ecCodes resuelve los nombres de parámetros

## Resultado principal

PyGRIB no impone una convención meteorológica propia sobre los GRIB2. Expone las claves de ecCodes, entre ellas `name`, `shortName` e identificador de parámetro. Por ello, el mismo `shortName` no demuestra que dos mensajes de fuentes distintas sean físicamente equivalentes.

La documentación de ecCodes indica expresamente que `shortName` y `name` no son únicos; distintas definiciones de parámetro pueden compartirlos. El identificador de parámetro es la clave de mayor nivel que ecCodes resuelve a partir de las propiedades del mensaje.

## Evidencia del entorno analizado

PyGRIB usa las definiciones vinculadas a ecCodes; `pygrib.get_definitions_path()` devolvió `None` y `codes_info -d` identificó la ruta instalada de definiciones ecCodes.

En las definiciones locales de ECMWF, la entrada para precipitación total asigna `shortName=tp` cuando coinciden, entre otras, estas condiciones: tabla local 1, disciplina 0, categoría 1, parámetro 193, superficie y procesamiento estadístico de acumulación. Es una definición local de ECMWF distinta de la identidad GFS `0-1-8`, aunque ambos mensajes terminan mostrando `shortName=tp`.

De forma equivalente, la definición local de ECMWF asigna `shortName=tcc` al código `0-6-192`; GFS usa `0-6-1` y ecCodes también lo presenta como `tcc`.

La base de parámetros ECMWF identifica el parámetro local `0-1-193` como precipitación total acumulada (`tp`, identificador 228, unidad `m`) cuando usa procesamiento estadístico de acumulación. Ese código está en el rango reservado para uso local de la tabla GRIB2 de humedad; su significado no puede deducirse de la tabla WMO sin conocer el centro y la tabla local. El parámetro WMO `0-1-52` sí es tasa de precipitación total, con unidad `kg m**-2 s**-1`, y corresponde al segundo campo ECMWF observado como `TPRATE`.

| Caso | GFS | ECMWF | Lectura correcta |
|---|---|---|---|
| Precipitación | `0-1-8`, identificador 228228, `tp` | `0-1-193`, identificador 228, `tp` | El nombre compartido procede de definiciones ecCodes diferentes; no certifica equivalencia física. |
| Cobertura nubosa total | `0-6-1`, identificador 228164, `tcc`, porcentaje | `0-6-192`, identificador 164, `tcc`, fracción | El nombre compartido oculta una unidad distinta y códigos distintos. |

## Implicación para la estandarización

La selección futura debe conservar como identidad la combinación de centro, tablas, disciplina, categoría, parámetro, nivel, proceso e intervalo temporal. El nombre NCEP de WGRIB2 será la referencia de presentación y de la futura decisión de nomenclatura, pero los nombres PyGRIB/ecCodes se usarán como información de lectura, no como clave única de equivalencia.

La siguiente decisión científica será revisar, caso por caso, si los campos con nombres WGRIB2 distintos describen la misma cantidad bajo una transformación definida. Sólo entonces podrá declararse una equivalencia hacia un nombre NCEP elegido; no debe derivarse automáticamente de `shortName`.

## Fuentes consultadas

- [API oficial de PyGRIB](https://jswhit.github.io/pygrib/api.html): los atributos de cada mensaje corresponden a claves GRIB, incluidos nombre, nombre corto e identificador de parámetro.
- [Claves de parámetros de ecCodes](https://codes.ecmwf.int/grib/format/edition-independent/7/): especifica que `shortName` y `name` no son únicos.
- [Parámetros locales de ecCodes](https://confluence.ecmwf.int/spaces/UDOC/pages/435820714/Creating%2Byour%2Bown%2Blocal%2Bparameters%2B-%2BecCodes%2BGRIB%2BFAQ): explica que las definiciones de un centro resuelven nombre, nombre corto, unidad e identificador de parámetro a partir de claves GRIB.
- [Base oficial ECMWF: parámetro 228](https://codes.ecmwf.int/grib/param-db/228): documenta `0-1-193` como precipitación total local en metros.
- [Registro WMO: código `0-1-52`](https://codes.wmo.int/grib2/codeflag/4.2/_0-1-52): documenta la tasa de precipitación total en `kg m**-2 s**-1`.
