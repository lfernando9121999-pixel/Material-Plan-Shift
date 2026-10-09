# Plan Material Shift v2.2

Programa de escritorio para Windows que **balancea el material semanal (y diario) entre destinos** de un plan de minado leído desde Excel. Mueve tonelaje entre destinos **donantes** y **receptores** dentro de cada fila, respetando las reglas rígidas de conservación, y ofrece experimentos de **reordenamiento de filas** y **asignación balanceada aleatoria**.

## Ejecutar

Doble clic en **`Plan Material Shift.exe`**. No requiere instalación. La carpeta `_internal` contiene el motor (Python, NumPy, SciPy/HiGHS y openpyxl) y debe permanecer junto al ejecutable.

| Carpeta | Uso |
|---|---|
| `Inputs` | Sugerida para los Excel de análisis (el botón de importación abre el Escritorio). |
| `Escenarios` | Escenarios guardados (`.pmsx`: inputs o inputs + resultados). |
| `Outputs` | Exportaciones: Plan Modificado y Reporte en Excel. |

## Flujo de trabajo

1. **Inputs**
   - *Input para Análisis* → **Seleccionar Archivo…** (Excel `.xlsx/.xlsm`).
   - *Hoja para Análisis*: lista de hojas del libro. La tabla empieza en la celda **«# Sec»**; la primera fila es el encabezado y se leen todas las filas con datos.
   - *Nombre del Escenario*, *Descripción* (máx. 500 caracteres sin espacios) y *Año* (se detecta en «Fecha Liberación»).
   - **Detección de Datos**: columnas detectadas y tres ventanas:
     - **A. Configuración de Fases**: fases únicas (las filas con fase vacía o 0 no se detectan).
     - **B. Configuración de Destinos**: destinos con tonelaje > 0, en el orden del Excel; *Tipo de Destino* (Mineral / Desmonte / N/A) y *Configuración* (Receptor / Donante). *Sugerir Tipo por Materiales* propone el tipo según el material que recibe cada destino.
     - **C. Configuración de Materiales**: materiales con tonelaje > 0 y su tipo (Mineral / Desmonte / N/A).
   - Los bloques **MINERAL** y **DESMONTE** resumen lo asignado; un bloque sin datos se ve gris (inactivo).
2. **Restricciones** (segunda pestaña): fases en evaluación, **Activar Balanceo** por circuito y **Matriz de Material por Destino** (qué material puede recibir y entregar cada destino).
3. **Función Objetivo** (tercera pestaña)
   - **Meta Física** (por circuito): *Modo de Cumplimiento* (Objetivo Fijo / Balanceado), *Nivel de Granularidad* (Semanal / Diario) y metas **Máximo / Promedio (Deseado) / Mínimo** en Mt (Mt = t / 1 000 000). Debajo, la **Priorización** por receptor: 1. Fases → 2. Donantes → 3. Materiales (arrastrar ≡ o Alt+↑/↓; la casilla habilita el elemento; el interruptor activa o desactiva el bloque).
   - **Experimentos** (selección única):
     1. **Convencional**: balance por programa lineal de las 52 semanas.
     2. **Reordenamiento de Filas**: Convencional + permutación del contenido de las filas dentro de cada polígono para que una proporción de polígonos inicie con mineral (casilla *Polígonos que inician con mineral (%)*, precargada en 50 %). El botón **Priorización de Destinos en la Permutación…** abre una ventana para ordenar los registros de cada polígono de arriba hacia abajo según su destino (ver abajo).
     3. **Asignación Balanceada Aleatoria**: Convencional + reparto aleatorio del tonelaje de cada fila entre los destinos del circuito (*Estricto / Moderado / Flexible*; *Semilla* para reproducir).
     4. **Optimización Integral**: Convencional + Aleatoria + Reordenamiento (en ese orden).
   - **Ejecutar Experimento** (o `F5`).
4. **Resultados**: Dashboard, Tabla, Materiales, Plan de Mina (reporte dinámico con filtros), Reordenamiento de Filas, Validación y Movimientos. Clic derecho sobre un gráfico o tabla para copiar sus datos.

## Reglas rígidas que siempre se cumplen

- **Oferta y devolución**: en una semana, un donante cede como máximo su tonelaje de cada material; un receptor devuelve como máximo su tonelaje base. El intercambio directo entre receptores solo usa el excedente sobre el objetivo semanal.
- **Conservación de masa**: el total de cada fila no cambia; las columnas de material no cambian; el total anual de cada donante y receptor se conserva exactamente.
- **Un material por fila**, que puede repartirse en varios destinos.
- **Matriz de materiales**: una combinación desmarcada nunca se modifica.

La pestaña **Validación** verifica cada regla después de cada corrida (✓ Ok / ! Revisar) y lista las semanas o días fuera de banda.

## Reordenamiento de filas

- Un **polígono** es un bloque de filas contiguas con el mismo «Polígono / Origen» (y la misma semana). Sus filas no salen del bloque.
- Se mueve como unidad el contenido desde «Total Material» hasta la última columna de material; # Sec, Semana, Fase, Malla y Polígono quedan fijos.
- Los polígonos con un solo tipo de material conservan su inicio; los que tienen ambos permiten elegir.
- **Base del porcentaje**: *Polígonos con mineral y desmonte* (los que pueden cambiar) o *Todos los polígonos de la semana*. Con la segunda opción, si una semana ya tiene todos sus polígonos mixtos iniciando con mineral y estos son menos de la mitad, el reparto factible más cercano al 50 % es el orden actual (sin cambios).
- Si una semana no permite la proporción exacta se aplica la más cercana; con empate, la que reduce el desvío acumulado y luego la que requiere menos intercambios.

## Priorización de destinos en la permutación (nuevo en v2.2)

Ventana emergente disponible en *Reordenamiento de Filas* y en *Optimización Integral* (aparece sola la primera vez que se ejecuta uno de esos experimentos):

- **Activar priorización de destinos en la permutación**: interruptor general.
- **Polígonos que Inician con Desmonte** y **Polígonos que Inician con Mineral**: una lista de destinos para cada tipo de inicio, cada una con su propio interruptor. Arrastre ≡ (o Alt+↑/↓) para ordenar; la casilla incluye o excluye el destino.
- Dentro de cada polígono, los registros quedan **de arriba hacia abajo** según el destino de mayor prioridad al que va su tonelaje. El primer registro con material siempre es del tipo de inicio que decidió el porcentaje (mineral o desmonte). Los destinos desmarcados van al final.
- Solo se permuta el contenido dentro del bloque del polígono: toneladas, semana, fase, malla, polígono y # Sec no cambian. La pestaña Reordenamiento de Filas muestra *Polígonos Cambiados* y *Filas Movidas*.

## Rendimiento (v2.2)

- Las tablas miden el ancho de las columnas con caché (antes, hasta 10 000 mediciones por vista).
- Los gráficos no se redibujan al mover la ventana ni al volver a una pestaña; al redimensionar se agrupan los redibujos.
- Al escribir (nombre, descripción, metas) ya no se reconstruye ningún elemento: sin parpadeo.
- Seleccionar un experimento, marcar fases o activar el balanceo actualiza solo lo necesario.
- Después de cargar o ejecutar, las pestañas y subpestañas se preparan en segundo plano, así que su primera apertura es inmediata.

## Atajos

| Atajo | Acción | Atajo | Acción |
|---|---|---|---|
| `Ctrl+N` | Nuevo escenario | `F5` | Ejecutar experimento |
| `Ctrl+O` | Abrir escenario | `Ctrl+E` | Exportar Plan Modificado |
| `Ctrl+S` / `Ctrl+Shift+S` | Guardar / Guardar como | `Ctrl+Shift+E` | Exportar Reporte |
| `Ctrl+W` | Cerrar escenario | `Ctrl+Shift+M` | Modo oscuro |
| `Ctrl+I` | Importar Input para Análisis | `F1` | Acerca de |

Varios escenarios pueden estar abiertos en pestañas (**+** para crear; **✕** o clic central para cerrar; **●** indica cambios sin guardar).
