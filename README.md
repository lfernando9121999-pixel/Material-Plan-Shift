# Plan Material Shift

Programa de escritorio (Windows) para balancear el material semanal y diario entre destinos donantes y receptores de un plan de minado leído desde Excel, con experimentos de **Reordenamiento de Filas** y **Asignación Balanceada Aleatoria**. Criterios según *Material Shift v2.1 (Codex).docx*.

## Versiones

| Versión | Ejecutable (entregable) | Código y pruebas |
|---|---|---|
| **v2.2** (vigente) | `Plan Material Shift v2.2/` | `Desarrollo v2.2/` — rendimiento, pestañas Restricciones antes de Función Objetivo, priorización de destinos en la permutación |
| v2.1 | `Plan Material Shift/` | `Desarrollo/` |

Detalle de la v2.2: `Desarrollo v2.2/Pruebas/Verificacion.md`.

## Estructura (v2.1; la v2.2 tiene la misma organización en `Desarrollo v2.2/`)

```
Plan Material Shift/              ← ENTREGABLE v2.1: Plan Material Shift.exe + _internal + Inputs, Escenarios, Outputs, Leame.md
Desarrollo/
├── Codigo Fuente/
│   ├── main.py                   Punto de entrada (también «--smoke» para la prueba de humo del .exe)
│   ├── pms/
│   │   ├── plan.py               Lectura del Excel y detección de la tabla («# Sec», destinos, materiales)
│   │   ├── config.py             Configuración del escenario, validaciones de inputs y archivo .pmsx
│   │   ├── engine.py             Motor: LP semanal/diario (SciPy HiGHS), asignación aleatoria, reordenamiento, validaciones
│   │   ├── export.py             Plan Modificado (formato original) y Reporte Excel con gráficos nativos
│   │   ├── app.py                Ventana principal, pestañas de escenarios, tareas en segundo plano
│   │   ├── view_inputs.py · view_config.py · view_results.py   Pestañas
│   │   ├── widgets.py · grid.py · charts.py · dialogs.py · theme.py   Controles, tablas y gráficos propios (tkinter)
│   │   └── assets/               Logo e ícono
│   ├── Plan Material Shift.spec  Compilación PyInstaller · compilar.ps1 · armar_entrega.ps1
│   └── entrega/                  Leame y carpetas anexas de la entrega
└── Pruebas/                      Pruebas del motor (pytest), prueba automática de interfaz y resultados
Fund. Plan Material Shift GIT/    Insumos y fuentes de referencia (sin cambios)
```

## Compilar

El ejecutable se compila en Windows con el flujo `.github/workflows/compilar-windows.yml` (pruebas → PyInstaller → prueba de humo → publica `Plan Material Shift/`). Localmente, en Windows con Python 3.12:

```powershell
powershell -ExecutionPolicy Bypass -File "Desarrollo\Codigo Fuente\compilar.ps1"
```

## Pruebas

```bash
cd Desarrollo/Pruebas
python -m pytest -q                       # motor (Excel sintético + Excel de trabajo)
python prueba_interfaz.py capturas        # interfaz completa con capturas
```

Detalle de la verificación: `Desarrollo/Pruebas/Verificacion.md`.
