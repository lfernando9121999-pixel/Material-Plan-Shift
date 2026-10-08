# Material Shift — lógica matemática y backend

Revisión estática del código disponible en `C:\Users\Luis Fernando\Desktop\Material Shift` (8 de octubre de 2026). Este documento describe el comportamiento implementado; no equivale a una certificación de resultados de operación.

## 1. Flujo del programa

`Material Shift.exe` es la interfaz Windows. El motor persistente `Model/app/motor_servidor.py` recibe solicitudes JSON por `stdin`, ejecuta `ajuste_plan_ejecutable.main(argv)` y devuelve `{id, rc, output}` por `stdout`. Recarga los módulos en cada solicitud para restablecer sus variables globales; conserva una caché de lectura del Excel. `ajuste_plan_ejecutable.py` carga el plan, ejecuta los circuitos, construye validaciones, exporta el plan modificado y genera JSON/HTML para el dashboard. La optimización está en `generar_ajuste_plan_2034.py`, con `scipy.optimize.linprog(method="highs")`.

El libro se lee directamente como OOXML: encabezados en fila 4 desde columna B y datos desde fila 5. Se omiten filas sin valor en B. El valor de fórmulas procede de la caché guardada en el XLSX; el motor no recalcula Excel. La hoja `Config` define, por columna de destino, `Receptor`/`Donante` y `Mineral`/`Desmonte`. Sin esa hoja se detectan receptores por nombre `Chw2a` y donantes por posición; solo se ejecuta Desmonte. Mineral se calcula únicamente cuando tiene al menos un receptor configurado. La configuración editada en la aplicación puede sustituir la del libro.

## 2. Universo y parámetros

- Solo participan registros con `Fecha Liberación` en el año activo, `Semana` entre 1 y 52 y tipo de material reconocido. El año predeterminado es 2034 y puede cambiarse. `detect_active_year` sugiere el año modal, pero no cambia por sí solo el filtro.
- Desmonte reconoce `Wa`, `Wb`, `Wc`, `Wh`, `Wrell`, `Wrip`; Mineral usa las columnas de mineral presentes. El tipo de cada fila se infiere del **primer** material con valor positivo. Las columnas de material no son modificadas por el ajuste.
- Objetivo semanal predeterminado: 1,18 Mt por receptor; tolerancia: ±0,05 Mt. La CLI convierte Mt a toneladas multiplicando por 1 000 000. Un objetivo independiente de Mineral puede reemplazarlo.
- En modo diario, la tolerancia predeterminada es ±0,02 Mt/día. El objetivo diario explícito es independiente del semanal. Si falta, el algoritmo usa el total semanal **real** del receptor dividido entre el número de días con filas elegibles de esa semana.
- Se admiten prioridades de donantes y fases por receptor. Los elementos omitidos siguen siendo elegibles con rango bajo. La matriz de permisos bloquea pares destino/material; por defecto bloquea `Wa` en destinos Tucush.

## 3. Modelo semanal

Se resuelve **un programa lineal conjunto para las 52 semanas** de cada circuito. Sea `x⁺[w,c,d,m]` la transferencia del donante `d` al receptor `c` y `x⁻[w,c,d,m]` la devolución inversa para semana `w` y material `m`. Ambas variables son no negativas. El tonelaje final del receptor es:

`F[w,c] = B[w,c] + Σ(d,m) x⁺[w,c,d,m] − Σ(d,m) x⁻[w,c,d,m]`.

Restricciones principales:

1. `Σc x⁺[w,c,d,m] ≤ disponibilidad_base[w,d,m]` y `Σd x⁻[w,c,d,m] ≤ base_receptor[w,c,m]`. Cada arco bloqueado tiene cota superior cero.
2. Banda semanal con variables de holgura no negativas `s⁻` y `s⁺`: `F ≥ objetivo − tolerancia − s⁻` y `F ≤ objetivo + tolerancia + s⁺`. Por ello el modelo siempre puede expresar una brecha, incluso si la banda es inalcanzable.
3. Para **cada donante**, `Σ(w,c,m)(x⁺ − x⁻)=0`; para **cada receptor**, `Σ(w,d,m)(x⁺ − x⁻)=0`. Esto conserva exactamente el total anual de cada columna de destino dentro del modelo.
4. No hay transferencia directa receptor↔receptor. Las transferencias se realizan dentro de filas del mismo material; al aplicar cada movimiento se resta y suma el mismo tonelaje en la fila.

Función objetivo implementada: minimizar `Σ(rango_donante+1)x⁺ + 0,1Σx⁻ + 10⁷Σ(s⁻+s⁺)`. En modo `balanceado`, **solo si hay exactamente dos receptores**, se añade `2Σ|F[w,c1]−F[w,c2]|`, representado por una variable y dos desigualdades. Es una preferencia blanda; no impone igualdad ni sustituye la banda objetivo. Para uno o tres o más receptores, ese término se omite. La prioridad de fase no aparece en la función objetivo: determina el orden de filas donde se materializa cada transferencia del LP.

Si HiGHS falla, el código usa vector de transferencias cero, registra `LAST_LP.success=false` y luego calcula las brechas del plan sin ajustar. El consumidor debe revisar `lp_ok`; un archivo producido no prueba por sí solo que hubo solución óptima.

## 4. Materialización y refinamiento diario

Las transferencias semanales se aplican a filas del mismo material y semana. Al incorporar desde un donante se ordenan por prioridad de fase ascendente, polígono y secuencia. Al devolver desde receptor se recorren fases y secuencias en sentido inverso. El registro `moves` conserva origen, destino, tonelaje y fila Excel.

El paso diario es **heurístico**, posterior al LP. Dentro de cada semana y receptor calcula faltantes debajo de `objetivo_diario−tolerancia` y excedentes encima de `objetivo_diario+tolerancia`; limita el llenado a `min(faltante_total, excedente_total)`. Llena días deficitarios con material de donantes del **mismo día** y luego descarga días excedentes hacia las mismas columnas donantes usadas en esa semana. Si la matriz de materiales impide saldar todo, intenta devolver dentro de la semana o deshace el suavizado de ese receptor/semana. Así preserva los totales semanales y anuales, pero no garantiza que todas las bandas diarias se cumplan. Las brechas se informan.

## 5. Validaciones y salidas

`build_validations` compara total base y modificado por destino (`|Δ|≤10⁻⁵ t`), total por fila (`|Δ|≤10⁻⁵ t`, pero almacena solo las primeras 100 filas discrepantes) y banda semanal por receptor. `check_material_matrix` busca cambios en celdas destino/material bloqueadas (`|Δ|>10⁻⁶ t`). `check_row_material_balance` compara suma de destinos con suma de columnas de materiales por fila y acepta desviación porcentual ≤0,05 %, calculada sobre el mayor de ambos totales. Este último control también detecta inconsistencias ya presentes en la base; no implica que el algoritmo las haya causado.

La aplicación fusiona Desmonte y Mineral por columnas: cada circuito cambia únicamente sus destinos configurados. Escribe `Plan Modificado` en XLSX y, según la opción, un reporte completo, `Resultados.json` y un dashboard HTML autónomo. El JSON contiene series semanales/diarias, conservación, movimientos, objetivos, tolerancias y estados. `build_dashboard_dest_fast` usa un umbral visual de **1 t**, distinto del umbral `10⁻⁵ t` de `build_validations`; una pantalla puede indicar `OK` donde la validación estricta marca `Revisar`.

## 6. Criterios y límites que conviene revisar

1. **Balance por material.** La conservación anual impuesta es por destino, sumando materiales. No hay igualdad anual por cada par destino/material. La matriz impide arcos prohibidos, pero la composición anual de un destino puede cambiar.
2. **Filas con varios materiales.** `infer_waste_type` toma el primer material positivo. Si una fila contiene varios tipos, todas sus toneladas de destino se tratan como ese tipo para permisos y optimización. Conviene validar que cada fila tenga un único material operativo o desagregarla.
3. **Valores y parámetros.** La CLI restringe los nombres de modo, pero no establece cotas explícitas para objetivo, tolerancias ni valores numéricos del plan. Objetivos negativos, tolerancias negativas, valores no finitos o tonelajes negativos necesitan validación de entrada si pueden llegar desde archivos o escenarios.
4. **Reconciliación de aplicación.** Las restricciones del LP conservan cantidades matemáticas; la aplicación en filas usa umbrales `10⁻⁶`/`10⁻⁷` y coma flotante. Por ello deben verificarse `destinos_ok`, `row_breaks`, `matriz_ok`, `balance_material_ok`, `brechas` y `lp_ok` en cada corrida.
5. **Semanas y fechas.** El filtro acepta cualquier valor de `Semana` 1–52 de una fecha del año activo, sin comprobar que la fecha realmente corresponde a esa semana calendario. El modo diario agrupa según la fecha y usa la semana declarada.
6. **Concurrencia.** El motor persistente atiende peticiones secuencialmente y recarga los módulos en cada una. Las funciones del núcleo cambian variables globales durante la ejecución de cada circuito; invocarlas en paralelo desde otro proceso anfitrión requeriría aislar el estado.
7. **Precisión de estados.** El estado semanal creado dentro del LP admite `tolerancia+10⁻⁶`, mientras `build_validations` compara con la tolerancia exacta. En un límite numérico puede haber diferencia entre ambos estados.

## 7. Evidencia revisada

- `Model/app/generar_ajuste_plan_2034.py`: lectura, configuración, selección de filas, LP, aplicación de movimientos, refinamiento diario y validaciones.
- `Model/app/ajuste_plan_ejecutable.py`: parámetros, ejecución de ambos circuitos, fusión, exportaciones y datos del dashboard.
- `Model/app/motor_servidor.py`: protocolo JSON, recarga de módulos, caché y manejo de errores.
- `Desarrollo/Verificacion/Verificacion de Calculos.md`: documenta comparaciones previas con v19.5 y pruebas de interfaz; sus resultados se citan como evidencia histórica del proyecto, no se repitieron en esta revisión.

La revisión fue de código y documentación. No se ejecutó una corrida nueva ni se alteraron archivos del programa.
