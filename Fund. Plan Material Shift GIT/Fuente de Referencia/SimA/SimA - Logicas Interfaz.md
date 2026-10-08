# SimA – Lógicas de Interfaz (v1.6)

> **Alcance.** Referencia funcional del front-end de **SimA – Simulation Analyst v1.6**. Describe navegación, ventanas, importación, selección, filtros, tablas, gráficos, orden y estilo visual. No documenta las fórmulas de cálculo de cada pestaña. Se elaboró a partir del código fuente de la versión 1.6 en `SimA - Simulation Analyst/Desarrollo/Codigo Fuente`.

## 1. Modelo de interacción

```text
Aplicación
├─ Ventana principal (menús, herramientas, marca y barra de estado)
│  ├─ Escenarios abiertos: pestañas independientes, + para crear
│  └─ Escenario activo
│     ├─ Panel izquierdo: Archivos del Modelo
│     └─ Pestañas de trabajo
│        ├─ Inputs y sus subpestañas
│        ├─ Vistas de análisis y sus controles
│        └─ Tablas Dinámicas
├─ Ventanas ligeras: filtros, listas y editores de celda
├─ Ventanas de herramienta: configuración y selección de inputs
└─ Diálogos de sistema: abrir, guardar, confirmar y progreso
```

Las opciones actúan sobre el **escenario activo**. Varios escenarios pueden estar abiertos simultáneamente. La aplicación inicia con un escenario nuevo y vacío; si se abre un archivo `.simx` desde Windows, se carga ese escenario. Las preferencias generales (tema, posición del panel, carpetas recientes, lista de escenarios recientes y memoria de la última corrida) se guardan entre sesiones.

## 2. Ventana principal, apertura y navegación

| Zona | Comportamiento |
|---|---|
| Barra superior | Menús **Archivo**, **Modelo**, **Tools** y **Acerca de SimA**; botones con iconos y ayuda al pasar el mouse; marca y versión a la derecha. |
| Escenarios | Cada escenario ocupa una pestaña. **+** crea uno; **×**, clic central o `Ctrl+W` lo cierran. El indicador junto al nombre señala cambios sin guardar. |
| Ventanas independientes | Arrastrar la pestaña de un escenario fuera de la barra abre otra ventana; también puede soltarse en la barra de otra ventana de SimA. El menú contextual ofrece abrir en ventana nueva, mover y cerrar. |
| Pestañas principales | Inputs, Análisis de Estados, Análisis de Tiempos, Orígenes y Destinos, Tiempos y Métricas, Plan de Mina, Plan vs Simulación y Tablas Dinámicas. La activa tiene subrayado; **»** aloja las que no caben. |
| Subpestañas | Se seleccionan con clic. Algunas muestran contadores y botones segmentados a la derecha. El control **Réplica** aparece donde corresponde; **Año** permanece visible y lleva a Inputs ▸ General. |
| Barra inferior | A la izquierda muestra mensajes temporales; a la derecha, escenario, estado de resultados, réplica, fecha de cálculo y nombre del `.simx` cuando aplica. |

La pestaña elegida permanece visible mientras se prepara la siguiente. Las vistas no visibles se marcan para actualizarse y se preparan gradualmente cuando la aplicación está inactiva. Al cambiar de pestaña se cierra el filtro emergente que no pertenece a la nueva vista. Los controles segmentados cambian de modo dentro de la pestaña (por ejemplo, **Resumen / Detallado**, **Tablas / Gráfico**, **Día / Semana / Mes**, **Dot Plot / Barra**), sin abrir un escenario nuevo.

### Opciones de Archivo

- **Nuevo** (`Ctrl+N`), **Abrir…** (`Ctrl+O`) y **Abrir Existente** con archivos recientes. La lista omite rutas inexistentes y ofrece **Limpiar Lista**.
- **Guardar** (`Ctrl+S`) y **Guardar Como…** (`Ctrl+Shift+S`) utilizan `.simx`. Un escenario ya abierto en otra ventana se activa allí en lugar de duplicarse.
- Si se cambió la configuración después del cálculo, Guardar advierte que conservará **solo la configuración**; se puede ejecutar `F5` antes de guardar resultados vigentes.
- Al cerrar con cambios aparece **Cambios sin Guardar**: Guardar, No Guardar o Cancelar. Cancelar conserva el escenario abierto.
- **Activar/Desactivar Modo Oscuro** (`Ctrl+Shift+M`) aplica a todas las ventanas. La elección se recuerda. En una ventana secundaria, **Cerrar Ventana** afecta a sus escenarios; **Salir** en la principal cierra el conjunto, respetando las confirmaciones.

### Modelo y Tools

**Modelo** reúne importar CSV, importar métricas del plan, ejecutar (`F5`), vincular o desvincular filtros, y exportar Excel, PowerPoint o Plan vs Simulación. **Tools** abre los dos pivotes y permite sacar un escenario a otra ventana. Los menús pueden abrirse con `Alt+A`, `Alt+M` y `Alt+T`. Los botones de la barra superior duplican las acciones frecuentes.

## 3. Explorador de archivos e importación

### Cuadros Abrir / Guardar

Los cuadros del Explorador de Windows se abren centrados en el monitor de la ventana activa, con tamaño medio y ajustable (aprox. 60 % del ancho y 70 % del alto disponible, dentro de límites). No se muestran antes de ubicarse. La aplicación recuerda la carpeta del último escenario y la última carpeta de CSV; en ausencia de ellas usa las carpetas del programa o el escritorio.

### Resultados de simulación CSV

1. **Modelo ▸ Importar Resultados Simulación CSV…** abre selección múltiple. El filtro del Explorador muestra `o_*.csv`.
2. Se admiten nombres que **empiecen por `o_` y terminen en `.csv`** (sin distinguir mayúsculas). Se excluyen `o_poliRetenido.csv`, `o_poliRetSolapamiento.csv` y `o_sinOrigen.csv`. Los omitidos se informan.
3. Cada archivo se inspecciona antes de cargar: existencia, codificación, separador, decimal, encabezados, tamaño y filas. Se reconocen codificaciones comunes y delimitadores coma, punto y coma, tabulación o barra vertical. Si un archivo falla, se informa su nombre y los demás pueden continuar.
4. Se abre **Inputs para Análisis**, una ventana pequeña con casillas por archivo, **Seleccionar Todo**, **Ninguno**, **Cargar** y **Cancelar**. Los archivos no encontrados se indican y no pueden seleccionarse. Si la ventana se cierra al abrir otra, los cambios de selección se aplican solo si hubo cambios.
5. La carga muestra progreso y posibilidad de cancelar. La lectura extensa se hace por bloques. Los resultados importados alimentan el panel y la configuración de Inputs.

En los datos de réplica, un encabezado `NREP` repetido y los valores que no representan réplicas válidas no se presentan como opción; la selección visible parte de la primera réplica válida. Para **Cambiar Input** se exige el mismo nombre de archivo esperado. Los archivos faltantes de un `.simx` no impiden abrir y revisar resultados guardados; para recalcular se reubican desde el panel.

### Panel «Archivos del Modelo»

Está a la izquierda. El alfiler alterna **fijo** y **ocultación automática**; en este último caso queda una tira vertical que despliega el panel al pasar el mouse. La barra de iconos permite importar, cambiar, quitar del escenario, mostrar carpeta y abrir archivo. Quitar del escenario **no borra el CSV del disco**. Las filas muestran estado incluido/excluido/no encontrado y metadatos. Se seleccionan con clic, `Ctrl`+clic, `Shift`+clic o `Ctrl+A`; el clic derecho ofrece **Abrir Archivo**. El pie resume cantidad de archivos, incluidos, tamaño y selección.

## 4. Configuración previa y orden de reporte

Las subpestañas **General**, **Configuración de Equipos** y **Origen y Destino** de Inputs se marcan como requeridas. La descripción es opcional. Ejecutar valida que los campos obligatorios, la clasificación de flotas y los estados de tiempo estén completos; si falta algo, muestra un aviso y lleva a Inputs. Los estados asignados se resumen en un cuadro pequeño junto a las flotas.

**Configuración de Tiempos** se abre como ventana de herramienta redimensionable. Permite asociar columnas del CSV a estados, muestra recuentos y comparación con la plantilla estándar, permite ordenar las columnas con el encabezado y restablecer valores por defecto. **Configuración de Destinos** y **Inputs para Análisis** usan el mismo patrón de ventana auxiliar.

El cuadro **Orden de Reporte** organiza cada clase de equipo con listas de **Tipo**, **Flota** y, donde corresponde, **Categoría**. Arrastrar un valor cambia su orden vertical; arrastrar el encabezado de una lista modifica la prioridad horizontal de las dimensiones. **Restablecer** retorna al orden predeterminado. Este orden gobierna la lectura de tablas fijas, gráficos y tablas dinámicas, y se conserva con la configuración.

En **Vector Plan**, la tabla permite buscar, muestra observaciones debajo y edita el **Indicador Simulador** o la **Variación** desde la propia celda. El selector de indicadores admite varios compatibles; las combinaciones incompatibles se deshabilitan. Las asignaciones sugeridas pueden restablecerse. No hace falta una ventana grande de «Editar Vínculos».

Al iniciar un caso nuevo, la memoria de la última corrida propone clasificación de orígenes, destinos y categoría de equipos coincidentes; el plan completo se recupera si el año coincide. Los elementos que no se repiten no se copian entre años.

## 5. Ventanas emergentes, avisos y progreso

| Tipo | Aspecto y cierre |
|---|---|
| **Emergente ligero** | Lista desplegable, filtro o editor breve. Se abre junto al control, dentro del monitor de SimA, con título arrastrable y **✕**. Solo hay uno activo: abrir otro cierra el anterior conservando lo elegido. Clic fuera o **✕** aplica; `Esc` cancela. Cambiar de pestaña cierra el que no corresponde. |
| **Ventana de herramienta** | Configuración de tiempos/destinos, selección de inputs y edición de campos pivot. Tiene marco del sistema, puede moverse/redimensionarse y deja operable la ventana principal. Se muestra centrada en el mismo monitor. Al abrir otra ventana auxiliar se resuelve la anterior según sus cambios. |
| **Aviso / error / confirmación** | Diálogo compacto con título de ventana **SimA – Simulation Analyst**, asunto dentro, icono y color por tipo; `Enter` activa la acción predeterminada, `Esc` cancela o cierra. Las confirmaciones retienen el foco hasta responder. |
| **Progreso** | Ventana con tarea, detalle, barra y, si aplica, **Cancelar**. El trabajo corre en segundo plano; al cancelar se solicita detenerlo y se informa el estado. |

La ventana de filtros no se apila sobre otras de SimA ni salta al monitor equivocado. Los mensajes breves que no exigen respuesta aparecen en la barra inferior y luego vuelven a **Listo**.

## 6. Tablas: estructura, formato y acciones

Hay dos patrones principales: **TablaDatos** para filas planas y **TablaArbol** para jerarquías. Ambas comparten encabezados centrados, valores alineados según su tipo, sangría legible, colores suaves de grupo, filas de total destacadas y barras de desplazamiento cuando hacen falta. Algunas tablas agregan un segundo nivel visual de encabezados (por ejemplo, **Total / Promedio**). Las columnas pueden redimensionarse y reordenarse arrastrando el encabezado; el orden visible se mantiene durante la sesión. El ancho se distribuye según el espacio disponible sin reducir títulos y valores por debajo de mínimos legibles.

En una **TablaArbol**, los triángulos abren o cierran niveles; el menú contextual ofrece expandir o contraer donde corresponde. En tablas normales se puede seleccionar una o varias filas. La rueda del mouse desplaza el área bajo el puntero, incluso sobre barras de desplazamiento.

**Clic en el texto del encabezado:** alterna orden ascendente → descendente → original. **Clic en el embudo del encabezado:** abre el filtro de esa columna. **Clic derecho en el encabezado:** menú para ordenar y filtrar. **Clic derecho en el cuerpo:** Copiar Selección (si existe), Copiar Tabla, Copiar Tabla con Formato o Copiar Tabla como Imagen. El formato se pega en Excel, Word o PowerPoint; en modo oscuro se usa un formato legible para Office.

## 7. Filtros de tablas y botones de gráficos

### Filtro pequeño del encabezado

El embudo abre un cuadro compacto de estilo Excel, con **Limpiar Filtro**, **(Seleccionar Todo)** y casillas. **Buscar** aparece cuando existen más de ocho valores. La búsqueda reduce la lista visible; (Seleccionar Todo) actúa sobre los valores visibles y habilitados. **Aceptar** aplica; **Cancelar** o `Esc` descarta. Clic fuera aplica la selección. Si quedan cero valores marcados, se conserva el filtro anterior para evitar una tabla vacía por accidente. Un embudo activo distingue la columna filtrada.

Los filtros activos aparecen como etiquetas con **×** y opción **Limpiar Filtros**. De forma predeterminada, **Vincular Filtros entre Tablas y Gráficos** hace que el filtro de una dimensión afecte a las tablas, tarjetas y gráficos de la misma página. Desde **Modelo** se puede desvincular: entonces cada tabla mantiene sus filtros de encabezado. Las selecciones se guardan dentro de la vista del escenario.

### Selecciones de gráfico y controles segmentados

Los botones segmentados cambian modo o nivel sin abrir otra pantalla. Ejemplos: **Tablas / Gráfico** en Análisis de Tiempos; **Dot Plot / Barra** en Tiempos y Métricas; **Día / Semana / Mes** en Plan de Mina; **Agrupadas / Apiladas** y **Vertical / Horizontal** en el gráfico pivot.

Los botones **Flotas**, **IDs**, **Mes**, **Fase**, **Tipo de Origen** y otros filtros de gráfico abren una lista con casillas. La etiqueta resume «Todas», «Todos», un valor o el número de valores elegidos. La selección se confirma al cerrar el emergente y actualiza la vista. **Limpiar Filtros** devuelve la selección completa. En Análisis de Tiempos, las selecciones de Flotas e IDs afectan el reporte gráfico; en pivotes, **Series** controla cuáles se dibujan.

El clic derecho sobre un gráfico ofrece **Copiar Datos de Gráfico**, **Copiar Gráfico como Imagen** y **Copiar Gráfico como Formato de PPT**. Esta última opción prepara un gráfico nativo editable y requiere PowerPoint instalado.

## 8. Tablas dinámicas y sus cuadros auxiliares

**Tablas Dinámicas** agrupa Análisis de Estados (Pivot) y Registro de Cargas (Pivot). El área izquierda muestra una grilla con encabezados de varios niveles, jerarquías desplegables, subtotales y un gráfico. El panel derecho reúne búsqueda de campos y cuatro zonas: **Filtros**, **Columnas**, **Filas** y **Valores**. Un campo se agrega con doble clic o se arrastra entre zonas; los chips se pueden reordenar, quitar y configurar desde su menú contextual. El arrastre muestra un indicador visual del destino.

La barra de herramientas incluye **Agregar Campo Calculado**, **Editar Expresiones**, **Formato de Campos**, **Actualizar**, **Campos Visibles**, **Opciones de Pivote**, **Expandir**, **Contraer**, **Copiar Tabla**, **Exportar a Excel** y **Limpiar**. Opciones de Pivote controla encabezados, totales, subtotales, líneas y actualización automática. El gráfico pivot tiene control para mostrarlo, tipo agrupado/apilado, orientación y selección de series.

Los cuadros pequeños permiten: filtrar valores de un campo (con valores condicionados por los demás filtros), elegir intervalos numéricos, escribir una expresión tipo Excel y definir título, formato numérico, agregación o ponderador. Los campos calculados y la disposición se conservan en el escenario. El campo **Réplica** se presenta con su nombre visible; `NREP` no se ofrece como dimensión. Al exportar el pivot se incluye su tabla y gráfico.

## 9. Estilo visual y comportamiento adaptable

- Dos temas: **claro** con fondo gris suave, paneles blancos y bordes tenues; **oscuro** con fondo profundo y texto claro. Acento azul para selección, verde para acción principal y color de aviso/error cuando corresponde. Los gráficos conservan colores semánticos por estado.
- Tipografía Segoe UI; títulos, cifras KPI, ayudas y detalles tienen jerarquía visual. Los iconos usan Segoe MDL2 Assets. Tooltips explican botones de icono y controles compactos.
- Tarjetas KPI y paneles se redistribuyen cuando disminuye el ancho. Si una tabla no cabe, ofrece desplazamiento horizontal. Las zonas de scroll se ajustan al contenido; el panel de archivos puede retraerse.
- Los gráficos y grillas demoran el redibujado al cambiar el tamaño; mover una ventana sin cambiar dimensiones no fuerza dibujar todo. Las páginas se reconstruyen fuera de vista y se publican completas para reducir parpadeos.
- La barra inferior queda reservada para estado. Los diálogos se mantienen dentro del área de trabajo del monitor correspondiente. La ventana principal admite minimizar, maximizar y acoplamiento de Windows.

## 10. Guía rápida de acciones

| Quiero… | Dónde |
|---|---|
| Abrir un escenario | Archivo ▸ Abrir… o Abrir Existente |
| Agregar resultados | Modelo ▸ Importar Resultados Simulación CSV…; luego Inputs para Análisis |
| Excluir un CSV sin borrarlo | Marca de inclusión en Archivos del Modelo |
| Configurar estados/orden | Inputs ▸ Configuración de Equipos |
| Cambiar réplica o año | Selector Réplica junto a pestañas / etiqueta Año |
| Filtrar una columna | Embudo del encabezado; para ordenar, clic en el título |
| Filtrar un gráfico | Botones con casillas encima del gráfico |
| Cambiar el alcance de filtros | Modelo ▸ Vincular/Desvincular Filtros entre Tablas y Gráficos |
| Copiar una tabla o gráfico | Clic derecho sobre el objeto |
| Desacoplar un escenario | Arrastrar su pestaña fuera o Tools ▸ Abrir Escenario en Ventana Nueva |
| Ejecutar y exportar | `F5`; Modelo ▸ Exportar Reporte Excel/PowerPoint |

---

**Fuentes inspeccionadas:** `app.py`, `config.py`, `csvio.py`, `escenario.py`, `panel_archivos.py`, `dialogo_archivos.py`, `dialogos.py`, `ui_comun.py`, `ui_github.py`, `graficos.py`, `vista_escenario.py`, `vista_inputs.py`, `vista_tiempos.py`, `vista_productividad.py`, `vista_perfil.py` y `vista_pivot.py` de la versión 1.6. Esta es una descripción del comportamiento implementado, no una especificación de nuevas funciones.
