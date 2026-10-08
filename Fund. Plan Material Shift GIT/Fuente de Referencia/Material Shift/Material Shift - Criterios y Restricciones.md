# Material Shift v2.0 - Criterios y restricciones del cálculo

**Propósito.** Explicar qué controla cada input y cuáles reglas son obligatorias, preferencias de optimización o verificaciones posteriores. Análisis del código fuente y de los archivos `.md` del programa, realizado el 8 de octubre de 2026.

## Resumen del cálculo

Material Shift reasigna toneladas entre columnas **Receptor** (chancadoras) y **Donante** del plan base. Resuelve las 52 semanas juntas, por separado para los circuitos **Desmonte** y **Mineral**. En el modo Diario ejecuta luego un ajuste dentro de cada semana. Cada movimiento cambia dos columnas de la misma fila por la misma cantidad, por lo que no altera el total de esa fila.

El tonelaje resultante de un receptor en una semana es: **plan base + entradas de donantes - devoluciones a donantes**. La banda semanal aceptable es **objetivo - tolerancia** a **objetivo + tolerancia**. Cuando no se puede cumplir, se informa una brecha; no se crean toneladas.

## Relación entre inputs y reglas

| Criterio | Input o columna | Regla del cálculo |
|---|---|---|
| Archivo y hoja | Inputs: Archivo base y Hoja | Lee los valores ya calculados del `.xlsx`; no evalúa fórmulas. Encabezados desde la fila 4 y datos desde la fila 5. |
| Año y semanas elegibles | Año activo; Fecha Liberación y Semana del Excel | Solo modifica filas del año activo y de semanas 1 a 52. Las demás filas se copian. El año más frecuente se propone como valor inicial. |
| Circuito y rol del destino | Config del Excel o Inputs: Columnas detectadas - Editar | Receptor y Donante se asignan a Desmonte o Mineral. N/A queda fuera. Sin Config, los nombres permiten detectar solo Desmonte; Mineral requiere configuración. |
| Material de cada fila | Wa, Wb, Wc, Wh, Wrell, Wrip o M1, M2, M2a, M2at, M4b, M4bt, M5, M6 | La primera columna de material del circuito con tonelaje positivo define el tipo usado en la reasignación. Solo participan filas cuyo tipo corresponde al circuito. |
| Objetivo semanal | Objetivos: Objetivo Mt/sem por chancadora | Se aplica a cada receptor del circuito. Mt se convierte a toneladas multiplicando por 1 000 000. Es una meta con banda, no una igualdad estricta. |
| Tolerancia semanal | Objetivos: Tolerancia, unidad Mt o % | Define la semiamplitud de la banda alrededor del objetivo. En %, la app multiplica objetivo por porcentaje/100. Ejemplo: 2,60 +/- 0,05 Mt equivale a 2,55-2,65 Mt/sem. |
| Modo Objetivo fijo | Objetivos: Modo | Minimiza los movimientos y las brechas para acercar cada receptor a su banda semanal. |
| Modo Balanceado | Objetivos: Modo | Además penaliza la diferencia semanal entre dos receptores. Solo tiene efecto adicional si el circuito tiene exactamente dos; no obliga a dejarlos iguales. |
| Oferta y devolución | Tonelajes del plan base por semana, destino y material | En una semana, cada donante puede ceder como máximo su tonelaje disponible de cada material. Cada receptor puede devolver como máximo su tonelaje base de cada material. No hay intercambio directo entre receptores. |
| Matriz de materiales | Material: permiso destino por material | Una celda bloqueada impide movimientos de entrada y salida de ese material en ese destino. Por defecto, N2_1, N2_2, N2_3 y N3_7 tienen Wa bloqueado. |
| Conservación anual | Tonelaje base de cada destino | El total anual de cada donante y de cada receptor se conserva exactamente mediante igualdades que abarcan las 52 semanas. Puede cambiar la distribución semanal, pero el cambio anual neto es cero. |
| Prioridad de donantes | Prioridad: orden por receptor | Los donantes más altos en la lista tienen menor costo en el optimizador. Es una preferencia subordinada a la oferta, matriz y conservación. |
| Prioridad de fases | Prioridad: orden; Fase, Poligono / Origen y # Sec | Distribuye el flujo calculado entre filas. Para recibir: fase prioritaria, polígono y sección ascendentes. Para devolver: fase menos prioritaria y sección más alta. |
| Granularidad Diario | Objetivos: Diario; Objetivo Mt/día; Tolerancia diaria Mt; Fecha Liberación | Tras el cálculo semanal, intenta llenar días bajos y drenar días altos dentro de la misma semana. El presupuesto es el menor entre faltante y exceso. Conserva los totales semanales y anuales; si no cierra una semana, revierte ese suavizado. |
| Archivo de salida | Inputs: Archivo de salida | Define dónde se escribe el Plan Modificado. No cambia la optimización. El escenario `.csv` guarda los parámetros y la configuración. |

## Qué es estricto y qué es una preferencia

| Tipo | Reglas |
|---|---|
| Restricciones estrictas | Oferta por semana y material; máximo que puede devolver un receptor; matriz de materiales; conservación anual por destino; movimiento dentro de la misma fila y entre donante y receptor. |
| Metas con posible brecha | Objetivo y tolerancia semanal. El modelo penaliza fuertemente déficit o exceso fuera de banda, pero permite reportarlos si las restricciones impiden cumplir. El objetivo diario también puede dejar brechas. |
| Preferencias | Orden de donantes; balance entre dos receptores; selección de filas según prioridad de fases. |
| Comprobaciones posteriores | Conservación por destino (diferencia <= 1e-5 t); conservación del total de la fila; balance entre destinos y materiales por fila (desviación <= 0,05 %); matriz bloqueada; brechas semanales y diarias. |

## Aclaraciones importantes

1. **Desmarcar en Prioridad no bloquea estrictamente.** La app envía al motor solo los elementos marcados para formar el ranking. El motor deja participar a los omitidos con prioridad baja; si la lista queda vacía, usa el orden por defecto. La matriz de materiales sí impide un flujo para una combinación destino-material.
2. **Balance Material es una prueba, no una reparación.** Compara, por fila, la suma de destinos del circuito con la suma de materiales del circuito. Si falta clasificar una columna con tonelaje como destino, puede mostrar Revisar aunque los movimientos de la corrida sean consistentes.
3. **El objetivo anual implícito puede ser incompatible con el plan.** Por ejemplo, 2,60 Mt/sem por 52 semanas implica 135,2 Mt/año por receptor. Si el total anual de ese receptor en el plan base es diferente, la conservación anual puede impedir que todas las semanas entren en la banda.
4. **Los criterios son independientes por circuito.** Desmonte y Mineral tienen modo, objetivo, tolerancia, granularidad, objetivo diario, tolerancia diaria, prioridades y matriz propios.

## Funcionalidades relacionadas

El programa permite guardar/abrir escenarios `.csv`, detectar y editar destinos, calcular, revisar Dashboard/Tabla/Materiales, comparar escenarios y exportar el Plan Modificado a Excel, un reporte completo, gráficos PowerPoint y un dashboard HTML. Estas funciones presentan o guardan el resultado; las reglas de reasignación están en el motor Python.

## Fuentes revisadas

- `README.md`: arquitectura, entradas, lógica y validaciones.
- `Leame.md`: flujo de uso e interfaz.
- `Material Shift v2.md` y `Resumen_Sesion_Material_Shift_v2.md`: alcance y cambios de v2.0.
- `Desarrollo/Verificacion/Verificacion de Calculos.md`: verificaciones históricas documentadas.
- `Model/app/generar_ajuste_plan_2034.py`: optimización, aplicación de flujos, ajuste diario y validaciones.
- `Model/app/ajuste_plan_ejecutable.py`: orquestación por circuito y parámetros.
- `Desarrollo/Codigo Fuente/MaterialShift.cs` y `Model/app/sidebar.html`: inputs, conversiones y prioridades de la interfaz.
- `Escenarios/Caso_5 Mineral completo.csv`: ejemplo de parámetros guardados.

**Alcance de esta revisión:** lectura del código y documentación. No se ejecutó una nueva corrida ni se verificó el ejecutable compilado contra el código fuente.
