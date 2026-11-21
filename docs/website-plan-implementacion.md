# Plan de implementación de Visualizaciones 3D

**Fecha:** 20 de noviembre de 2026.

**Proyecto:** `/home/alen/Documents/Senamhi/metvis3D`.

**Estado al 21 de noviembre de 2026:** piloto local implementado; recorrido
visual y funcional aprobado por el usuario y acceso por la red local confirmado.
En desarrollo se utiliza arranque manual. El servicio automático queda preparado
para instalar y comprobar en la máquina final.

Construir una web conceptual para explorar, reproducir y descargar las animaciones
meteorológicas de `metvis3d`. La implementación evolucionará mediante pruebas y
ajustes hasta alcanzar la madurez necesaria para su publicación. Este documento
contiene los acuerdos funcionales, la propuesta técnica, los recursos y las
verificaciones necesarias para comenzar sin consultar la conversación original.

## Instrucciones para retomar el trabajo

Leer primero `AGENTS.md`, este documento y los archivos de `context/`. Revisar
después el estado real del repositorio: las etapas pueden estar parcialmente
implementadas cuando se retome el trabajo. Conservar cambios ajenos y continuar
desde el punto comprobado, sin regenerar trabajo terminado.

Las reglas de `AGENTS.md` siguen vigentes. En particular:

- No modificar, mover ni renombrar los GRIB de `data/raw/`.
- Mantener los nombres de código en inglés y comentarios, docstrings, mensajes y
  errores en español. El flujo principal debe ser lineal y legible.
- Mantener las configuraciones de productos y operación en YAML.
- Realizar verificaciones manuales reproducibles; no introducir una suite de
  pruebas automatizadas como parte de este alcance.
- No ocultar datos requeridos ausentes ni errores mediante valores inventados,
  excepciones silenciadas o resultados presentados como completos.
- La implementación es provisional hasta que el usuario la pruebe y apruebe.
  Actualizar la documentación consolidada y `context/` sólo después de esa
  aprobación. Este plan está autorizado como documento de trabajo independiente.

Las etapas pueden ejecutarse por separado o agruparse si resulta práctico.
Implementar una etapa no equivale a aprobarla ni a autorizar la publicación en
Internet. No crear alojamiento externo ni desplegar mediante servicios de Sites:
la instalación acordada es local, con Conda, en la workstation del usuario.
La aclaración del 21 de noviembre distingue el arranque manual en esta máquina
de desarrollo del servicio automático previsto para el equipo final.

## Propósito y alcance acordado

La web se llama **Visualizaciones 3D**. La utilizarán meteorólogos, personal de
comunicaciones y público general. Su función es consultar videos existentes;
la generación científica continúa en el flujo actual de Met.3D y ParaView.

Las colecciones **Fechas recientes** y **Eventos históricos** tienen la misma
importancia y las mismas funciones. Los históricos reúnen fechas seleccionadas
por su interés meteorológico y pueden utilizar otras fuentes, como ERA5. No
requieren una estructura de contenido diferente ni una ficha narrativa por evento.

La navegación prioriza **fecha → animación → escena → modelos disponibles**. La
hora UTC de referencia se muestra junto a la fecha y permite distinguir ciclos de
un mismo día. La herramienta de generación también es visible: actualmente se
prioriza Met.3D, pero ParaView puede incorporarse a cualquier animación.

La primera implementación incluye galería con miniaturas, filtros, reproducción,
descarga, metadatos disponibles, tema claro y oscuro, y funcionamiento como
servicio en Linux. El acceso inicial es libre desde la red interna. Computadoras
de escritorio y portátiles son la referencia de diseño y validación.

La comparación simultánea entre modelos y el inicio de sesión quedan para una
ampliación posterior. No dimensionarlos ni implementarlos ahora. El frontend
puede adaptarse a ventanas estrechas sin convertir una versión móvil específica
en requisito de aceptación. Las tarjetas representan sólo videos existentes;
no mostrar productos pendientes o combinaciones sin datos.

## Insumos y estado de partida

### Rutas que debe conocer la implementación

| Recurso | Ruta |
| --- | --- |
| Proyecto | `/home/alen/Documents/Senamhi/metvis3D` |
| Reglas | `AGENTS.md` |
| Contexto | `context/STATUS.md`, `context/DECISIONS.md`, `context/ROADMAP.md` |
| Videos de referencia | `outputs/20261106/outputs/` |
| Configuraciones Met.3D | `config/met3d/animations/` y `config/met3d/scenes/` |
| Configuraciones ParaView | `config/paraview/animations/` y `config/paraview/scenes/` |
| Flujo Met.3D | `src/visualize/met3d_animation.py` y `src/visualize/met3D/` |
| Flujo ParaView | `src/visualize/paraview/animation.py` |
| Guías científicas | `docs/met3d.md` y `docs/paraview.md` |
| Recursos de identidad | `/home/alen/Documents/Codex/2026-11-20/qu/outputs/identidad-observatorio/` |

Al preparar este documento no existe `website/`. La carpeta de referencia contiene
66 MP4 y un `.gitkeep`, distribuidos así:

| Software | Animación de origen | Cantidad |
| --- | --- | ---: |
| Met.3D | `dana` | 20 |
| Met.3D | `friaje` | 20 |
| Met.3D | `jet` | 15 |
| ParaView | `south_america_jet` | 11 |

Están presentes IFS, GFS, ETA y WRF, con disponibilidad distinta según producto y
software. Las fechas de referencia son 2026-06-20, 2026-08-16, 2026-08-21,
2026-10-02 y 2026-10-14, a las 00 UTC. La inspección previa encontró H.264,
1920 × 1080, 6 o 10 fotogramas por segundo y duraciones de 2,1 a 14 segundos.
Volver a contar los archivos al implementar; estos números son la referencia
inicial, no una cantidad fija dentro del código.

La raíz general `outputs/` contiene análisis, copias de otras máquinas y
experimentos. **No recorrerla como catálogo ni como fuente de importación.**
Existen salidas más recientes de anticiclones y nubosidad fuera de la referencia;
no incorporarlas automáticamente en la preparación inicial.

Los MP4 antiguos no tienen todos los metadatos complementarios de las ejecuciones
recientes. Su nombre y ubicación permiten identificar producto, fuente, fecha y
software. La presencia de un modelo en esos videos no implica que el conversor
actual lo produzca de forma operativa.

## Tecnología y organización

Usar **Flask y Jinja en Python**, con HTML, CSS y JavaScript organizados por
función. Es suficiente para la galería y el reproductor acordados. No se requiere
React ni una etapa de compilación del frontend. No añadir una base de datos,
procesos de vigilancia de carpetas o tareas periódicas para construir el catálogo.

Backend y frontend tendrán carpetas separadas y serán atendidos por un único
servicio. El backend leerá YAML y archivos locales; el navegador manejará los
filtros y las interacciones. El reproductor utilizará el elemento HTML `video`.

```text
metvis3D/
  docs/
    website-plan-implementacion.md
  website/
    backend/
      src/
        application.py            # Aplicación y rutas de la web
        catalog.py                # Lectura del catálogo de videos
        publication.py            # Preparación de copias y miniaturas
    frontend/
      templates/                  # Páginas Jinja
      static/
        css/
        js/
        fonts/
        brand/
    config/
      website.yaml                # Rutas, servidor y presentación general
      catalog.yaml                # Nombres y descripciones por identificador
      publication.yaml            # Correspondencias de las salidas de referencia
    video/
      recent/                     # MP4, JPG y metadatos opcionales publicados
      historical/
    scripts/                      # Lanzadores breves de procesos principales
    deploy/                       # Archivo de servicio systemd
    validation/                   # Resultados generados de verificaciones
    environment.yml
    pyproject.toml
```

La lógica operativa debe residir directamente en `website/backend/src/`, con
módulos como `application.py`, `catalog.py` y `publication.py`, sin una carpeta
adicional de paquete. Los lanzadores sólo reciben argumentos y llaman al proceso
correspondiente. Mantener pocos módulos que representen operaciones reconocibles,
sin reproducir capas de arquitectura innecesarias. `website/pyproject.toml`
declarará esos módulos y su ubicación para instalarlos desde `website/` e
importarlos en el ambiente web, independientemente del directorio de ejecución
y sin modificar el paquete científico de la raíz.

Crear el ambiente **`metvis3d-web`** mediante `website/environment.yml`, con
`conda-forge` como canal. Incluir Python, Flask, Gunicorn, PyYAML y FFmpeg; Jinja
se incorpora con Flask. Elegir una versión de Python compatible al resolver el
ambiente y fijar las versiones comprobadas. No modificar ni reutilizar el
`environment.yml` científico para satisfacer dependencias de la web.

Guardar código, YAML y recursos gráficos propios en Git. Excluir los videos,
miniaturas de publicación, resultados de validación y archivos generados de
instalación. La regla actual `*.jpg` de `.gitignore` también excluye el logotipo
de MINAM: crear una excepción limitada a los recursos de marca que se incorporen,
sin habilitar todas las imágenes del proyecto.

## Organización de los videos

La carpeta de publicación será, inicialmente, `website/video/`. Configurar su
ruta en YAML; no fijar la ruta absoluta de esta workstation dentro del código.
Una ruta relativa se resolverá respecto de `website/`, con independencia del
directorio desde el que se ejecute el servicio. Admitir una ruta absoluta cuando
el contenido se encuentre en otro disco.

Mantener sólo dos subcarpetas de colección:

```text
website/video/
  recent/
    20260620_00Z__friaje__south_america__ncep-gfs__met3d.mp4
    20260620_00Z__friaje__south_america__ncep-gfs__met3d.jpg
  historical/
```

La pertenencia a una colección viene dada por la carpeta. No mover ni reclasificar
automáticamente un video por su antigüedad. Las eliminaciones de fechas recientes
las realizará el responsable de los archivos; la aplicación sólo reflejará lo
que encuentre.

### Nomenclatura

```text
YYYYMMDD_HHZ__animation__scene__center-model__software.mp4
```

| Campo | Regla |
| --- | --- |
| Fecha y hora | Fecha del calendario y hora UTC de referencia, con formato `20260620_00Z` |
| Animación | Identificador, por ejemplo `friaje`, `dana`, `jet`, `clouds` o `anticyclones` |
| Escena | Identificador, por ejemplo `south_america` o `peru` |
| Fuente | Centro y modelo o conjunto de datos, por ejemplo `ncep-gfs`, `ecmwf-ifs` o `ecmwf-era5` |
| Software | Identificador, inicialmente `met3d` o `paraview` |

Usar minúsculas en los identificadores, salvo la `Z` temporal. Admitir letras ASCII,
números, guiones y guiones bajos simples dentro de ellos; reservar `__` para separar
los cinco campos. No usar espacios ni tildes en los nombres físicos. Validar
también la fecha del calendario y la hora entre 00 y 23.

La fecha representa la referencia meteorológica del producto, no la fecha de
copia, modificación o publicación. Para pronósticos se puede presentar como
«Corrida»; para ERA5, «Fecha de referencia». No interpretar todos los productos
como pronósticos ni equiparar una animación de modelo con un evento observado.

La miniatura tendrá el mismo nombre base con extensión `.jpg`. El archivo
opcional de información específica será `<nombre_base>.metadata.yaml`.
El software forma parte de la identificación, por lo que dos herramientas pueden
publicar el mismo producto, escena, fuente y fecha sin colisiones. La colección
también distingue archivos del mismo nombre que estén en ambas colecciones.

### Metadatos y YAML

`catalog.yaml` contendrá mapas por identificador para animaciones, escenas,
fuentes y software: título legible, descripción opcional y orden opcional.
Su función es enriquecer la vista, no autorizar qué videos aparecen. Un
identificador nuevo debe mostrarse inmediatamente con su texto original cuando
todavía no tenga una entrada descriptiva.

El nombre del MP4 es la fuente de los campos de identificación. Los metadatos
opcionales pueden añadir variables, unidades, periodo representado y notas
específicas de esa ejecución. Omitir los campos que no se conozcan; no completar
variables ni plazos usando la configuración actual de una animación antigua.
Si un archivo complementario declara un dato de identificación, debe coincidir
con el nombre; de lo contrario informar el conflicto y detener esa lectura.

La duración de reproducción en segundos se distingue del periodo meteorológico
representado. No deducir los plazos a partir de los segundos del MP4. Mantener
UTC explícito para los tiempos meteorológicos.

## Preparación del contenido inicial

Implementar un proceso manual de publicación desde la referencia hacia
`website/video/recent/`. La referencia es un insumo de desarrollo: el servicio
final leerá directamente la carpeta de publicación con la nomenclatura nueva.
No mantener dos estructuras de catálogo en la aplicación web.

Las correspondencias de origen se declararán en `publication.yaml`:

| Software de origen | Producto de origen | Animación publicada | Escena publicada |
| --- | --- | --- | --- |
| `met3d` | `dana` | `dana` | `south_america` |
| `met3d` | `friaje` | `friaje` | `south_america` |
| `met3d` | `jet` | `jet` | `south_america` |
| `paraview` | `south_america_jet` | `jet` | `south_america` |

Resolver la fuente y la fecha a partir de los nombres y carpetas existentes,
comprobando que coincidan. La escena `south_america` se asigna mediante esa
correspondencia explícita. No inferirla a partir del contenido visual del video.

El flujo principal de preparación debe:

1. Leer configuración y comprobar todos los nombres y destinos antes de copiar.
2. Detectar colisiones y presentar cualquier correspondencia ausente con su ruta.
3. Copiar los MP4 sin recodificar y comprobar igualdad mediante SHA-256.
4. Consultar FFprobe y extraer una imagen con FFmpeg por video.
5. Registrar origen, destino, comprobación y resultado de cada archivo.

La posición del fotograma para la miniatura será configurable y podrá tener
excepciones por archivo; seleccionar un instante interior del video. No ejecutar
FFmpeg durante una visita a la web. En una repetición de la preparación, conservar
las copias idénticas ya comprobadas; detenerse ante destinos diferentes del
origen, sin sobrescribirlos silenciosamente. No implementar versiones de videos.

No modificar los generadores científicos para completar esta primera etapa. La
adaptación futura del flujo de entrega a la nomenclatura queda bien definida por
el contrato anterior y podrá integrarse después de validar la web.

Mantener `historical/` vacía en el uso habitual inicial. Para comprobar esa
colección se utilizará una carpeta de publicación temporal, fuera del catálogo
habitual, con una copia de prueba y un aviso visible de demostración. Al terminar,
volver a la configuración normal; no presentar esa copia como evento histórico
seleccionado o validado científicamente.

## Catálogo y entrega de archivos

Al cargar o actualizar la página, el navegador solicitará una vez el catálogo al
backend. Éste leerá en ese momento los MP4 de las dos colecciones configuradas y
sus metadatos opcionales. Los filtros operarán sobre ese resultado, sin consultas
periódicas ni nuevas exploraciones por cada clic.

No ejecutar FFprobe ni inspeccionar fotogramas para reconstruir el catálogo en
cada visita. La preparación de publicación produce las miniaturas y la información
adicional necesaria. El catálogo puede funcionar sólo con el nombre del MP4.

Propuesta mínima de rutas, ajustable conservando su comportamiento:

| Solicitud | Función |
| --- | --- |
| `GET /` | Entregar la interfaz |
| `GET /api/videos` | Leer y devolver el catálogo actual |
| `GET /media/<collection>/<filename>` | Entregar un MP4 o JPG publicado |
| `GET /download/<collection>/<filename>` | Descargar un MP4 como archivo adjunto |

La identificación de cada entrada incluirá colección y nombre. La respuesta del
catálogo contendrá los campos meteorológicos, títulos disponibles y direcciones
de miniatura, reproducción y descarga. No exponer rutas absolutas locales.

Limitar las rutas de archivos a las colecciones y formatos previstos, comprobando
que el destino resuelto permanezca dentro de la carpeta configurada. No publicar
configuraciones, registros ni `.metadata.yaml` como un directorio navegable.

La entrega de video debe admitir solicitudes de fragmentos HTTP, conocidas como
`Range`, para que el navegador pueda avanzar sin descargar otra vez todo el
archivo. Usar las funciones de entrega de archivos de Flask/Werkzeug. Comprobar
el tipo de contenido y la descarga con nombre correcto. Evitar que una copia
antigua del catálogo en el navegador o el proxy oculte los cambios al recargar.

## Interfaz y reproducción

La pantalla principal tendrá una cabecera compacta con el nombre del proyecto,
selector de tema y las colecciones que tengan videos. A continuación mostrará
los filtros y la galería. La información científica y las miniaturas ocuparán
el espacio principal; no crear una portada promocional que retrase la consulta.

Ordenar fechas de más reciente a más antigua y seleccionar inicialmente la fecha
más reciente de la colección. Permitir consultar todas las fechas existentes.
Cuando haya varios ciclos en un día, ofrecer sus horas UTC como selección
asociada a esa fecha. En la galería conservar visibles fecha y ciclo de cada video.

Los selectores de animación y escena se limitarán a lo disponible bajo la
selección previa. Pueden incluir «Todas las animaciones» y «Todas las escenas».
Al cambiar una selección, quitar cualquier filtro subordinado que haya quedado
sin coincidencias. Mostrar juntos los modelos disponibles, sin obligar a elegir
uno antes de ver la galería. El software se muestra en cada tarjeta; un filtro
adicional por software sólo resulta necesario cuando haya alternativas.

Cada tarjeta tendrá JPG, título, fuente, software y referencia UTC. Al abrir un
video, utilizar un reproductor principal en un diálogo o área claramente
destacada. Debe poder cerrarse conservando los filtros y la posición de consulta.
Permitir un único video en reproducción y detenerlo al cerrar o cambiar de video.

Incluir reproducción y pausa, desplazamiento temporal, repetición continua
activada inicialmente, selector de velocidad, pantalla completa y descarga.
El inicio de reproducción partirá de una acción del usuario. Usar los controles
nativos del navegador y añadir los necesarios para que las funciones acordadas
sean visibles y consistentes, sin depender de menús particulares de un navegador.

La vista previa acordada es una imagen estática. La reproducción al pasar el
cursor y las miniaturas animadas no forman parte de esta implementación. Cargar
las imágenes según se necesiten y evitar descargar todos los MP4 al abrir la
galería. No colocar un reproductor activo por tarjeta.

Junto al reproductor presentar la información de identificación y los metadatos
adicionales disponibles. Admitir nombres de productos nuevos sin cambiar el
código ni exigir descripciones. No es necesario un buscador global ni un filtro
por variable en la primera implementación; los filtros principales deben resolver
la consulta acordada.

## Identidad visual

La referencia es el Observatorio Nacional del Tiempo, Agua y Clima del Perú:
<https://observatorio.senamhi.gob.pe/>. El usuario aportó una extracción visual y
de estilos de sus secciones de ciudadanos, investigadores, agricultores, gestión
de riesgos y El Niño. Aplicar ese lenguaje a una biblioteca de videos científica,
institucional y tecnológica. No tratar la extracción como manual oficial.

| Uso | Color |
| --- | --- |
| Verde de marca | `#3FA535` |
| Verde claro | `#6CC04A` |
| Azul de marca de la interfaz | `#0079C1` |
| Turquesa | `#00A9A7` |
| Azul adicional de interfaz | `#0049B9` |
| Amarillo de acción | `#FFCC20` |
| Fondo oscuro | `#050B18` |

Usar una firma de verde, turquesa y azul, con degradados moderados en elementos
de marca. El amarillo destaca la acción principal de reproducción. El tema oscuro
tendrá paneles azul pizarra diferenciados del fondo; el claro tendrá superficies
claras y texto oscuro con contraste equivalente. Definir ambos mediante variables
CSS compartidas y conservar la preferencia de tema localmente en el navegador.
Usar inicialmente el tema oscuro si no existe una elección guardada.

Utilizar Roboto con alternativa `sans-serif`, servida desde archivos locales con
su licencia. Pesos de referencia: 400, 500, 700 y 800. Cuerpo de al menos 16 px y
etiquetas habituales de al menos 14 px. Evitar exceso de mayúsculas y textos de
bajo contraste. Usar tarjetas y controles con esquinas próximas a 12 px, bordes
discretos, iconos de línea y estados de foco y selección claramente visibles.
La navegación y el reproductor deben poder utilizarse con teclado.

No recolorear las miniaturas ni los videos para adaptarlos al tema: sus colores
representan variables meteorológicas. Conservar su relación de aspecto y permitir
ver el contenido completo en el reproductor.

### Recursos gráficos locales

Directorio de origen:

```text
/home/alen/Documents/Codex/2026-11-20/qu/outputs/identidad-observatorio/
```

| Archivo | Características |
| --- | --- |
| `logo-senamhi.svg` | SVG transparente; `viewBox` de 341,6 × 166,8 |
| `logo-minam.jpg` | JPEG de 330 × 71, con fondo blanco |
| `LEEME.txt` | Procedencia, colores y recomendaciones de proporción |

Copiar los recursos que se utilicen a `website/frontend/static/brand/`, conservando
los originales externos. Usar **Visualizaciones 3D** como nombre principal; los
logotipos de SENAMHI y MINAM se mostrarán como identificación institucional
secundaria, sin sustituir la identidad del proyecto. Conservar proporciones,
colores y espacio libre; el JPG de MINAM necesita una superficie clara también
en el tema oscuro.

Los colores del SVG de SENAMHI son `#0047BA` y `#FFC600`; no confundirlos con los
colores de interfaz `#0049B9` y `#FFCC20`. Servir recursos y tipografía localmente
para no depender de la disponibilidad de la web de referencia. La información
aportada alcanza para comenzar; no se requiere otra extracción de identidad.

## Casos de funcionamiento que deben comprobarse

Estas reglas concretan el comportamiento propuesto para los casos especiales.
Si durante la implementación aparece un caso distinto que cambie el significado
de los productos, plantearlo antes de introducir una corrección automática.

| Caso | Comportamiento |
| --- | --- |
| Carpeta raíz configurada inexistente o sin acceso | Error claro con el contexto del directorio; no presentar un catálogo vacío como éxito |
| Raíz existente con colecciones vacías o todavía ausentes | Catálogo vacío válido; ocultar colecciones sin videos y mostrar un mensaje de ausencia de contenido |
| Histórico sin archivos | Ocultar su sección; mostrarla al actualizar cuando reciba videos |
| MP4 nuevo con identificadores válidos sin entrada en YAML | Mostrar el video y los identificadores originales; omitir descripciones ausentes |
| JPG ausente | Mostrar una tarjeta con una imagen neutra de interfaz y el título; mantener la reproducción disponible |
| MP4 con nombre o fecha inválidos | Informar el archivo y la regla incumplida; detener esa reconstrucción del catálogo, sin devolver una lista parcial como completa |
| Metadatos complementarios presentes pero inválidos o contradictorios | Informar archivo y campo; detener esa reconstrucción, sin ignorar el problema |
| Archivo eliminado desde la última carga | Desaparecer al actualizar; si se intenta abrir antes, informar que ya no está disponible |
| Archivo copiado con el mismo nombre y contenido diferente durante la preparación | Detener la preparación e identificar origen y destino; no sobrescribir silenciosamente |
| Dos herramientas para la misma combinación | Mostrar ambas tarjetas con software explícito |
| Distintos ciclos de una fecha | Mantenerlos diferenciados en filtros, tarjetas y metadatos |
| Fuente de reanálisis | Mostrar fecha de referencia sin atribuirle un horizonte de pronóstico inventado |
| Video dañado o ilegible | Detener la preparación si FFprobe falla; informar un fallo de reproducción si ocurre después |

Las copias son pequeñas, llegan terminadas y se incorporan aproximadamente una
vez al día, normalmente de madrugada. No añadir seguimiento de progreso,
observadores de archivos ni un protocolo de publicación complejo. Los errores
esperados deben tener mensajes específicos; los inesperados deben conservar su
detalle original y no permitir continuar con resultados aparentes de éxito.

## Operación local y preparación para publicación

Servir la aplicación mediante Gunicorn en el ambiente Conda independiente.
En desarrollo se inicia manualmente mediante `website/scripts/run_website.py`
con `conda run --no-capture-output -n metvis3d-web` y se detiene con Ctrl+C.
No instalar un servicio automático en esta workstation de desarrollo.

En la máquina final, el archivo systemd debe utilizar el ejecutable del ambiente
y un directorio de trabajo explícito, sin requerir activar Conda manualmente.
La ruta concreta se obtiene del ambiente instalado, no de una ruta de usuario
fijada dentro del código. La plantilla se prepara mediante
`website/scripts/prepare_service.py`, ejecutado en el ambiente web de ese equipo.

Preparar para la máquina final una unidad que arranque con el equipo y vuelva a
levantarse ante un fallo del proceso. La instalación y comprobación del arranque
al encender dependen de los permisos de systemd disponibles. Si no se puede
instalar, entregar la unidad terminada y los comandos exactos; informar esa
verificación pendiente en lugar de declarar que el inicio automático funciona.

El acceso inicial será desde la red interna mediante dirección y puerto
configurables, usando el servidor de aplicación sin depurador de desarrollo.
Los videos llegarán como copias desde las salidas ya generadas; el servicio web
no lanzará Met.3D ni ParaView ni modificará las fuentes científicas.

Preparar las rutas para servir en la raíz de un dominio o bajo un prefijo como
`/visualizaciones/`. Un proxy es el servidor que recibirá las visitas públicas y
las enviará a esta aplicación. Generar los enlaces de manera compatible con ese
prefijo y habilitar el tratamiento de cabeceras reenviadas únicamente cuando
exista el proxy real y se conozca su configuración. Comprobar en un entorno local
el prefijo sin afirmar que se validó el futuro servidor público.

La publicación en Internet se realizará cuando el usuario considere madura la
web y defina el servidor final. El login y su efecto sobre reproducción y descarga
directa de archivos se diseñarán en una ampliación posterior.

## Etapas y resultados verificables

### Etapa 1 Estructura y ambiente

Crear la estructura, los módulos directamente en `website/backend/src/`, los YAML
y el ambiente `metvis3d-web`. Configurar su instalación e importación mediante
`website/pyproject.toml`. Comprobar las dependencias, la importación de los módulos
y el arranque de una página mínima desde esa organización. Verificar que no se
modificó el ambiente científico.

**Resultado:** aplicación local arrancable con un comando reproducible y rutas
resueltas correctamente al ejecutar desde distintos directorios.

### Etapa 2 Preparación de videos

Implementar el proceso de publicación con las correspondencias explícitas.
Preparar las copias y las miniaturas de los 66 videos de referencia, o del total
comprobado si el origen cambió. Revisar conteos por producto y software, nombres,
ausencia de colisiones e igualdad SHA-256 de cada copia.

**Resultado:** colección reciente utilizable, originales intactos y registro
generado de preparación. La colección histórica habitual continúa vacía.

### Etapa 3 Catálogo y archivos

Implementar lectura del catálogo, enriquecimiento opcional, entrega de miniaturas,
video y descargas. Comprobar los casos de archivos y metadatos previstos. Revisar
con una solicitud HTTP que un fragmento válido del MP4 devuelve `206 Partial
Content`, y que un recurso eliminado devuelve `404` con un mensaje adecuado.

**Resultado:** catálogo coherente con el disco y navegación multimedia funcional,
sin exploración periódica de carpetas ni procesamiento multimedia por visita.

### Etapa 4 Interfaz e identidad

Construir galería, filtros dependientes, reproductor, metadatos y ambos temas.
Incorporar los recursos locales y revisar el comportamiento visual en los
navegadores de escritorio disponibles. Corregir recortes, desbordamientos,
contraste y estados de selección o error observados.

**Resultado:** recorrido completo desde elegir una fecha hasta reproducir y
descargar, con las funciones acordadas y la identidad aplicada.

### Etapa 5 Servicio y red

Ejecutar mediante Gunicorn y comprobar acceso desde otra computadora de la red.
Mantener el arranque manual en desarrollo. Preparar la unidad systemd para la
máquina final e instalarla allí cuando los permisos lo permitan.
Validar las rutas bajo un prefijo de prueba y revisar los registros del servicio.
Comprobar el arranque en la máquina final cuando sea posible realizar el reinicio
de forma coordinada con el usuario.

**Resultado:** operación local reproducible; distinguir con precisión lo
comprobado de la instalación, red o reinicio que todavía requiera intervención.

### Etapa 6 Revisión y aprobación

Ejecutar el recorrido de aceptación siguiente y conservar sus resultados
generados. Presentar al usuario la web y los límites de verificación. Ajustar lo
observado. Después de su aprobación, consolidar las instrucciones operativas y
actualizar `context/` dentro del alcance aprobado.

**Resultado:** versión revisada con evidencia de funcionamiento. La publicación
externa sigue siendo una decisión posterior.

## Recorrido manual de aceptación

Registrar fecha, comando o acción, entrada, resultado esperado, resultado obtenido
y evidencia pertinente en `website/validation/`. Las comprobaciones generadas no
constituyen aprobación del usuario ni actualización del estado oficial.

1. Crear el ambiente desde `website/environment.yml` e instalar los módulos de
   `website/backend/src/` mediante `website/pyproject.toml`, ejecutando la instalación
   desde `website/`. Comprobar su importación y el arranque desde distintos
   directorios, además de Flask, Gunicorn, YAML, FFmpeg y FFprobe.
2. Preparar la colección de referencia y contrastar su cantidad por producto y
   software con el origen. Verificar todas las copias mediante SHA-256.
3. Abrir la web y consultar cada fecha, producto y fuente disponible. Confirmar
   que no aparecen combinaciones inexistentes ni datos de otras carpetas.
4. Añadir una copia de prueba con nombre válido; recargar y comprobar su aparición.
   Eliminar esa copia; recargar y comprobar que desaparece.
5. En una carpeta temporal configurada, comprobar la colección histórica vacía y
   después con una copia de demostración. Volver a la configuración habitual.
6. Comprobar nuevas animación, escena, fuente y herramienta sin añadir sus títulos
   al YAML; deben aparecer con sus identificadores. Añadir títulos y revisar la
   presentación tras recargar.
7. En la carpeta temporal, comprobar nombre inválido, metadatos contradictorios y
   miniatura ausente según la tabla de casos, sin alterar el catálogo habitual.
8. Comprobar varios ciclos y dos herramientas para una misma combinación usando
   copias de demostración identificadas como tales. No atribuir esos nombres
   sintéticos a nuevos resultados meteorológicos reales.
9. Reproducir, pausar, avanzar, repetir al terminar, cambiar velocidad y entrar en
   pantalla completa. Cerrar y comprobar que el video se detiene. Verificar la
   descarga y su igualdad con el archivo publicado.
10. Confirmar que se descargan miniaturas en la galería y que no se transfieren
    todos los MP4 antes de abrirlos. Comprobar la solicitud parcial de video.
11. Cambiar entre tema claro y oscuro y recargar para comprobar la preferencia.
    Revisar tarjetas y reproductor a 1366 × 768 y 1920 × 1080, con teclado y con
    aumento de texto. Probar al menos Chromium y Firefox si están disponibles.
12. Comprobar Gunicorn, registros, acceso desde la red y funcionamiento bajo el
    prefijo de prueba. Revisar estado del servicio y arranque automático cuando
    las condiciones permitan verificarlo.

Si el entorno no permite navegador, otra computadora o reinicio, informar qué
parte quedó sin comprobar y entregar los pasos exactos para completarla. No
afirmar verificación visual, acceso de red o inicio automático sin observarlo.

## Condiciones para completar la implementación

La entrega debe incluir código organizado, ambiente reproducible, YAML ajustables,
colección de prueba preparada, recursos locales, configuración del servicio y
resultados de las comprobaciones ejecutadas. Informar archivos cambiados, comando
de arranque, dirección local y limitaciones materiales.

La web debe admitir el crecimiento del catálogo por archivos nuevos sin modificar
código: colecciones reconocidas, nuevas fechas, animaciones, escenas, fuentes y
software. Su apariencia y sus funciones básicas deben ser utilizables desde la
primera versión. La madurez para publicación se evaluará con el usuario después
de las pruebas y ajustes.

## Referencias técnicas

- [Flask y plantillas](https://flask.palletsprojects.com/en/stable/quickstart/).
- [Entrega de archivos en Flask](https://flask.palletsprojects.com/en/stable/api/#flask.send_file).
- [Gunicorn con Flask](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/).
- [Flask detrás de un proxy](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/).
- [Video HTML y portada](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video).
- [Velocidad de reproducción](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/playbackRate).

