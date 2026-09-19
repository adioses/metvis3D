# Hoja de ruta contractual

Los cuatro hitos de este documento corresponden directamente a los puntos A,
B, C y D solicitados por el cliente. El entorno Docker/Conda, el inventario de
archivos y las pruebas de herramientas son actividades de soporte; su avance se
registra en `STATUS.md`, no como hitos independientes.

Los procedimientos, tecnologías puntuales y comprobaciones se detallarán al
abordar cada hito. No se consideran definidos sólo por estar mencionados aquí.

## A. Preparación, transformación y estandarización de información meteorológica

Objetivo: implementar el proceso que recibe las fuentes seleccionadas y entrega
una estructura homogénea para visualización, respetando las características de
cada modelo.

Actividades a definir y ejecutar:

- Caracterizar las fuentes ECMWF y GFS: estructura, formatos, nomenclatura,
  coordenadas, resolución, niveles verticales, ciclos y horizontes.
- Revisar la documentación técnica y acordar las variables necesarias para los
  productos seleccionados.
- Definir y documentar el contrato NetCDF común, manteniendo los niveles
  verticales nativos acordados.
- Implementar los adaptadores de los modelos y las comprobaciones propias del
  proceso de conversión.

Resultado esperado: NetCDF homogéneos y documentados, compatibles con los
procesos de visualización posteriores.

## B. Visualizaciones tridimensionales y animaciones meteorológicas

Objetivo: generar productos 3D configurables, claros y visualmente atractivos
para difusión institucional y medios de prensa.

Actividades a definir y ejecutar:

- Acordar eventos, variables, dominios, duración y estilo de los productos.
- Preparar plantillas configurables para campos 3D, superficies, topografía,
  transparencias, paletas, iluminación, cámaras y perspectivas.
- Usar ParaView y/o Blender según el aporte de cada herramienta al producto.
- Generar animaciones reproducibles con información histórica o de pronóstico.

Resultado esperado: plantillas y animaciones configurables que puedan ajustarse
en Jupyter y reproducirse mediante el flujo de producción.

## C. Plataforma web piloto

Objetivo: organizar, consultar, filtrar y reproducir las animaciones
meteorológicas publicadas.

Actividades a definir y ejecutar:

- Verificar las capacidades y el software disponible en el servidor final.
- Seleccionar una tecnología web mínima compatible con dichas restricciones.
- Implementar catálogo, indexación y filtros por evento, modelo, variable y
  fecha.
- Incorporar controles de reproducción y publicación para históricos,
  información reciente y pronósticos.

Resultado esperado: plataforma web piloto funcional con acceso a productos
multimedia según los criterios solicitados.

## D. Integración, operación y documentación

Objetivo: dejar operativo un flujo modular desde la preparación de datos hasta
la publicación, junto con su documentación técnica y funcional.

Actividades a definir y ejecutar:

- Integrar preparación, conversión, visualización, producción de animaciones y
  publicación.
- Estructurar configuraciones y componentes para reutilizarlos con nuevos
  periodos y datos compatibles.
- Preparar procedimientos de generación, publicación, operación y
  mantenimiento.
- Documentar arquitectura, estructura de datos, componentes y pautas de uso.

Resultado esperado: producto implementado, operativo y documentado para su
uso por el equipo responsable.
