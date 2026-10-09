# Verificación de Plan Material Shift v2.1

Pruebas internas ejecutadas el 09/10/2026 sobre el Excel de trabajo (hoja `Plan_Base`, 10 998 filas, 88 columnas) y sobre un Excel sintético generado por las pruebas. Las capturas están en `Capturas/` y las salidas en `Resultados/`.

## 1. Motor (`python -m pytest -q` → 19/19)

| Prueba | Qué verifica |
|---|---|
| `test_deteccion` | Celda «# Sec», encabezado, destinos y materiales por suma de filas, fase 0 no detectada, año más frecuente, columnas con suma 0 excluidas, bloques de polígono. |
| `test_experimentos` (8) | Los 4 experimentos × Objetivo Fijo / Balanceado: todas las validaciones rígidas en Ok, LP resuelto, movimientos > 0. |
| `test_mejora_brechas` | El Convencional reduce las semanas fuera de banda. |
| `test_diario` | El refinamiento diario conserva exactamente los totales semanales por destino. |
| `test_matriz_bloqueada` | Las celdas destino/material desmarcadas no cambian. |
| `test_prioridad_exclusion` | Un donante desmarcado en la Priorización no entrega a ese receptor. |
| `test_reordenamiento` / `_todos` | El contenido solo se permuta dentro de su polígono, como unidad; columnas fijas intactas; reparto factible más cercano por semana. |
| `test_aleatoria_reproducible_y_grados` | Misma semilla = mismo resultado; Estricto ≤ Moderado ≤ Flexible en destinos por fila; totales semana × destino iguales al Convencional. |
| `test_pmsx` | Guardar y abrir `.pmsx` con resultados. |
| `test_exportaciones` | Plan Modificado con los valores del resultado en las celdas originales y Reporte. |
| `test_excel_de_trabajo` | Columnas 14–59 (destinos) y 60–74 (materiales) en el Excel de trabajo; Convencional e Integral válidos. |

## 2. Resultados con el Excel de trabajo

Configuración de prueba: Desmonte (receptores Chw2a_1, Chw2a_2; seis donantes; Wa…Wrip) con meta 1.25 / 1.30 / 1.35 Mt/sem; Mineral (receptor Ore1; dos donantes; M1…M6) con 0.95 / 1.00 / 1.05 Mt/sem.

| Experimento | Tiempo | Movimientos | Brechas semanales Desmonte | Brechas semanales Mineral | Validaciones rígidas |
|---|---|---|---|---|---|
| Convencional · Objetivo Fijo · Semanal | 0.6 s | 3 636 | 103 → 1 | 50 → 35 | Ok |
| Convencional · Balanceado · Semanal | 0.2 s | 3 503 | 103 → 1 | 50 → 35 | Ok |
| Convencional · Objetivo Fijo · Diario | 0.7 s | 7 705 | 103 → 1 | 50 → 35 | Ok |
| Reordenamiento de Filas (50 %) | 0.2 s | 3 636 | 103 → 1 | 50 → 35 | Ok |
| Asignación Balanceada Aleatoria (Moderado) | 0.8 s | 12 462 | 103 → 1 | 50 → 35 | Ok |
| Optimización Integral | 0.8 s | 12 462 | 103 → 1 | 50 → 35 | Ok |

- Las 35 brechas de Mineral son estructurales: el receptor tiene 37.2 Mt/año en el plan y la meta pedida equivale a 52.0 Mt/año. La conservación anual exacta impide cerrar esa diferencia; el programa la informa como brecha. Con las metas que el programa propone por defecto (promedio anual del plan ÷ 52 ± 5 %: 0.68 / 0.716 / 0.752 Mt/sem) quedan 19 semanas fuera de banda, por falta de oferta de los donantes de Mineral en esas semanas.
- Destinos por fila en el circuito Desmonte: Convencional 1.65 · Estricto 1.07 · Moderado 1.78 · Flexible 2.18.

### Reordenamiento de filas (condición inicial = Graphs.xlsx)

En el plan, **los 422 polígonos que contienen mineral y desmonte inician con mineral** y hay 1 261 polígonos solo de desmonte y 40 solo de mineral (1 723 en total).

| Base del porcentaje (50 %) | Intercambios | Polígonos que inician con mineral |
|---|---|---|
| Polígonos con mineral y desmonte (predeterminada) | 211 | 462 → 251 (en cada semana, la mitad de los mixtos inicia con mineral y la otra mitad con desmonte; diferencia máxima de uno si son impares) |
| Todos los polígonos de la semana | 3 | 462 → 459 (en casi todas las semanas el 50 % es inalcanzable; el reparto factible más cercano es el orden actual) |

Por eso la base predeterminada es «Polígonos con mineral y desmonte»: con «Todos los polígonos» y estos datos el reordenamiento prácticamente no cambia el orden. Ambas opciones están disponibles en Experimentos.

## 3. Interfaz (`prueba_interfaz.py` → 16/16)

Carga del Excel en segundo plano (4.3 s, pausa máxima del bucle de eventos 0.17 s: **la interfaz no se congela**), detección de hoja, año y fases, las ventanas de Fases / Destinos / Materiales / Matriz, los cuatro experimentos, todas las subpestañas de Resultados (Mineral y Desmonte), granularidad diaria, guardar y abrir `.pmsx`, ambas exportaciones y modo oscuro. Resultado en `Resultados/resultado_interfaz_linux.txt`; la misma prueba se ejecuta en Windows al compilar (`Resultados/resultado_interfaz_windows.txt`).

## 4. Ejecutable

El flujo `.github/workflows/compilar-windows.yml` (runner `windows-latest`, Python 3.12) ejecuta las pruebas del motor y de interfaz, compila con PyInstaller, abre el `.exe` en modo `--smoke` (interfaz + LP HiGHS + openpyxl dentro del ejecutable) y publica la carpeta `Plan Material Shift/`. Resultado de la prueba de humo: `Resultados/prueba_humo_exe_windows.txt`.
