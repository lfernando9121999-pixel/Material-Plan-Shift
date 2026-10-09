"""Punto de entrada de Plan Material Shift.

Uso:  Plan Material Shift.exe [escenario.pmsx]
      Plan Material Shift.exe --smoke <archivo_salida.txt>   (prueba de humo del ejecutable)
"""
import sys


def smoke(out_path):
    """Abre la interfaz, ejecuta un LP mínimo con el motor empaquetado y cierra."""
    import tkinter as tk
    import numpy as np
    from pms.app import App
    from scipy.optimize import linprog

    lines = []
    try:
        r = linprog(np.array([1.0, 2.0]), A_ub=np.array([[-1.0, -1.0]]), b_ub=np.array([-1.0]),
                    bounds=[(0, None), (0, None)], method="highs")
        lines.append(f"linprog: {r.status} {r.fun:.3f}")
        import openpyxl  # noqa: F401
        lines.append("openpyxl: ok")
        root = tk.Tk()
        app = App(root, [])
        for key in ("obj", "restr", "res", "inputs"):
            app.ws.show(key)
            root.update()
        lines.append(f"ui: ok ({len(app.workspaces)} escenario)")
        root.after(300, root.destroy)
        root.mainloop()
        lines.append("SMOKE OK")
    except Exception as ex:  # noqa: BLE001
        import traceback
        lines.append("SMOKE FAIL: " + repr(ex))
        lines.append(traceback.format_exc())
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--smoke":
        smoke(sys.argv[2])
    else:
        from pms.app import main
        main()
