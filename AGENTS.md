# Guía de trabajo del proyecto

Estas reglas aplican a quienes desarrollen o usen asistentes de programación
en `metvis3d`.

## Propósito

Preparar datos meteorológicos de modelos numéricos, generar visualizaciones
3D reproducibles y publicar sus productos. Las cuatro obligaciones del
proyecto son: estandarización de datos, visualización/animación, plataforma
web piloto e integración/documentación del flujo.

## Acuerdos vigentes sobre datos

- `data/raw` es una fuente de solo lectura. No modificar, renombrar ni mover
  GRIB originales desde procesos del proyecto.
- Cada modelo y corrida produce un único NetCDF final, no NetCDF parciales por
  variable ni por tiempo.
- Las dimensiones canónicas son `time`, `lev`, `latitude` y `longitude`.
  Superficie usa `(time, latitude, longitude)` y presión usa
  `(time, lev, latitude, longitude)`.
- Conservar los niveles verticales nativos de cada modelo.
- Las transformaciones adicionales, la convención definitiva de longitudes y
  las comprobaciones del conversor se definirán al diseñar el código de
  estandarización.

El contrato detallado se mantiene en `docs/data-standard.md`.

## Herramientas y ejecución

- Desarrollo local: Docker Compose y la imagen Micromamba definida en `Dockerfile`.
- Despliegue HPC: el mismo `environment.yml` mediante Miniconda/Conda, sin depender de Docker.
- Jupyter Lab sirve para explorar o ajustar parámetros. La lógica operativa
  debe residir en `src/` y configuraciones YAML versionables, no solamente en
  notebooks.
- ParaView y Blender consumen plantillas y parámetros configurables. Sus datos
  temporales pertenecen a `paraview/render_data` o `paraview/render_cache`.

## Estilo de código científico

- Usar nombres en inglés asociados al dominio meteorológico y al flujo de
  datos: `grib_files`, `forecast_hours`, `pressure_levels`, `temperature`,
  `wind_u`, `wind_v` y `netcdf_output`.
- Usar comentarios, docstrings, mensajes de avance y errores en español.
- Evitar nombres o conceptos internos de arquitectura de software que no
  aporten al proceso científico, como `handler`, `payload`, `repository`,
  `factory`, `cache`, `persistence` o `atomic`.
- Cada proceso principal debe tener una función que muestre el flujo completo
  de forma lineal y legible, por ejemplo `standardize_model_run(...)`.
- Dentro de la función principal, separar visualmente las etapas relevantes:
  lectura de configuración, revisión de archivos, lectura GRIB, selección de
  variables, construcción de coordenadas, escritura NetCDF y resultado final.
- Crear funciones auxiliares sólo cuando representen una operación científica o
  técnica con sentido propio. Evitar dividir el flujo en funciones pequeñas que
  sólo oculten una o pocas líneas de código.
- Mantener las configuraciones meteorológicas y de productos en archivos YAML.
  No dispersar niveles, variables, rutas o parámetros físicos como valores
  fijos dentro del código.
- Antes de implementar un conversor o producto, acordar los casos que requieren
  comprobación o manejo especial.
- Manejar únicamente los errores esperados y definidos para ese proceso. No
  incorporar condiciones defensivas genéricas ni correcciones automáticas no
  acordadas.
- Ante un dato requerido ausente o inconsistente, detener el proceso con un
  mensaje claro que indique modelo, corrida, archivo, variable, nivel o plazo
  involucrado.
- No ocultar errores mediante valores de relleno, valores por defecto o bloques
  `except Exception` que permitan continuar sin una decisión explícita.
- Todo bloque `try/except` debe informar claramente el error asociado y detener
  el proceso. Para errores esperados, el mensaje debe indicar el contexto
  meteorológico; para errores no previstos, debe indicar que ocurrió un error
  general y conservar el detalle original.
- Nunca usar `try/except` para silenciar un error, continuar con datos
  incompletos ni devolver un resultado como si el procesamiento hubiera
  finalizado correctamente.
- Los comentarios deben explicar decisiones meteorológicas, transformaciones de
  datos o propósito de una etapa; no deben describir sintaxis evidente de
  Python.

## Límites y cambios

- No incorporar base de datos, Node.js ni otro servicio web hasta confirmar su
  disponibilidad y necesidad en el servidor final.
- Mantener configuraciones, código y documentación separados de los datos y productos pesados.
- No borrar ni alterar archivos existentes sin autorización expresa.

## Documentación de seguimiento

- `docs/STATUS.md`: foto actual del avance, bloqueos y siguiente actividad.
- `docs/DECISIONS.md`: registro acumulativo de decisiones técnicas.
- `docs/ROADMAP.md`: hitos contractuales y resultados esperados.

Actualizar el estado o las decisiones sólo cuando exista un avance verificable,
un acuerdo confirmado o un cambio material de alcance.
