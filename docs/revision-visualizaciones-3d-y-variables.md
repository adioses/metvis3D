# Revisión técnica: animaciones meteorológicas 3D y variables a representar

**Estado:** borrador de investigación para el primer entregable del TDR  
**Fecha de consulta:** 25 de septiembre de 2026  
**Alcance:** sustentar la selección de variables para animaciones meteorológicas
tridimensionales. No define todavía una selección por modelo ni modifica el
contrato de datos.

## 1. Propósito y límites de esta revisión

El punto 6.a del TDR requiere revisar documentación técnica para definir las
variables a representar. Esta revisión responde a esa obligación desde el
producto que se quiere construir: **animaciones 3D de modelos numéricos**, con
utilidad para pronóstico, análisis de eventos históricos y comunicación
institucional.

No se busca el mínimo común de variables entre modelos. Cada animación puede
usar el modelo que entregue los campos físicos necesarios. Por ello, la
selección se organiza por fenómeno y por técnica 3D, no por GFS, ECMWF, ETA o
MPAS.

Se excluyen deliberadamente los gráficos bidimensionales y los cortes como
producto objetivo. Un campo de superficie (por ejemplo, precipitación, presión
al nivel del mar o temperatura del mar) puede aparecer sobre el terreno o el
océano como contexto espacial de una escena 3D, pero no se contabiliza como la
visualización atmosférica tridimensional principal. Tampoco se incluyen
huracanes u otros fenómenos fuera del ámbito sudamericano.

## 2. Método de revisión

Se revisaron artículos científicos, documentación de centros de investigación y
productos técnicos de meteorología. La evidencia se clasificó así:

- **Método de visualización:** demuestra que una técnica 3D se usa con datos de
  modelos atmosféricos (volumen, isosuperficie, trayectorias, partículas o
  terreno).
- **Uso meteorológico:** vincula los campos con un fenómeno o una tarea de
  pronóstico.
- **Aplicación regional:** muestra la relevancia física de las variables para
  Perú, los Andes o Sudamérica.
- **Implementación:** documenta qué tipo de variables volumétricas o vectoriales
  se emplean en software de visualización científica.

Las recomendaciones siguientes son una síntesis técnica de esas fuentes. No
implican que una variable deba estar disponible en todos los modelos ni que un
producto sea operacional sin validación del especialista meteorólogo.

## 3. Conclusión ejecutiva

La literatura respalda que las animaciones 3D de mayor valor meteorológico se
basan en la combinación de un **campo escalar volumétrico** que revela una
estructura atmosférica y un **campo vectorial o un segundo escalar** que explica
su dinámica. El terreno da contexto físico y geográfico, especialmente en los
Andes.

Las familias priorizadas son:

1. **Viento tridimensional y transporte:** partículas, trayectorias o líneas de
   corriente generadas con `u`, `v` y, cuando exista, `w`; color por rapidez,
   humedad o altura.
2. **Nubes, humedad e hidrometeoros:** volumen semitransparente o
   isosuperficies de agua de nube, hielo, lluvia, nieve, graupel, reflectividad,
   fracción nubosa o, como aproximación menos específica, humedad relativa.
3. **Estructuras dinámicas de escala sinóptica:** isosuperficies de rapidez del
   viento para chorros y de vorticidad potencial para tropopausa dinámica/DANA,
   coloreadas por presión, temperatura potencial o humedad.
4. **Interacción atmósfera-terreno:** trayectorias de viento y volumen de
   humedad/nube sobre un DEM; adecuada para transporte de humedad, ascenso
   orográfico, heladas y lluvias en los Andes.
5. **Evolución de lluvia intensa o El Niño costero:** combinación de transporte
   de humedad y viento de bajo nivel, ascenso, nubes/hidrometeoros y el terreno
   costero-andino. La precipitación acumulada y la SST son capas de contexto en
   la escena, no sustitutos de la estructura 3D.

En cambio, no se recomienda presentar temperatura, humedad relativa,
precipitación o presión de superficie como una extrusion artificial por sí
sola: pierde significado físico vertical. Deben formar parte de una escena cuyo
elemento principal sea realmente volumétrico, una isosuperficie o un flujo 3D.

## 4. Técnicas 3D respaldadas y variables necesarias

| Familia de animación 3D | Construcción tridimensional | Variables de entrada | Mejor finalidad | Fundamento |
|---|---|---|---|---|
| Flujo y transporte | Partículas, trayectorias o líneas de corriente animadas en el volumen | `u`, `v`, `w`; rapidez derivada; opcionalmente humedad específica, `RH` o temperatura para el color | Ambas; muy apta para didáctica si la escena es limpia | VAPOR y Met.3D incluyen visualización de flujo 3D; Treinish usa líneas de corriente en modelos anidados [R1, R3, R7]. |
| Chorro y circulación de altura | Isosuperficie de rapidez de viento, con color por presión, altura, temperatura o `PV` | `u`, `v`; rapidez derivada; altura geopotencial, presión, temperatura potencial o `PV` derivada | Principalmente operativa; también didáctica | Met.3D muestra isosuperficies de 30 y 50 m s-1 para localizar el chorro y su estructura espacial [R1]. |
| DANA / vaguada aislada | Isosuperficie de `PV`, complementada por trayectorias de viento y volumen de nubes/humedad | `u`, `v`, `w`, temperatura, altura geopotencial, humedad; `PV`, vorticidad y temperatura potencial derivadas | Operativa y didáctica | Los estudios de bajas aisladas emplean altura geopotencial, vorticidad y `PV`; la `PV` identifica la tropopausa dinámica y el núcleo de la DANA [R10-R13]. |
| Convección, tormenta y lluvia intensa | Volumen o isosuperficies de hidrometeoros / reflectividad, con viento 3D y ascenso | Agua de nube, hielo, lluvia, nieve, graupel y/o reflectividad; `w`, `u`, `v`, temperatura, humedad | Ambas; especialmente didáctica y de alto impacto | La representación físicamente basada de hidrometeoros comunica la naturaleza 3D de una tormenta; VAPOR documenta volumen e isosuperficies para datos de tormenta [R3, R6, R8]. |
| Nubes y humedad | Volumen semitransparente o isosuperficies de condensado; `RH`/fracción nubosa sólo como alternativa | Agua de nube y hielo preferentemente; fracción nubosa, humedad específica o relativa como alternativas | Didáctica; apoyo operativo para ubicación de nubosidad | La documentación WRF/VAPOR muestra volumen de vapor, temperatura y nubes; una aplicación web 3D usa fracción nubosa como volumen [R5, R8, R9]. |
| Transporte de humedad y chorro de bajo nivel | Trayectorias de viento de bajo nivel coloreadas por humedad o flujo de humedad, con terreno | `u`, `v`, `w`, humedad específica; flujo de humedad e IVT derivados; precipitación como contexto | Ambas; muy relevante para Sudamérica | El SALLJ transporta humedad a lo largo del flanco oriental andino y se relaciona con convección y precipitación extrema [R15-R18]. |
| Interacción orográfica | Trayectorias en 3D, condensado/humedad volumétrica y DEM; se puede mostrar ascenso mediante `w` | DEM/orografía, `u`, `v`, `w`, temperatura potencial, humedad, hidrometeoros | Ambas | La visualización de modelos anidados combina líneas de corriente, campos escalares y topografía; los trabajos de Perú asocian lluvias a flujo de bajo nivel y ascenso orográfico [R7, R14, R19]. |
| Masa de aire fría, helada o ingreso frío | Isosuperficie de temperatura potencial o temperatura, con flujo y terreno | Temperatura, `u`, `v`, `w`, humedad; temperatura potencial y estabilidad derivadas; `T2m` como contexto | Operativa, con alto potencial didáctico | La temperatura potencial y la temperatura equivalente son campos 3D usados en análisis de NWP; su interpretación debe estar guiada por meteorología [R2]. |
| El Niño costero y lluvias de la costa norte | Escena costera con trayectorias de viento/humedad, volumen nuboso e hidrometeoros; SST y precipitación como contexto superficial | Viento bajo nivel, `w`, humedad, agua de nube/hidrometeoros, temperatura, altura geopotencial; SST y precipitación acumulada como contexto | Ambas | Estudios de Piura y norte peruano relacionan lluvia intensa con flujo oeste de bajo nivel, humedad, SST cálida y ascenso orográfico [R14, R19-R21]. |

## 5. Variables candidatas y papel dentro de una escena

La lista se organiza por función física. Las variables denominadas “derivadas”
no obligan a que el modelo las entregue directamente; pueden calcularse de los
campos básicos cuando la definición, la malla y las unidades lo permitan.

| Grupo | Variables | Uso 3D recomendado | Prioridad |
|---|---|---|---|
| Viento 3D | Componentes zonal, meridional y vertical (`u`, `v`, `w`) | Partículas, trayectorias, líneas de corriente y vectores discretos. `w` es esencial para representar ascenso/descenso y convección. | Muy alta |
| Termodinámica 3D | Temperatura, humedad específica, humedad relativa, altura geopotencial | Volumen tenue, color de otra estructura, o cálculo de temperatura potencial/equivalente y estabilidad. | Muy alta |
| Dinámica derivada | Rapidez del viento, vorticidad relativa, divergencia, vorticidad potencial, temperatura potencial, temperatura potencial equivalente | Isosuperficies de chorro, DANA/tropopausa, masas de aire y estructura dinámica. | Alta |
| Nube e hidrometeoros | Agua de nube, agua/hielo de nube, lluvia, nieve, graupel, reflectividad, fracción nubosa | Volumen o isosuperficies; son los campos más expresivos para una nube o tormenta físicamente tridimensional. | Alta cuando estén disponibles |
| Transporte de humedad | Flujo de humedad, transporte integrado de vapor (IVT), convergencia de humedad | Color de trayectorias y apoyo a la explicación de alimentación de precipitación. | Alta para Andes, SALLJ y El Niño costero |
| Convección diagnóstica | CAPE, CIN, nivel de condensación, base/tope de nube | Elementos auxiliares o disparadores narrativos; no constituyen por sí mismos un volumen 3D. | Media |
| Superficie y contexto | DEM, SST, precipitación acumulada/intensidad, presión al nivel del mar, `T2m`, viento a 10 m | Terreno, océano y señal de impacto bajo el volumen atmosférico. No deben convertirse artificialmente en “volúmenes meteorológicos”. | Alta como contexto |

### Reglas de selección por calidad física

1. Para visualizar una nube o una tormenta, se debe preferir condensado,
   hidrometeoros o reflectividad antes que humedad relativa. `RH` alta no es
   equivalente a una nube y debe presentarse como indicador de ambiente húmedo,
   no como nube fotorrealista.
2. Para viento, las partículas o trayectorias deben integrar un vector 3D. Las
   flechas excesivas ocultan la forma de la estructura y dificultan la lectura.
3. Para DANA y chorros, `PV`, temperatura potencial, vorticidad o rapidez del
   viento son más expresivas en 3D que una superficie de presión aislada. La
   altura geopotencial sigue siendo necesaria para calcular e interpretar el
   contexto dinámico.
4. Una escena debe limitarse normalmente a una estructura principal, un campo
   explicativo y el terreno/contexto. La literatura de visualización destaca que
   la percepción espacial, la transparencia, el color y la iluminación requieren
   control cuidadoso [R1, R3, R4].
5. La elevación vertical debe tratarse explícitamente al preparar la escena.
   Las variables entregadas en niveles de presión representan una estructura 3D,
   pero el motor de visualización necesita una ubicación vertical coherente o una
   transformación documentada a altura/altitud de renderizado.

## 6. Productos candidatos para la etapa piloto

Estas propuestas no son todavía plantillas aprobadas. Sirven para elegir un
primer conjunto de prototipos y, a partir de ellos, cerrar la selección de
variables del conversor y de las fuentes.

| Producto | Fenómenos | Escena propuesta | Variables indispensables | Enfoque principal |
|---|---|---|---|---|
| A. Transporte de humedad andino | SALLJ, lluvia intensa, sistemas convectivos, El Niño costero | Terreno andino + partículas de bajo nivel coloreadas por humedad/IVT + volumen de nube o hidrometeoros | `u`, `v`, `w`, humedad específica; DEM; nube/hidrometeoros si existen | Operativo y didáctico |
| B. Convección y precipitación extrema | Tormentas, lluvia intensa, sistemas convectivos de mesoescala | Volumen de condensado/reflectividad + trayectorias de viento + ascenso vertical + terreno | Hidrometeoros o reflectividad, `u`, `v`, `w`, temperatura y humedad | Didáctico; operativo como exploración de estructura |
| C. DANA y circulación de altura | DANA, vaguadas aisladas, nevadas asociadas, frentes y otros sistemas sinópticos | Isosuperficie de `PV` o vorticidad + chorro como isosuperficie de rapidez + nubes/humedad + terreno | Temperatura, altura geopotencial, `u`, `v`, `w`, humedad; `PV`/vorticidad/temperatura potencial derivadas | Operativo y didáctico |
| D. Chorro y conexión trópico-extratrópico | Sistemas sinópticos, transporte de humedad, DANA | Isosuperficie de rapidez de viento, coloreada por presión/temperatura potencial, con trayectorias | `u`, `v`, temperatura, altura geopotencial; rapidez y temperatura potencial derivadas | Operativo |
| E. El Niño costero: ambiente favorable a lluvia | FEN costero y lluvias de Piura/norte | Océano y terreno + flujo oeste de bajo nivel coloreado por humedad + nubes/hidrometeoros + ascenso | `u`, `v`, `w`, humedad, temperatura, nubes/hidrometeoros; SST y precipitación como contexto | Ambas |
| F. Masa de aire fría y heladas | Heladas, ingresos fríos y eventos altoandinos | Terreno + isosuperficie o volumen de temperatura potencial + trayectorias de viento + humedad | Temperatura, humedad, `u`, `v`, `w`, DEM; temperatura potencial derivada | Operativo y didáctico |

Los productos A, B y C son los mejores candidatos para una primera iteración:
abarcan el transporte de humedad y la orografía sudamericana, la convección de
alto impacto y la escala sinóptica/DANA. Además, permiten separar claramente
qué campos son disponibles en cada fuente sin reducir la propuesta al conjunto
común de modelos.

## 7. Aplicación a los eventos priorizados

### DANA y otros sistemas sinópticos

Las fuentes revisadas describen las bajas aisladas como sistemas de niveles
medios y altos, asociados a mínimos de altura geopotencial, circulación
ciclónica, vorticidad relativa y, en enfoques dinámicos, valores altos de `PV`
relacionados con una tropopausa anómalamente baja [R10-R13]. Una animación 3D
de DANA debe, por tanto, priorizar la estructura de altura (`PV`/vorticidad o
rapidez del viento) y no sólo la lluvia observada o pronosticada en el suelo.
Nubes, humedad y precipitación contextualizan el impacto potencial.

### Convección y lluvias intensas

La evidencia de VAPOR, WRF y renderizado físico de tormentas prioriza
hidrometeoros y reflectividad para construir la geometría de la nube/tormenta
[R3, R6, R8, R9]. El viento 3D y `w` muestran organización, entrada de humedad
y ascenso. Cuando esos campos no existen, una escena de humedad relativa y
trayectorias puede ser útil para explicar el ambiente favorable, pero no debe
presentarse como una representación directa de la nube o la precipitación.

### Andes, chorro de bajo nivel y transporte de humedad

Los estudios del SALLJ señalan que los chorros de bajo nivel al este de los
Andes transportan humedad y modulan convección y precipitación extrema en
Sudamérica [R15-R18]. Por ello, `u`, `v`, humedad específica y el flujo de
humedad son variables centrales; `w`, el terreno y los hidrometeoros explican
el ascenso y el resultado convectivo. Este caso justifica que el DEM no sea un
adorno, sino un componente de la explicación física.

### El Niño costero y lluvia en la costa norte del Perú

La literatura regional indica que los episodios de lluvia intensa de Piura y el
norte peruano se relacionan con SST costera cálida, flujo oeste de bajo nivel,
aporte de humedad, nubosidad/convección y ascenso sobre la vertiente occidental
de los Andes [R14, R19-R21]. La SST debe tratarse como superficie oceánica de
contexto; la estructura tridimensional principal debe ser el viento húmedo, el
ascenso y la nube o el hidrometeoro.

### Heladas e ingresos de aire frío

Una animación útil no debe limitarse a la temperatura a 2 m. El volumen o una
isosuperficie de temperatura potencial, junto con viento, humedad y topografía,
permite mostrar el espesor, movimiento y posible acumulación de aire frío. Es
un producto aplicable al pronóstico y especialmente apto para comunicación
cuando se asocia con el relieve altoandino.

## 8. Requisitos que se deberán verificar después, por fuente y modelo

La investigación no restringe variables a un modelo, pero cada producto elegido
deberá pasar una verificación concreta antes de producción:

1. Que el campo exista para el modelo, dominio, ciclo y horizonte de pronóstico
   que se va a usar.
2. Que sea tridimensional y tenga niveles suficientes para la escena; las
   variables de superficie sólo pueden cumplir función contextual.
3. Que sus unidades, definición física y acumulación temporal estén documentadas
   (en especial precipitación, `w`, nubosidad e hidrometeoros).
4. Que tenga coordenadas horizontales y verticales compatibles con la escena y
   el terreno.
5. Que el campo sea científicamente comparable sólo cuando se pretenda comparar
   modelos; de lo contrario, cada producto debe etiquetar con claridad la fuente
   utilizada.
6. Que el rendimiento de lectura, preparación y renderizado sea aceptable para
   una animación reproducible. Los trabajos sobre volumen y publicación web
   advierten que los campos 3D dependientes del tiempo son voluminosos [R4, R5].

## 9. Próxima actividad propuesta

1. Validar con el equipo meteorológico los tres primeros productos piloto (A,
   B y C) o sustituir alguno por un caso institucional prioritario.
2. Inventariar, por cada fuente disponible, los campos requeridos por esos
   productos sin descartar opciones que sólo existan en una fuente.
3. Preparar una ficha por producto: fenómeno, variables, diagnósticos derivados,
   técnica 3D, paleta/transparencia, cámara, duración y criterio de aceptación.
4. Probar una escena corta por producto antes de procesar corridas completas.
5. Incorporar en el informe final imágenes o fotogramas de los prototipos y la
   referencia exacta de las fuentes de datos/modelos que finalmente se usen.

## 10. Registro de fuentes consultadas

La siguiente bibliografía conserva las páginas y artículos que sustentan esta
revisión. `Uso` indica el rol que tuvo en el análisis, no una aprobación de un
software o modelo particular.

| ID | Fuente | Tipo y uso |
|---|---|---|
| R1 | Rautenhaus, M., Kern, M., Schäfler, A. y Westermann, R. (2015). [Three-dimensional visualization of ensemble weather forecasts – Part 1: The visualization tool Met.3D](https://doi.org/10.5194/gmd-8-2329-2015). *Geoscientific Model Development*, 8, 2329-2353. | Artículo revisado por pares. Uso de isosuperficies de viento, `PV`, percepción espacial y aplicación a pronóstico, investigación y enseñanza. |
| R2 | Schäfler, A. y Rautenhaus, M. (2023). [Interactive 3D Visual Analysis of Weather Prediction Data Reveals Midlatitude Overshooting Convection during the CIRRUS-HL Field Experiment](https://doi.org/10.1175/BAMS-D-22-0103.1). *Bulletin of the American Meteorological Society*, 104, E1426-E1434. | Artículo revisado por pares. Caso operativo con IFS y campos 3D de temperatura, humedad, viento, `PV`, agua líquida y hielo de nube. |
| R3 | Li, S., Jaroszynski, S., Pearse, S., Orf, L. y Clyne, J. (2019). [VAPOR: A Visualization Package Tailored to Analyze Simulation Data in Earth System Science](https://doi.org/10.3390/atmos10090488). *Atmosphere*, 10(9), 488. | Artículo revisado por pares. Volumen, isosuperficie y flujo para datos atmosféricos variables en el tiempo; caso de tormenta simulada. |
| R4 | Liang, J., Gong, J., Li, W. e Ibrahim, A. N. (2014). [Visualizing 3D atmospheric data with spherical volume texture on virtual globes](https://doi.org/10.1016/j.cageo.2014.03.015). *Computers & Geosciences*, 68, 81-91. | Artículo revisado por pares. Renderizado volumétrico, escalamiento vertical e integración con terreno y objetos geográficos. |
| R5 | Robinson, N. H., Prudden, R. y Arribas, A. (2017). [A New Approach to Streaming Data from the Cloud](https://doi.org/10.1175/BAMS-D-16-0120.1). *Bulletin of the American Meteorological Society*, 98(11), 2280-2283. | Artículo técnico revisado por pares. Volumen 3D de fracción nubosa y condicionantes de publicación web de datos atmosféricos grandes. |
| R6 | Riley, K., Ebert, D., Hansen, C. y Levit, J. (2004). [A System for Realistic Weather Rendering](https://ams.confex.com/ams/84Annual/techprogram/paper_73147.htm). AMS IIPS. | Ponencia técnica. Renderizado volumétrico de agua de nube, hielo, lluvia, nieve y graupel para WRF; uso para pronóstico, investigación y educación. |
| R7 | Treinish, L. (2000). [Multi-Resolution Visualization Techniques for Nested Weather Models](https://doi.org/10.1145/375213.375319). *IEEE Visualization 2000*, 513-516. | Artículo de conferencia. Líneas de corriente 3D, campos escalares y topografía en modelos de mesoescala anidados. |
| R8 | NCAR/WRF. [Chapter 9: Post-Processing Utilities - VAPOR](https://www2.mmm.ucar.edu/wrf/users/docs/user_guide_v4/v4.1/users_guide_chap9.html). | Documentación técnica primaria. Volumen de temperatura, vapor y nubes; líneas de corriente y trayectorias 3D. |
| R9 | NCAR/WRF. [Single Domain Run - WRF Tutorial](https://www2.mmm.ucar.edu/wrf/wrf_tutorial/single_domain.html). | Documentación técnica primaria. Ejemplo de variables 4D: `QVAPOR`, `QCLOUD`, `QRAIN`, `QICE`, `QSNOW`; y componentes de viento. |
| R10 | [Seamless Detection of Cutoff Lows and Preexisting Troughs](https://doi.org/10.1175/MWR-D-20-0255.1) (2021). *Monthly Weather Review*, 149(9). | Artículo revisado por pares. Diagnóstico de bajas aisladas mediante altura geopotencial, vorticidad y `PV`; relación con lluvia intensa. |
| R11 | [Climatological Features of Cutoff Low Systems in the Northern Hemisphere](https://doi.org/10.1175/JCLI3386.1) (2005). *Journal of Climate*, 18(16). | Artículo revisado por pares. Describe diagnóstico mediante mínimos de altura geopotencial, viento, temperatura y `PV`. |
| R12 | [Sensitivity of identifying cut-off lows in the Southern Hemisphere using multiple criteria](https://d-nb.info/1205714073/34) (2019). | Artículo científico. Compara altura geopotencial y vorticidad relativa para identificar sistemas de baja aislada en el hemisferio sur. |
| R13 | Choquehuanca, B. et al. [A study on cut-off lows](https://sedici.unlp.edu.ar/bitstream/handle/10915/181971/Documento_completo.pdf%3Fsequence%3D1). | Estudio regional. Ejemplos de pronóstico con altura geopotencial, viento en 300 hPa y precipitación acumulada en Sudamérica. |
| R14 | Takahashi, K. (2004). [The atmospheric circulation associated with extreme rainfall events in Piura, Peru, during the 1997-1998 and 2002 El Niño events](https://doi.org/10.5194/angeo-22-3917-2004). *Annales Geophysicae*, 22, 3917-3925. | Artículo revisado por pares. Lluvias en Piura, SST, flujo oeste de bajo nivel y levantamiento orográfico. |
| R15 | Jones, C., Mu, Y., Carvalho, L. M. V. et al. (2023). [The South America Low-Level Jet: form, variability and large-scale forcings](https://www.nature.com/articles/s41612-023-00501-4). *npj Climate and Atmospheric Science*, 6, 175. | Artículo revisado por pares. Chorro de bajo nivel como conducto de humedad y modulador de precipitación sudamericana. |
| R16 | Montini, T. L., Jones, C. y Carvalho, L. M. V. (2019). [The South American Low-Level Jet: A New Climatology, Variability, and Changes](https://doi.org/10.1029/2018JD029634). *Journal of Geophysical Research: Atmospheres*. | Artículo revisado por pares. Viento, cizalladura y transporte integrado de humedad en SALLJ. |
| R17 | [Assessing the Moisture Transports Associated With Nocturnal Low-Level Jets in Continental South America](https://doi.org/10.3389/fenvs.2021.657764) (2021). *Frontiers in Environmental Science*. | Artículo revisado por pares. Transporte de humedad, chorros de bajo nivel y convección sudamericana. |
| R18 | Mu, Y. et al. (2025). [Impacts of Northerly Low-Level Jets on Mesoscale Convective Systems East of the Andes](https://doi.org/10.1029/2025JD043842). *Journal of Geophysical Research: Atmospheres*. | Artículo revisado por pares. Vincula chorro, flujo de humedad, ascenso, orografía, convección y lluvia intensa. |
| R19 | Douglas, M. W., et al. (2009). [Synoptic Variability of Rainfall and Cloudiness along the Coasts of Northern Peru and Ecuador during the 1997/98 El Niño Event](https://doi.org/10.1175/2008MWR2191.1). *Monthly Weather Review*, 137, 116-136. | Artículo revisado por pares. Vincula lluvia costera, anomalías de viento oeste y nubosidad. |
| R20 | [Unprecedented Rainfall and Moisture Patterns during El Niño 2016 in the Eastern Pacific and Tropical Andes: Northern Perú and Ecuador](https://doi.org/10.3390/atmos10120768) (2019). *Atmosphere*, 10(12), 768. | Artículo revisado por pares. Vapor integrado, convergencia de humedad y circulación regional para lluvia en norte peruano y Ecuador. |
| R21 | [Behavior of the ITCZ second band near the Peruvian coast during the 2017 coastal El Niño](https://www.revistascca.unam.mx/atm/index.php/atm/article/view/53017) (2022). *Atmósfera*. | Artículo científico. Precipitación, viento superficial, SST y variables en niveles isobáricos durante el Niño costero. |
| R22 | SENAMHI. [Presentación técnica sobre la DANA “Tania” y nevadas de mayo de 2021](https://www.senamhi.gob.pe/load/file/02264SENA-9.pdf). | Material institucional regional. Ejemplo de uso conjunto de vorticidad relativa y altura geopotencial a 500 hPa, humedad amazónica y precipitación/nieve. |
| R23 | National Oceanic and Atmospheric Administration. [A new visualization system for displaying NOAA weather data](https://ams.confex.com/ams/96Annual/webprogram/Paper285592.html) (2016). | Ponencia técnica. Partículas para viento GFS en un globo 3D y capas de temperatura, presión, humedad y precipitación. Se registra como antecedente de difusión, no como evidencia científica principal. |
| R24 | Treinish, L. A. [Interactive, Web-Based Three-Dimensional Visualizations of Operational Mesoscale Weather Models](https://ams.confex.com/ams/pdfpapers/27770.pdf) (2002). AMS IIPS. | Ponencia técnica. Antecedente de visualización 3D web orientada a análisis de modelos operativos. |

### Fuentes revisadas pero no usadas como base de la recomendación

- [Improving the Display of Wind Patterns and Ocean Currents](https://doi.org/10.1175/BAMS-D-13-00135.1), BAMS (2014): aporta principios perceptuales de viento, pero se centra en flujos 2D; se conserva como referencia secundaria, no como propuesta de producto.
- [Atmospheric Data Visualization in Mixed Reality](https://doi.org/10.1175/BAMS-D-15-00259.1), BAMS (2017): antecedente de percepción inmersiva, no necesario para la plataforma ni para los productos del TDR.
- [Graphics processing unit-based dynamic volume rendering for typhoons on a virtual globe](https://doi.org/10.1080/17538947.2014.915349): se revisó sólo por su técnica de volumen; el caso de huracán queda fuera del ámbito temático del proyecto.

## 11. Nota para el informe entregable

Antes de presentar el informe como versión final, se debe añadir: (i) la fecha
de corte definitiva de la bibliografía, (ii) las fuentes específicas de los
modelos que se seleccionen, (iii) una tabla de disponibilidad real de variables
por producto y fuente, y (iv) capturas o enlaces a los prototipos generados.
La presente revisión es la justificación técnica inicial de por qué esas
variables y técnicas 3D deben evaluarse.

## 12. Referentes de gráficos meteorológicos 3D: casos y productos documentados

**Fecha de esta ampliación:** 25 de septiembre de 2026  
**Propósito:** identificar precedentes verificables de escenas meteorológicas
tridimensionales, tanto en la documentación de eventos como en productos de uso
operativo. Esta sección se agrega sin modificar la selección técnica ni la
bibliografía anterior.

### 12.1 Criterio estricto de inclusión

Sólo se incluyen como referentes principales los casos que documenten al menos
uno de los siguientes elementos en el espacio físico de la atmósfera:

- renderizado de un volumen atmosférico o una isosuperficie;
- partículas, trayectorias o líneas de corriente integradas desde un campo de
  viento tridimensional;
- estructura atmosférica situada verticalmente sobre el relieve o una referencia
  geográfica coherente;
- una aplicación 3D que declare las variables y la tecnología de renderizado.

Se excluyen de la tabla principal los visores que sólo animan campos de
superficie sobre un globo, aunque la cámara tenga perspectiva. También se
excluyen los productos que se autodenominan “3D” sin describir su componente
vertical, las variables o la técnica usada. Este criterio es importante para no
confundir una interfaz atractiva con una visualización atmosférica 3D.

Los estados utilizados son:

- **Operativo documentado:** existe evidencia de empleo institucional o
  comercial para una tarea recurrente o de toma de decisiones.
- **Prueba operacional / campaña:** se empleó con pronósticos para apoyar una
  misión o se evaluó por pronosticadores, pero no se demuestra que sea un
  producto diario vigente.
- **Caso científico o demostrador:** documenta una técnica y un evento, sin
  afirmar uso operacional rutinario.

### 12.2 Casos y productos que cumplen el criterio

| Referente | Institución / estado | Gráfico 3D y variables documentadas | Herramienta declarada | Lectura para este proyecto |
|---|---|---|---|---|
| Análisis de predicciones de conjunto para la campaña T-NAWDEX-Falcon (2012) | TUM, DLR y ECMWF. **Prueba operacional / campaña.** | Isosuperficies de rapidez del viento para el chorro, `PV`, trayectorias y campos de pronóstico de conjunto; la escena sirve para localizar estructuras que interesan a la planificación de vuelo [R1, R27]. | **Met.3D**, con GPU y datos de conjunto ECMWF. | Es el referente más directo para un producto de DANA/chorro o sistemas sinópticos: una estructura dinámica 3D central, variables auxiliares y animación temporal. |
| CIRRUS-HL: convección sobresaliente de latitudes medias (2021; publicación 2023) | DLR y colaboradores; uso de predicciones operativas IFS durante una campaña. **Prueba operacional / campaña.** | Estructuras de tropopausa y nubes en 3D; campos 3D de temperatura, humedad, viento, `PV`, agua líquida y hielo de nube [R2]. | **Met.3D**. | Demuestra un caso documentado en el que nube/hidrometeoros y dinámica de altura se combinan para explicar convección; es transferible a lluvia intensa, no al fenómeno geográfico específico. |
| VISUAL en la oficina central del DWD | Deutscher Wetterdienst, Offenbach. **Operativo documentado histórico** (prototipo evaluado en operación diaria en 1997). | Renderizados 3D de campos de modelo con orientación espacial, perspectiva y proyecciones/sombras; el documento identifica como diagnósticos de interés `PV`, advección de temperatura, nubes, turbulencia y relieve [R29]. | **VISUAL**, software meteorológico propio del DWD. | Evidencia histórica de que el valor operativo aumenta cuando se usan configuraciones fijas por tarea; no debe interpretarse como un producto público vigente. |
| D3D en oficinas del National Weather Service | NOAA Forecast Systems Laboratory y NWS. **Prueba operacional histórica** en oficinas WFO y centros regionales. | Datos de modelo en tiempo real en una estación interactiva 3D; la documentación muestra un navegador de volúmenes y edición de una isosuperficie de vorticidad [R30, R31]. | **D3D**, construido sobre **Vis5D**. | Precedente de transición investigación-operación. También advierte que la capacitación y productos preconfigurados son necesarios para que el 3D sea utilizado por pronosticadores. |
| Portal con productos NWP 3D prerenderizados | Investigación de Koutek y van der Neut. **Prototipo para evaluación operacional**, no producto institucional confirmado. | Productos 3D de corridas NWP, prerenderizados para navegación rápida y con vistas VR; se diseñó para que los pronosticadores prueben configuraciones asociadas a fenómenos [R32]. | Arquitectura propia de granja de renderizado; no declara ParaView, VAPOR ni Met.3D como motor de producto. | Referencia directa para la futura plataforma web: procesar y almacenar el producto audiovisual antes de servirlo es más realista que renderizar el volumen completo en cada navegador. |
| Visualización 3D de WRF de alta resolución en Chicago/O’Hare | Raytheon, TACC y NCAR. **Caso científico de meteorología severa.** | Simulación WRF de alta resolución; la canalización lee datos HDF5, desestaggera variables y reconstruye coordenadas geográficas y elevación [R35]. | **ParaView**, con importador específico. | Evidencia útil para el componente de producción: ParaView puede manejar datos de modelo con terreno y malla atmosférica, pero la geometría vertical debe prepararse correctamente. |
| Viento 3D alrededor del monte Troodos | Cyprus Institute / Kitware. **Caso científico y de divulgación.** | Campo de viento 3D de WRF alrededor y a través de montaña; se restaura la topología de niveles que siguen el terreno antes de renderizar [R36]. | **ParaView** y filtro programable. | Referencia muy próxima al caso andino: el relieve no debe quedar separado del volumen. La transformación de coordenada presión/eta a geometría de renderizado es una condición técnica explícita. |
| MEVA: exploración y comparación de corridas WRF | Helmholtz Centre for Environmental Research y colaboradores. **Caso científico con evaluación de usuarios.** | Geometrías 3D precomputadas, entre ellas isosuperficies y líneas de corriente; permite animar, cambiar opacidad y comparar corridas [R37]. | **ParaView** para extraer geometrías y **Unity** para la aplicación de presentación. | Muestra una separación útil: motor científico para obtener objetos 3D verificables y motor de presentación para cámara, interacción y comunicación. |
| VAPOR y simulación de tornado F5 | NCAR, University of Wisconsin-Madison y modelo CM1. **Caso científico/documentación de herramienta.** | Tubos y estructuras tridimensionales de viento dentro de una simulación de tornado; el producto fue publicado como animación y visualización científica [R33]. | **VAPOR**. | El evento queda fuera del alcance sudamericano definido para el proyecto, pero el caso valida VAPOR para flujo 3D, volúmenes y animación de fenómenos severos. |
| Ejemplos WRF-VAPOR de aire frío, estancamiento, convección y vórtices | NCAR/WRF. **Demostrador técnico y capacitación.** | Volumen, isosuperficie, integración de flujo, animación y terreno para distintos fenómenos de WRF; incluye embalsamiento de aire frío y convección [R34]. | **VAPOR**. | Aunque no constituye un servicio meteorológico, es evidencia primaria de que los productos propuestos para heladas, viento-terreno y convección son realizables con datos de modelos. |
| McIDAS-V: ejemplo GFS en topografía | Space Science and Engineering Center, University of Wisconsin-Madison. **Herramienta científica de análisis y enseñanza.** | Agua precipitable GFS sobre topografía, líneas de corriente a 200 hPa e isosuperficie de 40 m s-1; carga GRIB/NetCDF y permite exportar animaciones [R38]. | **McIDAS-V**, basado en VisAD e IDV. | Referencia secundaria para chorro y transporte de humedad. No se adopta como motor previsto, pero confirma la combinación física de estas variables en una escena 3D. |
| 3D ARVI para despacho aeronáutico | MTI Ltd., con conocimiento operativo de ANA y tecnología de JAXA. **Producto comercial operativo declarado.** | Renderizado 3D de lluvia, viento, nubes, temperatura, rayos y turbulencia para información de vuelo; incluye zonas de riesgo de rayo inducido por aeronave [R39]. | Tecnología de renderizado 3D de **MTI**; el motor de software no se publica. | Es el referente comercial más claro de uso operativo de una escena 3D multivariable. Muestra que el producto debe responder a una decisión concreta, no solamente exhibir datos. |
| StormQuant en el Centro de Operaciones de Emergencia de Florida | StormQuant y Florida Division of Emergency Management. **Producto comercial operativo declarado.** | Mosaico 3D de radar en tiempo real, velocidad de viento, secciones a varias alturas y alertas para meteorólogos de emergencia [R40]. | Tecnología propietaria **StormQuant**. | Es operacional, pero su fuente central es radar y no salida de un modelo numérico. Sirve como referencia de interfaz y decisión, no como plantilla directa del flujo GRIB2–NetCDF. |

### 12.3 Productos no aceptados como referente 3D principal

El buscador de Meteomatics presenta una “3D Weather Map” y muestra una tormenta
pronosticada por EURO1k; sin embargo, la misma página describe el producto como
una **vista de mapa de alta resolución** y no documenta un volumen, isosuperficie,
trayectoria 3D ni la geometría vertical utilizada [R41]. Por ello no se lo
considera un referente técnico de animación atmosférica 3D hasta disponer de una
descripción más precisa.

La búsqueda tampoco identificó, dentro de las páginas institucionales revisadas,
un producto público y actual de un servicio meteorológico sudamericano que
cumpla el criterio estricto de esta sección. Este resultado sólo expresa el
alcance de las fuentes examinadas; **no prueba que tal producto no exista**. Si
SENAMHI u otro servicio proporciona una referencia interna, un video o una
herramienta no indexada, debe incorporarse como fuente adicional antes de cerrar
el informe.

### 12.4 Lectura comparativa: qué se observa en la práctica

1. Los productos 3D documentados para pronóstico rara vez son el producto
   público principal de un servicio meteorológico. Aparecen con mayor frecuencia
   en apoyo experto a campañas, aviación, meteorología severa, gestión de
   emergencias o exploración de modelos.
2. Los casos operativos de DWD, NOAA y los estudios de Met.3D coinciden en que
   el 3D debe estar preconfigurado para una pregunta meteorológica concreta. Un
   visor general con muchas opciones no asegura adopción por un pronosticador
   bajo presión de tiempo [R27, R29-R32].
3. Los referentes de mayor madurez operacional no utilizan una única variable:
   combinan una estructura 3D principal con variables interpretativas. Por
   ejemplo, una nube/hidrometeoro con viento y temperatura; o una superficie de
   chorro/PV con altura, humedad y trayectorias.
4. La mayoría de productos comerciales no divulga el motor ni la transformación
   exacta de sus datos. Deben servir para estudiar la necesidad de usuario y el
   lenguaje visual, pero no para justificar decisiones científicas o de
   arquitectura sin una fuente técnica independiente.
5. Para el TDR, el espacio menos cubierto por referentes públicos es la
   combinación de fenómenos sudamericanos, topografía andina y productos 3D
   reproducibles. Esa ausencia es una oportunidad de diferenciación, pero exige
   validar cada escena con el especialista meteorológico antes de presentarla
   como guía de pronóstico.

### 12.5 Implicancias para las herramientas consideradas en el proyecto

| Herramienta | Evidencia encontrada | Mejor papel en el flujo propuesto | Límite a considerar |
|---|---|---|---|
| **ParaView** | Casos WRF de meteorología severa, viento-terreno, y aplicación MEVA muestran importación, isosuperficies, trayectorias y exportación de geometrías [R35-R37]. | Motor principal de preparación visual y renderizado reproducible para animaciones de alta calidad: DEM, isosuperficies, volumen y flujo. | No debe asumir que una coordenada de presión o niveles que siguen el terreno ya tienen geometría física correcta; requiere una etapa explícita de coordenada vertical. |
| **VAPOR** | NCAR documenta importación directa de WRF, renderizado de volumen, isosuperficie, flujo, variables derivadas y animación; existen casos de convección, aire frío y tormentas [R33-R34]. | Exploración rápida de campos 3D y ajuste de umbrales, transparencia y combinaciones de variables; útil para validar la idea meteorológica de un producto antes de automatizarlo. | Es una plataforma científica interactiva. La identidad visual institucional y la automatización de un video final deben evaluarse con pruebas propias. |
| **Met.3D** | Casos con datos ECMWF/DWD, `PV`, trayectorias, volumen e isosuperficies; uso en campañas y conexiones con Metview [R25-R28]. | Referente y posible herramienta de análisis para productos de escala sinóptica, DANA, chorro y predicción de conjunto. | Es especializada en análisis meteorológico y conjuntos; no debe asumirse como motor de acabado audiovisual sin validar su integración con las fuentes y el flujo del proyecto. |
| **Blender** | En esta búsqueda no se halló un caso institucional u operacional de modelos meteorológicos que documente Blender como motor científico de la escena. | Posible etapa posterior de composición, iluminación, cámara, rótulos y acabado visual después de producir objetos/campos verificados en ParaView u otro motor científico. | No debe ser la única fuente de la geometría o transformación meteorológica: se debe conservar trazabilidad al campo científico de origen. |
| **Motor web propio / presentación prerenderizada** | El prototipo de Koutek y van der Neut demuestra que la precalculación favorece una respuesta rápida para productos 3D de NWP [R32]. | Publicación de videos, fotogramas, vistas 3D simplificadas o catálogos en la futura plataforma piloto. | No sustituye la creación científica de la escena y puede requerir infraestructura adicional; su selección se difiere a la fase de plataforma. |

### 12.6 Consecuencia para la selección de los primeros prototipos

Los referentes confirman que el primer prototipo no debería ser un visor genérico
con todas las variables disponibles. Debe responder a una historia atmosférica
concreta y dejar trazables sus campos. Se mantienen como prioridades:

1. **Transporte de humedad y relieve andino:** trayectorias de viento 3D,
   humedad/flujo de humedad, ascenso y topografía. Tiene sustento regional y
   precedentes técnicos de ParaView y VAPOR.
2. **Convección y lluvia intensa:** volumen o isosuperficie de condensado,
   hidrometeoros o reflectividad con viento 3D. Es el producto de mayor impacto
   visual, pero depende de disponibilidad de microfísica o de un sustituto
   físicamente defendible.
3. **DANA, chorro y sistema sinóptico:** isosuperficies de `PV` o rapidez de
   viento, coloreadas por una variable termodinámica y complementadas por nubes
   o humedad. Es el producto con mejor antecedente para análisis de pronóstico
   experto mediante Met.3D.

Para cada prototipo se deberá guardar la receta completa de la escena: fuente,
modelo, corrida, variable, unidades, fórmula de diagnósticos derivados,
umbral de isosuperficie/transferencia de opacidad, exageración vertical,
trayectorias iniciales, cámara, iluminación y duración. Éste es el puente entre
un ejemplo de referencia y un producto institucional reproducible.

### 12.7 Fuentes añadidas para esta sección

| ID | Fuente | Tipo y uso |
|---|---|---|
| R25 | [Met.3D - Interactive 3D visualization of gridded atmospheric datasets](https://met3d.wavestoweather.de/). | Página oficial del proyecto. Documenta la herramienta, las técnicas 3D y el ejemplo de plantillas con datos abiertos del DWD. |
| R26 | ECMWF (2022). [Met.3D: Interactive 3D visualization for rapid exploration of atmospheric ensemble simulation data](https://events.ecmwf.int/event/296/contributions/3242/). | Presentación de ECMWF. Declara integración con Metview y usos de investigación y operación. |
| R27 | Rautenhaus, M., Grams, C. M., Schäfler, A. y Westermann, R. (2014). [GPU based interactive 3D visualization of ECMWF ensemble forecasts](https://www.ecmwf.int/sites/default/files/elibrary/012014/14581-newsletter-no138-winter-201314_1.pdf). *ECMWF Newsletter*, 138. | Artículo institucional. Caso TNF, propósito de pronóstico y campos de conjunto en Met.3D. |
| R28 | DLR. [AVATAR-T](https://www.dlr.de/en/pa/research-transfer/projects/completed-projects/avatar-t). | Página institucional. Documenta uso de Met.3D para combinar viento, aerosoles y nubosidad durante planificación de campaña. |
| R29 | Koppert, H.-J. et al. (1997). [3D Visualisation in Daily Operation at the DWD](https://www.ecmwf.int/sites/default/files/elibrary/1997/10532-3-d-visualisation-daily-operation-deutscher-wetterdienst.pdf). | Documento de operación meteorológica. Prototipo VISUAL evaluado en la oficina central del DWD. |
| R30 | Szoke, E., Grote, H., McCaslin, P. y McDonald, P. (2001). [D3Ds: Using 3D visualization and other Vis5D tools in an operational forecast office](https://www.ecmwf.int/en/elibrary/76553-d3ds-using-3d-visualization-and-other-v1s5d-tools-operational-forecast-office). | Ponencia ECMWF. Documento de evaluación operacional de D3D/Vis5D. |
| R31 | Watson, A. I., Fournier, J. D., Lericos, T. P. y Szoke, E. [The Use of D3D When Examining Tropical Cyclones](https://www.weather.gov/tae/research-d3d-ams-trop-web). NOAA/NWS. | Caso de NWS. Se usa sólo como evidencia de la estación D3D y Vis5D; el fenómeno de ciclón tropical no pertenece al alcance temático del proyecto. |
| R32 | Koutek, M. y van der Neut, I. (2018). [Web-based 3D Meteo Visualization: 3D Rendering Farms from a New Perspective](https://doi.org/10.2312/envirvis.20181132). *Workshop on Visualisation in Environmental Sciences*. | Artículo de conferencia. Prototipo web para productos 3D prerenderizados de corridas NWP operativas. |
| R33 | NCAR (2015). [A 3D window into a tornado](https://news.ucar.edu/21089/3d-window-tornado). | Nota institucional. Caso de visualización VAPOR de una simulación CM1; se usa como referencia de técnica, no de fenómeno prioritario. |
| R34 | NCAR/WRF. [WRF Post-processing - VAPOR](https://www2.mmm.ucar.edu/wrf/site/users_guide/post_processing.html). | Documentación primaria. Capacidades 3D y ejercicios para WRF: volumen, isosuperficie, flujo, variables derivadas y animación. |
| R35 | Liu, S., Foss, G., Abram, G. y Bowen, A. (2015). [Visualization of High-Resolution Weather Model Data](https://doi.org/10.2312/pgv.20151156). *Eurographics Symposium on Parallel Graphics and Visualization*, 63-66. | Artículo de conferencia. WRF de alta resolución y canalización ParaView en el entorno de O’Hare. |
| R36 | Miani, M. y Proestos, Y. (2022). [Scientific visualization of Weather Research and Forecasting model output in ParaView](https://www.kitware.com/scientific-visualization-of-weather-research-and-forecasting-model-output-in-paraview/). | Nota técnica de Kitware/Cyprus Institute. Restauración de topología vertical y ejemplo de viento 3D sobre relieve. |
| R37 | Helbig, C. et al. (2015). [MEVA - An Interactive Visualization Application for Validation of Multifaceted Meteorological Data with Multiple 3D Devices](https://doi.org/10.1371/journal.pone.0123811). *PLOS ONE*, 10(4), e0123811. | Artículo revisado por pares. Flujo ParaView–Unity con WRF, isosuperficies, trayectorias y animación. |
| R38 | SSEC (2024). [McIDAS-V](https://ams.confex.com/ams/104ANNUAL/mediafile/Handout/Session66343/McIDAS_AMS2024.pdf). | Presentación técnica. Ejemplo explícito GFS 3D con topografía, líneas de corriente e isosuperficie de viento. |
| R39 | MTI Ltd. [ARVI/3D ARVI: Aviation Weather Services](https://www.aviavi-arvi.com/en/en-news/info-en/483.html). | Página de producto comercial. Declara campos y uso aeronáutico, pero no publica el motor de renderizado. |
| R40 | StormQuant (2025). [FDEM’s State Emergency Operations Center in Tallahassee Implements StormQuant Technology](https://stormquant.com/fdems-state-emergency-operations-center-in-tallahassee-implements-stormquant-technology/). | Página de producto comercial e instalación institucional. Caso de radar 3D operativo, no de salida NWP. |
| R41 | Meteomatics. [Weather Browser - 3D Weather Map](https://www.meteomatics.com/en/3d-weather-map/). | Página de empresa revisada y excluida de los referentes principales: no documenta una técnica atmosférica 3D verificable. |
