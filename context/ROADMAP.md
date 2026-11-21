# Hoja de ruta contractual

Los cuatro hitos de este documento corresponden directamente a los literales
a), b), c) y d) de la sección 6, «Alcance y descripción del servicio», de los
Términos de Referencia. El entorno Docker/Conda, el inventario de archivos y
las pruebas de herramientas son actividades de soporte; su avance se registra
en `STATUS.md`, no como hitos independientes.

Los procedimientos, tecnologías puntuales y comprobaciones se detallarán al
abordar cada hito. No se consideran definidos sólo por estar mencionados aquí.

## A. Preparación, transformación y estandarización de información meteorológica

Objetivo: implementar el proceso que recibe la información de los modelos,
variables y eventos seleccionados, y entrega una estructura homogénea para los
procesos posteriores de visualización, respetando las características de cada
fuente.

Actividades a definir y ejecutar:

- Caracterizar las fuentes ECMWF y GFS: estructura, formatos, nomenclatura,
  sistemas de coordenadas, resolución espacial, niveles verticales, ciclos de
  inicialización y horizontes de pronóstico.
- Revisar la documentación técnica y acordar las variables necesarias para los
  productos seleccionados.
- Definir y documentar el contrato NetCDF común, manteniendo los niveles
  verticales nativos acordados.
- Implementar los adaptadores de los modelos y las comprobaciones propias del
  proceso de conversión.

Resultado esperado: estructura de datos homogénea y documentada, compatible
con los procesos de visualización posteriores.

## B. Visualizaciones tridimensionales y animaciones meteorológicas

Objetivo: implementar y configurar visualizaciones tridimensionales y
animaciones meteorológicas a partir de los datos procesados, con productos
configurables, claros y visualmente atractivos para difusión institucional y
medios de prensa.

Actividades a definir y ejecutar:

- Acordar eventos, variables, dominios, duración y estilo de los productos.
- Preparar plantillas configurables, según corresponda, para campos
  atmosféricos 3D, superficies, topografía, transparencias, paletas,
  iluminación, cámaras y perspectivas.
- Usar ParaView y/o Blender según el aporte de cada herramienta al producto.
- Generar animaciones reproducibles con información histórica o de pronóstico.

Resultado esperado: plantillas y animaciones configurables que puedan ajustarse
en Jupyter y reproducirse mediante el flujo de producción.

Avance confirmado al 2026-11-17: composición de anticiclones aprobada por el
usuario con PNM por rangos y partículas con rastros de seis horas en todo el
dominio disponible de Sudamérica, usando IFS como referencia. El registro de
la decisión es D-015 y la ejecución está en `docs/met3d.md`. Esta aprobación
visual aporta al hito B; su cierre conserva pendiente la validación
meteorológica y los demás productos acordados.

## C. Plataforma web piloto

Objetivo: desarrollar una plataforma web piloto para organizar, consultar,
filtrar y reproducir las animaciones meteorológicas generadas.

Actividades a definir y ejecutar:

- Verificar las capacidades y el software disponible en el servidor final.
- Seleccionar una tecnología web mínima compatible con dichas restricciones.
- Implementar catálogo, indexación y filtros por evento, modelo, variable y
  fecha.
- Incorporar controles de reproducción multimedia y componentes de gestión e
  indexación para publicar eventos históricos, información reciente y
  pronósticos.

Resultado esperado: plataforma web piloto funcional con acceso a productos
multimedia según los criterios solicitados.

Avance confirmado al 2026-11-21: piloto Visualizaciones 3D implementado con
Flask/Jinja y Gunicorn, 66 videos de referencia preparados y recorrido visual
y funcional aprobado por el usuario. El acceso desde la red local está
confirmado. El alcance inicial consulta por colección, fecha/ciclo, animación,
escena y herramienta, mostrando juntas las fuentes disponibles; el filtro por
variable queda fuera de esta primera versión. En desarrollo se utiliza
arranque manual. El servicio automático está preparado y se instalará y
comprobará en la máquina final, conforme a D-016. Este avance no declara
completado el despliegue final ni la publicación en Internet.

## D. Integración, operación y documentación

Objetivo: dejar implementado y operativo un flujo modular desde la preparación
de datos hasta la publicación, junto con su documentación técnica y funcional.

Actividades a definir y ejecutar:

- Integrar preparación, conversión, visualización, producción de animaciones y
  publicación.
- Estructurar configuraciones y componentes para reutilizarlos con nuevos
  periodos y datos compatibles.
- Preparar procedimientos de generación, publicación, operación y
  mantenimiento, con parámetros ajustables y reutilizables para nuevos
  periodos o datos compatibles.
- Documentar arquitectura, estructura de datos, componentes, procedimientos de
  generación y publicación, y pautas básicas de operación y mantenimiento.

Resultado esperado: producto implementado, operativo y documentado para su
uso por el equipo responsable.
