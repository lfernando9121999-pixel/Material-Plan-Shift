"""Prueba automática de la interfaz (sin intervención): carga el Excel, configura el
escenario, ejecuta experimentos, recorre todas las pestañas y guarda capturas.

Uso: python prueba_interfaz.py <carpeta_capturas> [--dark]
Requiere un servidor gráfico (en Linux: xvfb-run).
"""
import os
import subprocess
import sys
import time
import traceback

import casos  # noqa: F401  (agrega el código fuente al path)
from casos import INPUT, base_config

import tkinter as tk

from pms import config as C
from pms.app import App

OUT = sys.argv[1] if len(sys.argv) > 1 else "capturas"
DARK = "--dark" in sys.argv
os.makedirs(OUT, exist_ok=True)
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("OK   " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""), flush=True)


def snap(root, name):
    root.update()
    time.sleep(0.25)
    root.update()
    path = os.path.join(OUT, name + ".png")
    try:
        subprocess.run(["import", "-window", "root", path], check=True, timeout=30)
    except Exception:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)


def wait(root, cond, timeout=180):
    t0 = time.time()
    while not cond():
        root.update()
        time.sleep(0.05)
        if time.time() - t0 > timeout:
            return False
    root.update()
    return True


def main():
    root = tk.Tk()
    root.geometry("1600x980+0+0")
    app = App(root, [])
    if DARK and not app.dark:
        app.toggle_dark()
    if not DARK and app.dark:
        app.toggle_dark()
    root.update()
    ws = app.ws
    snap(root, "01_inicio")

    # ---- carga del Excel (equivale a Seleccionar Archivo…) ------------------
    from pms.plan import list_sheets
    ws.cfg["general"]["archivo"] = INPUT
    ws.sheets = list_sheets(INPUT)
    t0 = time.time()
    ws.load_sheet(ws._guess_sheet(INPUT, ws.sheets))
    responsive = []

    def tick():
        responsive.append(time.time())
    for i in range(20):
        root.after(100 * i, tick)
    ok = wait(root, lambda: ws.plan is not None and not app.busy)
    check("Carga del Excel en segundo plano", ok, f"{time.time() - t0:.1f} s · {ws.plan.n if ws.plan else 0} filas")
    gaps = [b - a for a, b in zip(responsive, responsive[1:])]
    check("La interfaz no se congela durante la carga", gaps and max(gaps) < 1.5,
          f"pausa máxima del bucle de eventos {max(gaps) if gaps else 0:.2f} s")
    check("Hoja detectada automáticamente", ws.cfg["general"]["hoja"] == "Plan_Base", ws.cfg["general"]["hoja"])
    ys = ws.plan.years()
    check("Año detectado (más frecuente en Fecha Liberación)", ws.cfg["general"]["anio"] == max(ys, key=ys.get),
          str(ws.cfg["general"]["anio"]))
    check("Fases sin 0", "0" not in ws.cfg["fases"] and len(ws.cfg["fases"]) == 3, ", ".join(ws.cfg["fases"]))
    plan = ws.plan
    check("Destinos 14–59 / Materiales 60–74", plan.dest_idx[0] == 13 and plan.dest_idx[-1] == 58
          and plan.mat_idx[0] == 59 and plan.mat_idx[-1] == 73)
    ws.cfg["general"]["nombre"] = "Prueba Interfaz"
    ws.refresh_all()
    snap(root, "02_inputs_detectado")

    # ventanas emergentes de configuración
    from pms.dialogs import DestinationsDialog, MaterialsDialog, MatrixDialog, PhasesDialog
    for cls, name in ((PhasesDialog, "03_fases"), (MaterialsDialog, "04_materiales"),
                      (DestinationsDialog, "05_destinos")):
        root.after(700, lambda n=name: (snap(root, n), _close_tool(root)))
        cls(ws, ws.plan, ws.cfg, lambda st: None)
    # configuración completa como en las pruebas del motor
    ref = base_config(ws.plan)
    for k in ("fases", "destinos", "materiales", "circuitos"):
        ws.cfg[k] = ref[k]
    ws.changed()
    ws.refresh_all()
    snap(root, "06_inputs_configurado")
    ws.show("restr")
    snap(root, "07_restricciones")
    root.after(700, lambda: (snap(root, "08_matriz"), _close_tool(root)))
    MatrixDialog(ws, ws.plan, ws.cfg, "Desmonte", lambda m: None)
    ws.show("obj")
    ws.pages["obj"].pages["meta"].refresh()
    snap(root, "09_meta_fisica")
    ws.pages["obj"].show("exp")
    snap(root, "10_experimentos")

    # ---- experimentos ----------------------------------------------------------
    for exp in ("convencional", "reordenamiento", "aleatoria", "integral"):
        ws.cfg["experimento"]["tipo"] = exp
        ws.changed()
        t0 = time.time()
        ws.run()
        ok = wait(root, lambda: not app.busy and ws.result is not None and ws.results_state() == "Ejecutado")
        r = ws.result
        bad = [v for v in r.validations if v["estado"] != "Ok" and not v["indicador"].startswith("Brechas")]
        check(f"Experimento {exp}", ok and not bad, f"{time.time() - t0:.1f} s · {len(r.moves):,} movimientos"
              + (f" · revisar: {[b['indicador'] for b in bad]}" if bad else ""))
    page = ws.pages["res"]
    for key, _ in page.TABS:
        page.show(key)
        snap(root, f"11_res_{key}_desmonte")
    page.circ.set("Mineral", notify=True)
    page.show("dash")
    snap(root, "12_res_dash_mineral")
    page.show("reord")
    v = page.views["reord"]
    v._range(1, 6)
    snap(root, "13_reord_1a6_resultado")
    v.src.set("plan", notify=True)
    snap(root, "14_reord_1a6_plan")
    check("Reordenamiento cambia el orden de filas", ws.result.swaps > 0, f"{ws.result.swaps} intercambios")

    # diario
    for c in C.CIRCUITS:
        ws.cfg["circuitos"][c]["granularidad"] = "diario"
    ws.cfg["experimento"]["tipo"] = "convencional"
    ws.changed()
    ws.run()
    ok = wait(root, lambda: not app.busy and ws.results_state() == "Ejecutado")
    check("Granularidad diaria", ok and "Desmonte" in ws.result.daily_status)
    page.show("dash")
    snap(root, "15_res_dash_diario")

    # ---- guardar / abrir .pmsx --------------------------------------------------
    path = os.path.join(OUT, "Prueba Interfaz.pmsx")
    ok = app._write(ws, path)
    check("Guardar .pmsx con resultados", ok and os.path.exists(path), f"{os.path.getsize(path) / 1e6:.1f} MB")
    app.new_scenario()
    app.open_project(path)
    wait(root, lambda: not app.busy)
    check("Abrir .pmsx (resultados restaurados)", app.ws.result is not None and app.ws.results_state() == "Ejecutado")
    snap(root, "16_reabierto")

    # ---- exportaciones ------------------------------------------------------------
    from pms.export import export_plan, export_report
    t0 = time.time()
    n = export_plan(app.ws.result, os.path.join(OUT, "Plan Modificado.xlsx"))
    check("Exportar Plan Modificado", n > 0, f"{n:,} celdas · {time.time() - t0:.1f} s")
    t0 = time.time()
    export_report(app.ws.result, os.path.join(OUT, "Reporte.xlsx"))
    check("Exportar Reporte", os.path.exists(os.path.join(OUT, "Reporte.xlsx")), f"{time.time() - t0:.1f} s")

    # ---- modo oscuro ---------------------------------------------------------------
    app.toggle_dark()
    root.update()
    app.ws.show("res")
    snap(root, "17_oscuro_resultados")
    app.ws.show("obj")
    snap(root, "18_oscuro_meta")
    app.toggle_dark()
    root.update()
    for s in app.workspaces:
        s.dirty = False
    root.destroy()


def _close_tool(root):
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel):
                try:
                    c.cancel()
                except Exception:
                    c.destroy()
            else:
                walk(c)
    walk(root)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        results.append(("Excepción no controlada", False, ""))
    n_ok = sum(1 for r in results if r[1])
    print(f"\nRESULTADO: {n_ok}/{len(results)} pruebas OK")
    with open(os.path.join(OUT, "resultado_interfaz.txt"), "w", encoding="utf-8") as f:
        for name, ok, det in results:
            f.write(("OK   " if ok else "FAIL ") + name + (f" · {det}" if det else "") + "\n")
        f.write(f"\nRESULTADO: {n_ok}/{len(results)} pruebas OK\n")
    sys.exit(0 if n_ok == len(results) else 1)
