"""Prueba de rendimiento de la interfaz (latencias percibidas por el usuario).

Mide, con resultados cargados:
  * primera apertura y cambios repetidos de pestañas y subpestañas,
  * tiempo por tecla al escribir (nombre, descripción, metas) y si se reconstruyen widgets (parpadeo),
  * redimensionar y mover la ventana.

Uso: python prueba_rendimiento.py <carpeta_salida>      (Linux: xvfb-run)
"""
import os
import statistics
import sys
import time

import casos  # noqa: F401
from casos import INPUT, base_config

import tkinter as tk

OUT = sys.argv[1] if len(sys.argv) > 1 else "rendimiento"
os.makedirs(OUT, exist_ok=True)
rows = []
LIMITS = {"tab": 60.0, "tecla": 16.0, "resize": 40.0, "mover": 16.0}


def ms(fn, root, settle=0.25):
    """Bloqueo percibido: duración de la acción + el paso de eventos más largo hasta quedar en reposo.

    Incluye los redibujos diferidos (after) que ocurren después de la acción.
    """
    t = time.perf_counter()
    fn()
    root.update()
    worst = (time.perf_counter() - t) * 1000
    end = time.perf_counter() + settle
    while time.perf_counter() < end:
        t1 = time.perf_counter()
        root.update()
        worst = max(worst, (time.perf_counter() - t1) * 1000)
        time.sleep(0.004)
    return worst


def record(group, name, values, limit):
    mx = max(values)
    rows.append((group, name, statistics.mean(values), mx, limit, mx <= limit))
    print(f"{'OK  ' if mx <= limit else 'LENTO'} {group:8s} {name:46s} prom {statistics.mean(values):7.1f} ms  "
          f"máx {mx:7.1f} ms  (límite {limit:.0f})", flush=True)


def widget_ids(w):
    out = set()
    stack = [w]
    while stack:
        x = stack.pop()
        out.add(str(x))
        stack.extend(x.winfo_children())
    return out


def main():
    from pms.app import App
    from pms.plan import list_sheets
    root = tk.Tk()
    root.geometry("1500x940+0+0")
    app = App(root, [])
    ws = app.ws
    ws.cfg["general"]["archivo"] = INPUT
    ws.sheets = list_sheets(INPUT)
    ws.load_sheet(ws.sheets[0])
    while ws.plan is None or app.busy:
        root.update()
        time.sleep(0.02)
    ref = base_config(ws.plan, "integral")
    for k in ("fases", "destinos", "materiales", "circuitos", "experimento"):
        ws.cfg[k] = ref[k]
    ws.cfg["general"]["nombre"] = "Rendimiento"
    ws.cfg["experimento"]["prio_destinos"]["revisado"] = True
    ws.changed()
    ws.run()
    while app.busy or ws.result is None:
        root.update()
        time.sleep(0.02)
    root.update()
    # preparación en segundo plano de pestañas/subpestañas: bloqueo máximo del bucle de eventos
    blocks = []
    end = time.perf_counter() + 4.0
    while time.perf_counter() < end:
        t1 = time.perf_counter()
        root.update()
        blocks.append((time.perf_counter() - t1) * 1000)
        time.sleep(0.004)
    record("fondo", "Preparación en segundo plano (paso más largo)", [max(blocks)], 150)
    for task, t in getattr(ws, "prebuild_log", []):
        print(f"      paso {task}: {t:.0f} ms")

    main_tabs = [k for k, _ in ws.TABS]
    # primera apertura
    first = []
    for k in main_tabs:
        first.append(ms(lambda k=k: ws.show(k), root))
    page = ws.pages["res"]
    sub = [k for k, _ in page.TABS]
    first_sub = []
    for k in sub:
        first_sub.append(ms(lambda k=k: page.show(k), root))
    record("tab", "Primera apertura pestañas principales", first, 400)
    record("tab", "Primera apertura subpestañas de Resultados", first_sub, 600)
    # cambios repetidos
    times = []
    for _ in range(3):
        for k in main_tabs:
            times.append(ms(lambda k=k: ws.show(k), root))
    record("tab", "Cambio entre pestañas principales", times, LIMITS["tab"])
    ws.show("res")
    times = []
    for _ in range(3):
        for k in sub:
            times.append(ms(lambda k=k: page.show(k), root))
    record("tab", "Cambio entre subpestañas de Resultados", times, LIMITS["tab"])
    times = []
    for c in ("Mineral", "Desmonte", "Mineral", "Desmonte"):
        times.append(ms(lambda c=c: page.circ.set(c, notify=True), root))
    record("tab", "Cambio de circuito (vista actual)", times, 250)
    obj = ws.pages["obj"]
    ws.show("obj")
    times = []
    for _ in range(3):
        for k in ("exp", "meta"):
            times.append(ms(lambda k=k: obj.show(k), root))
    record("tab", "Cambio Meta Física / Experimentos", times, LIMITS["tab"])

    # escritura
    ws.show("inputs")
    inp = ws.pages["inputs"]

    def typing(widget, name, text="abcdefghij"):
        bar_before = widget_ids(app.tabbar)
        page_before = widget_ids(ws.host)
        tt = []
        widget.focus_force()
        root.update()
        for ch in text:
            def key(ch=ch):
                widget.insert("end", ch)
                widget.event_generate("<KeyRelease>")
            tt.append(ms(key, root, settle=0.12))
        rebuilt = len(bar_before ^ widget_ids(app.tabbar)) + len(page_before ^ widget_ids(ws.host))
        record("tecla", name, tt, LIMITS["tecla"])
        rows.append(("parpadeo", name + " (widgets reconstruidos)", rebuilt, rebuilt, 0, rebuilt == 0))
        print(f"{'OK  ' if rebuilt == 0 else 'PARPADEA'} widgets reconstruidos al escribir en {name}: {rebuilt}")

    typing(inp.name, "Nombre del Escenario")
    typing(inp.desc, "Descripción")
    ws.show("obj")
    obj.show("meta")
    root.update()
    blk = obj.pages["meta"].blocks["Desmonte"]
    e = blk.entries[("semanal", "prom")]
    e.delete(0, "end")
    typing(e, "Meta Promedio (Deseado)", "1.3")
    ws.show("res")
    page.show("dash")
    root.update()

    # redimensionar y mover
    sizes = ["1500x940", "1380x880", "1500x940", "1300x820", "1500x940", "1420x900"]
    times = [ms(lambda s=s: root.geometry(s), root) for s in sizes]
    record("resize", "Redimensionar ventana (Dashboard)", times, 250)
    page.show("reord")
    times = [ms(lambda s=s: root.geometry(s), root) for s in sizes]
    record("resize", "Redimensionar ventana (Reordenamiento)", times, 400)
    times = []
    for i in range(30):
        times.append(ms(lambda i=i: root.geometry(f"+{10 + 4 * i}+{10 + 2 * i}"), root, settle=0.03))
    record("mover", "Mover ventana (30 pasos)", times, LIMITS["mover"])
    for s in app.workspaces:
        s.dirty = False
    root.destroy()


if __name__ == "__main__":
    main()
    ok = sum(1 for r in rows if r[5])
    with open(os.path.join(OUT, "rendimiento.txt"), "w", encoding="utf-8") as f:
        f.write("Grupo\tMedición\tPromedio (ms)\tMáximo (ms)\tLímite\tEstado\n")
        for g, n, a, m, lim, good in rows:
            f.write(f"{g}\t{n}\t{a:.1f}\t{m:.1f}\t{lim}\t{'OK' if good else 'REVISAR'}\n")
        f.write(f"\nRESULTADO: {ok}/{len(rows)} mediciones dentro del límite\n")
    print(f"\nRESULTADO: {ok}/{len(rows)} mediciones dentro del límite")
