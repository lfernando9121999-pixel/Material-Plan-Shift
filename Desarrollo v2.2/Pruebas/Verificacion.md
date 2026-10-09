# Verificación de Plan Material Shift v2.2

Versión nueva en carpetas propias. La v2.1 (`Desarrollo/` y `Plan Material Shift/`) no se modificó.

## Cambios de la v2.2

1. **Rendimiento y comodidad de uso**
   - **Tablas**: el ancho de las columnas se calcula midiendo solo los textos candidatos, con caché. Antes se medían hasta 10 000 textos por vista y cada medición es una llamada a Tk.
   - **Gráficos**:
     - no se redibujan al mover la ventana ni al volver a mostrar una vista;
     - al redimensionar, los redibujos se agrupan;
     - un gráfico oculto se dibuja recién al mostrarse;
     - el gráfico de polígonos dibuja los tramos contiguos del mismo color como un solo rectángulo.
   - **Sin parpadeo al escribir**:
     - la barra de pestañas de escenarios y la barra de estado se actualizan en su lugar, en vez de reconstruirse con cada tecla;
     - el año, las fases, la activación del balanceo y la matriz actualizan solo lo afectado;
     - seleccionar un experimento repinta las tarjetas sin reconstruirlas.
   - **Páginas que solo se rehacen si cambió su estructura**: Meta Física, Restricciones y la tabla de Detección de Datos se reconstruyen solo cuando cambian el archivo, las fases, los destinos, los materiales o la activación del balanceo.
   - **Preparación en segundo plano**: tras cargar o ejecutar, las pestañas y subpestañas se construyen de a una cuando no hay interacción (como en SimA), así que su primera apertura es inmediata.
   - **Desplazamiento y ajuste de texto**: ya no se re-maquetan por cambios de 1 a 2 px, lo que evita oscilaciones.
   - **Cachés por resultado**: la tabla de movimientos y los datos del Plan de Mina se calculan una sola vez.
2. **Orden de pestañas**: Inputs · **Restricciones** · **Función Objetivo** · Resultados.
3. **Priorización de destinos en la permutación** (Reordenamiento de Filas y Optimización Integral):
   - **La ventana**: aparece sola la primera vez que se ejecuta uno de esos experimentos, y en cualquier momento desde el botón *Priorización de Destinos en la Permutación…*. Tiene un interruptor general y dos listas de destinos arrastrables con su propio interruptor: *Polígonos que Inician con Desmonte* y *Polígonos que Inician con Mineral*.
   - **El orden**: dentro de cada polígono, los registros se ordenan de arriba hacia abajo según el destino de mayor prioridad al que va su tonelaje. El primer registro con material conserva el tipo de inicio que decide el porcentaje.
   - **Lo que no cambia**: no se alteran toneladas ni registros entre polígonos.
   - **Desactivada**: el resultado es idéntico al de la v2.1.

## Pruebas (Linux; en Windows se ejecutan al compilar)

| Suite | Resultado |
|---|---|
| Motor (`python -m pytest -q`) | **22/22**: las 19 de la v2.1 + priorización en Reordenamiento e Integral + «priorización inactiva = v2.1» |
| Interfaz (`prueba_interfaz.py`) | **20/20**: incluye el orden de pestañas, la ventana que aparece al reordenar y la Integral con priorización (211 polígonos con inicio cambiado y 5 263 filas movidas, todas las validaciones en Ok) |
| Rendimiento (`prueba_rendimiento.py`) | **16/16** dentro del límite |

## Rendimiento: v2.1 vs v2.2

La medición es el **bloqueo percibido**: la acción más el paso de eventos más largo hasta que la interfaz queda en reposo. Incluye los redibujos diferidos. Se tomó con el Excel de trabajo después de ejecutar la Optimización Integral, en la misma máquina.

| Medición | v2.1 | v2.2 |
|---|---|---|
| Cambio de circuito (Mineral / Desmonte) | 1 679 ms | **22 ms** |
| Primera apertura de subpestañas de Resultados (peor caso) | 1 773 ms | **29 ms** |
| Primera apertura de pestañas principales (peor caso) | 186 ms | **66 ms** |
| Cambio entre pestañas principales (peor caso) | 35 ms | **23 ms** |
| Tecla en Descripción (peor caso) | 23 ms | **3 ms** |
| Tecla en meta Promedio (peor caso) | 20 ms | **10 ms** |
| Elementos reconstruidos por tecla (parpadeo) | 12 | **0** |
| Redimensionar con el gráfico de polígonos (peor caso) | 185 ms | **68 ms** |
| Mover la ventana (peor paso) | 3.8 ms | **2.1 ms** |
| Paso más largo de la preparación en segundo plano | — | 128 ms (una sola vez, sin interacción) |

Detalle: `Resultados/rendimiento_linux_v2.1_referencia.txt` y `Resultados/rendimiento_linux_v2.2.txt`. La misma prueba se ejecuta en Windows al compilar (`Resultados/rendimiento_windows.txt`).

## Ejecutable

El flujo `.github/workflows/compilar-windows-v22.yml` (Windows, Python 3.12) ejecuta las tres suites, compila con PyInstaller, corre la prueba de humo del `.exe` (lee un Excel, ejecuta la Optimización Integral, exporta y abre la interfaz) y publica `Plan Material Shift v2.2/`.
