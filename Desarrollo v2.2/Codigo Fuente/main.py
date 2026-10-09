"""Punto de entrada de Plan Material Shift.

Uso:  Plan Material Shift.exe [escenario.pmsx]
      Plan Material Shift.exe --smoke <archivo_salida.txt>   (prueba de humo del ejecutable)
"""
import sys


def smoke(out_path):
    """Abre la interfaz, ejecuta un LP mínimo con el motor empaquetado y cierra (nunca se bloquea)."""
    lines = ["inicio"]

    def flush():
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    flush()
    try:
        import numpy as np
        lines.append(f"numpy {np.__version__}")
        flush()
        from scipy.optimize import linprog
        r = linprog(np.array([1.0, 2.0]), A_ub=np.array([[-1.0, -1.0]]), b_ub=np.array([-1.0]),
                    bounds=[(0, None), (0, None)], method="highs")
        lines.append(f"linprog HiGHS: estado {r.status}, objetivo {r.fun:.3f}")
        flush()
        import openpyxl
        lines.append(f"openpyxl {openpyxl.__version__}")
        flush()
        lines.append(_smoke_engine())
        flush()
        import tkinter as tk
        from pms.app import App
        root = tk.Tk()
        root.after(20000, root.destroy)          # salvaguarda: nunca más de 20 s
        app = App(root, [])
        for key in ("obj", "restr", "res", "inputs"):
            app.ws.show(key)
            root.update()
        lines.append(f"interfaz: ok ({len(app.workspaces)} escenario, logo {'ok' if app.logo_big else 'no'})")
        flush()
        root.after(300, root.destroy)
        root.mainloop()
        lines.append("SMOKE OK")
    except BaseException as ex:  # noqa: BLE001
        import traceback
        lines.append("SMOKE FAIL: " + repr(ex))
        lines.append(traceback.format_exc())
    flush()


def _smoke_engine():
    """Excel mínimo → lectura → Optimización Integral → reporte (todo dentro del ejecutable)."""
    import datetime as dt
    import os
    import tempfile

    import openpyxl
    from pms import config as C
    from pms import engine
    from pms.export import export_report
    from pms.plan import load_plan

    tmp = tempfile.mkdtemp(prefix="pms_smoke_")
    path = os.path.join(tmp, "prueba.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    head = ["# Sec", "Semana", "Fase", "Malla / Stock", "Poligono / Origen", "Polígono Predecesor", "Fecha Liberación",
            "L1", "L2", "L3", "L4", "Proceso", "Total Material (t)", "RecA", "RecB", "DonA", "DonB", "Mx", "Wx", "Prop"]
    for j, h in enumerate(head):
        ws.cell(row=4, column=2 + j, value=h)
    r, sec = 5, 1
    for w in range(1, 53):
        for p in range(3):
            for k in range(2):
                mineral = (p + k + w) % 3 == 0
                t = 1000.0 * (1 + (w * 7 + p * 3 + k) % 5)
                dest = [t * 0.2, 0.0, t * 0.5, t * 0.3] if w % 2 else [0.0, t * 0.1, t * 0.4, t * 0.5]
                vals = [sec, w, f"FASE {p + 1}", f"P{w}_{p}", f"P{w}_{p}", "N/A", dt.datetime(2030, 1, 1) +
                        dt.timedelta(days=7 * (w - 1) + p), 1, 1, 1, 1, "CARGUIO", t] + dest + \
                       ([t, 0.0] if mineral else [0.0, t]) + [0]
                for j, v in enumerate(vals):
                    ws.cell(row=r, column=2 + j, value=v)
                r += 1
                sec += 1
    wb.save(path)
    plan = load_plan(path, ws.title)
    cfg = C.new_config()
    cfg["general"].update({"archivo": path, "hoja": ws.title, "nombre": "Humo"})
    C.ensure_plan_defaults(plan, cfg)
    cfg["materiales"].update({"Mx": "Mineral", "Wx": "Desmonte"})
    cfg["destinos"].update({"RecA": {"tipo": "Desmonte", "rol": "Receptor"}, "RecB": {"tipo": "Desmonte", "rol": "Receptor"},
                            "DonA": {"tipo": "Desmonte", "rol": "Donante"}, "DonB": {"tipo": "Desmonte", "rol": "Donante"}})
    C.refresh_circuits(plan, cfg)
    cfg["experimento"]["tipo"] = "integral"
    res = engine.run(plan, cfg)
    export_report(res, os.path.join(tmp, "reporte.xlsx"))
    bad = [v["indicador"] for v in res.validations if v["estado"] != "Ok" and not v["indicador"].startswith("Brechas")]
    if bad:
        raise RuntimeError("Validaciones con observaciones: " + ", ".join(bad))
    return f"motor: ok ({plan.n} filas, {len(res.moves)} movimientos, {res.swaps} intercambios, reporte exportado)"


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--smoke":
        smoke(sys.argv[2])
    else:
        from pms.app import main
        main()
