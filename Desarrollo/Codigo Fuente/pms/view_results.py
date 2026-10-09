"""Pestaña Resultados y sus subpestañas."""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk

import numpy as np

from . import config as C
from .charts import BarChart, LineChart, SegmentChart, Sparkline
from .export import MOVE_HEADERS, REORDER_HEADERS, moves_rows, reorder_rows
from .grid import DataGrid
from .theme import C as K, F, SERIES, PLAN_COLOR, SCEN_COLOR, MINERAL_COLOR, DESMONTE_COLOR
from .widgets import Btn, Card, Check, FilterButton, ScrollFrame, Segmented, Tooltip, autowrap, fmt, fmt_signed, label

MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
NUM = {"align": "e"}


def _date(o):
    return _dt.date.fromordinal(int(o)).strftime("%d/%m/%Y")


def dest_colors(dests):
    return {d: SERIES[i % len(SERIES)] for i, d in enumerate(dests)}


class ResultsPage(tk.Frame):
    TABS = (("dash", "Dashboard"), ("tabla", "Tabla"), ("mat", "Materiales"), ("mina", "Plan de Mina"),
            ("reord", "Reordenamiento de Filas"), ("val", "Validación"), ("mov", "Movimientos"))

    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        strip = tk.Frame(self, bg=K["panel"])
        strip.pack(fill="x")
        self.sub = {}
        for key, text in self.TABS:
            lb = tk.Label(strip, text=text, font=F["base"], bg=K["panel"], fg=K["text"], padx=9, pady=7, cursor="hand2")
            lb.pack(side="left")
            lb.bind("<ButtonRelease-1>", lambda e, k=key: self.show(k))
            self.sub[key] = lb
        self.circ = Segmented(strip, [(c, c) for c in C.CIRCUITS], "Desmonte", self._circuit, padx=10, pady=3,
                              colors={"Mineral": MINERAL_COLOR, "Desmonte": DESMONTE_COLOR})
        self.circ.pack(side="right", padx=8, pady=4)
        Tooltip(self.circ, "Circuito mostrado en Dashboard, Tabla, Materiales, Validación y Movimientos")
        tk.Frame(self, bg=K["border"], height=1).pack(fill="x")
        self.banner = tk.Frame(self, bg=K["bad_bg"])
        self.banner_lbl = label(self.banner, "", F["base"], K["bad_fg"], bg=K["bad_bg"])
        self.banner_lbl.pack(side="left", padx=12, pady=5)
        self.host = tk.Frame(self, bg=K["bg"])
        self.host.pack(fill="both", expand=True)
        self.empty = tk.Frame(self.host, bg=K["bg"])
        label(self.empty, "Sin Resultados", F["h1"], K["muted"], bg=K["bg"]).pack(pady=(80, 6))
        label(self.empty, "Complete Inputs, Restricciones y Función Objetivo, y pulse «Ejecutar Experimento» (F5).",
              F["base"], K["muted"], bg=K["bg"]).pack()
        self.views = {}
        self.cur = "dash"
        self.shown_result = None
        self._paint_tabs()
        self.after_idle(self.update_view)

    def _paint_tabs(self):
        for k, lb in self.sub.items():
            on = k == self.cur
            lb.configure(font=F["bold"] if on else F["base"], fg=K["accent"] if on else K["text"])

    def _circuit(self, c):
        self.update_view(force=True)

    def show(self, key):
        self.cur = key
        self._paint_tabs()
        self.update_view()

    def refresh(self):
        self.update_view()

    def update_view(self, force=False):
        res = self.ws.result
        for v in self.views.values():
            v.pack_forget()
        self.empty.pack_forget()
        if self.ws.results_state() == "Desactualizados":
            self.banner_lbl.configure(text="Resultados desactualizados: la configuración cambió después del cálculo. "
                                           "Pulse F5 para recalcular.")
            self.banner.pack(fill="x", before=self.host)
        else:
            self.banner.pack_forget()
        if res is None:
            self.empty.pack(fill="both", expand=True)
            return
        ran = [c for c in C.CIRCUITS if res.circuit_ran(c)]
        if ran and self.circ.get() not in ran:
            self.circ.set(ran[-1])
        circ = self.circ.get()
        if self.cur not in self.views:
            cls = {"dash": DashboardView, "tabla": TableView, "mat": MaterialsView, "mina": MineView,
                   "reord": ReorderView, "val": ValidationView, "mov": MovesView}[self.cur]
            self.views[self.cur] = cls(self.host, self)
        v = self.views[self.cur]
        v.pack(fill="both", expand=True)
        key = (id(res), circ)
        if force or getattr(v, "_key", None) != key:
            v._key = key
            v.update(res, circ)

    def rebuild(self):
        for v in self.views.values():
            v.destroy()
        self.views = {}
        self.update_view(force=True)


# ---------------------------------------------------------------------------
def _kpi(parent, title, help_=None):
    outer = tk.Frame(parent, bg=K["border"])
    inner = tk.Frame(outer, bg=K["panel"])
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    top = tk.Frame(inner, bg=K["panel"])
    top.pack(fill="x", padx=12, pady=(8, 0))
    t = label(top, title, F["small"], K["muted"])
    t.pack(side="left")
    if help_:
        q = label(top, "?", F["small"], K["muted"], cursor="question_arrow")
        q.pack(side="right")
        Tooltip(q, help_)
    v = label(inner, "", F["kpi"], K["text"], anchor="w")
    v.pack(fill="x", padx=12, pady=(0, 8))
    outer.parts = (inner, top, t, v)
    return outer


def _set_kpi(card, value, state=None):
    inner, top, t, v = card.parts
    bg = {None: K["panel"], "ok": K["ok_bg"], "bad": K["bad_bg"]}[state]
    fg = {None: K["text"], "ok": K["ok_fg"], "bad": K["bad_fg"]}[state]
    for w in (inner, top, t, v) + tuple(top.winfo_children()):
        w.configure(bg=bg)
    v.configure(text=value, fg=fg)


class _Chips(tk.Frame):
    def __init__(self, parent, on_change):
        super().__init__(parent, bg=K["panel"])
        self.on_change = on_change
        self.sel = []
        self.checks = {}

    def set(self, items, colors, selected):
        for w in self.winfo_children():
            w.destroy()
        self.checks = {}
        self.sel = [x for x in items if x in selected]
        for x in items:
            f = tk.Frame(self, bg=K["border"])
            f.pack(side="left", padx=(0, 6), pady=2)
            i = tk.Frame(f, bg=K["panel"])
            i.pack(padx=1, pady=1)
            ch = Check(i, "", x in selected, lambda v, x=x: self._t(x, v), bg=K["panel"])
            ch.pack(side="left", padx=(6, 4), pady=3)
            sw = tk.Canvas(i, width=10, height=10, bg=K["panel"], highlightthickness=0)
            sw.create_rectangle(0, 0, 10, 10, fill=colors[x], outline="")
            sw.pack(side="left")
            label(i, x, F["base"], bg=K["panel"]).pack(side="left", padx=(4, 8))
            self.checks[x] = ch
        self.items = items

    def _t(self, x, v):
        s = set(self.sel)
        (s.add if v else s.discard)(x)
        self.sel = [i for i in self.items if i in s]
        self.on_change()


# ---------------------------------------------------------------------------
class DashboardView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        self.page = page
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        b = sf.body
        self.kpis = tk.Frame(b, bg=K["bg"])
        self.kpis.pack(fill="x", padx=14, pady=(12, 6))
        # gráfico 1
        c1 = Card(b, "Material Semanal por Destino Seleccionado (t)")
        c1.pack(fill="x", padx=14, pady=6)
        self.c1 = c1
        self.per1 = Segmented(c1.head, [("semanal", "Semanal"), ("diario", "Diario")], "semanal", lambda v: self._draw1(),
                              pady=2)
        self.per1.pack(side="left", padx=12)
        self.mode1 = Segmented(c1.head, [("ind", "Individual"), ("tot", "Total")], "ind", lambda v: self._draw1(), pady=2)
        self.mode1.pack(side="right")
        self.chips1 = _Chips(c1.body, self._draw1)
        self.chips1.pack(fill="x", pady=(0, 6))
        row = tk.Frame(c1.body, bg=K["panel"])
        row.pack(fill="x")
        self.ch1 = LineChart(row, height=330, xlabel="Semana")
        self.ch1.pack(side="left", fill="both", expand=True)
        self.stats = tk.Frame(row, bg=K["panel"], width=190)
        self.stats.pack(side="right", fill="y", padx=(10, 0))
        self.stat_cards = []
        for t in ("Total", "Promedio", "Máximo", "Mínimo"):
            card = _kpi(self.stats, t)
            card.pack(fill="x", pady=3)
            self.stat_cards.append(card)
        # gráfico 2
        c2 = Card(b, "Conservación Semanal y Total por Destino Seleccionado (t)")
        c2.pack(fill="x", padx=14, pady=(6, 14))
        self.per2 = Segmented(c2.head, [("semanal", "Semanal"), ("diario", "Diario")], "semanal", lambda v: self._draw2(),
                              pady=2)
        self.per2.pack(side="left", padx=12)
        self.chips2 = _Chips(c2.body, self._draw2)
        self.chips2.pack(fill="x", pady=(0, 6))
        row2 = tk.Frame(c2.body, bg=K["panel"])
        row2.pack(fill="x")
        row2.grid_columnconfigure(0, weight=2)
        row2.grid_columnconfigure(1, weight=1)
        self.ch2 = LineChart(row2, height=300, xlabel="Semana")
        self.ch2.grid(row=0, column=0, sticky="nsew")
        self.ch3 = BarChart(row2, height=300)
        self.ch3.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def update(self, res, circ):
        self.res, self.circ = res, circ
        info = res.circuit_info(circ)
        cfg = res.cfg
        cc = cfg["circuitos"][circ]
        for w in self.kpis.winfo_children():
            w.destroy()
        daily = circ in res.daily_status
        vals = {v["indicador"]: v for v in res.validations if v["circuito"] in ("General", circ)}

        def st(name):
            v = vals.get(name)
            return "ok" if v and v["estado"] == "Ok" else "bad"
        cards = [("Movimientos", f"{res.moves_count(circ):,}", None,
                  "Número de traslados fila a fila (desde → hacia) del circuito en todas las etapas."),
                 ("Brechas Semanales", f"{res.gaps(circ):,}", None,
                  "Semanas × receptor fuera de la banda Mínimo–Máximo (en Balanceado: semanas con el total fuera de banda).")]
        if daily:
            cards.append(("Brechas Diarias", f"{res.gaps(circ, True):,}", None, "Días × receptor fuera de la banda diaria."))
        cards += [("Destinos", "✓ Ok" if st("Conservación Anual por Destino (Columnas)") == "ok" else "! Revisar",
                   st("Conservación Anual por Destino (Columnas)"), "Total anual de cada destino: plan vs escenario."),
                  ("Balance Material", "✓ Ok" if st("Balance Destino / Material por Fila") == "ok" else "! Revisar",
                   st("Balance Destino / Material por Fila"), "En cada fila, Σ destinos = Σ materiales (desviación ≤ 0.05 %)."),
                  ("Tabla Materiales", "✓ Ok" if st("Matriz de Materiales por Destino") == "ok" else "! Revisar",
                   st("Matriz de Materiales por Destino"), "Las combinaciones destino/material bloqueadas no cambian.")]
        ov = C.objective_values(cfg, circ, "semanal")
        for r in info.receptors[:3]:
            cards.append((f"Obj. {r} t/sem", fmt(ov[1]) if ov else "—", None,
                          f"Banda semanal: {fmt(ov[0])} – {fmt(ov[2])} t" if ov else ""))
        per_row = len(cards) if len(cards) <= 7 else (len(cards) + 1) // 2
        for i, (t, v, s, h) in enumerate(cards):
            k = _kpi(self.kpis, t, h)
            k.grid(row=i // per_row, column=i % per_row, sticky="nsew", padx=(0, 8), pady=(0, 6))
            self.kpis.grid_columnconfigure(i % per_row, weight=1, uniform="k")
            _set_kpi(k, v, s)
        self.dests = info.dests
        self.colors = dest_colors(self.dests)
        self.chips1.set(self.dests, self.colors, set(info.receptors))
        self.chips2.set(self.dests, self.colors, set(info.receptors))
        for s in (self.per1, self.per2):
            s.set("diario" if daily and cc["granularidad"] == "diario" and s is self.per1 else "semanal")
        self._draw1()
        self._draw2()

    def _series(self, per, which):
        res = self.res
        dn = res.dests()
        if per == "diario":
            M = res.day_dest(which)
            cats = [_date(o)[:5] for o in res.days()]
        else:
            M = res.week_dest(which)
            cats = [str(i) for i in range(1, 53)]
        return cats, {d: M[:, dn.index(d)] for d in self.dests}

    def _draw1(self):
        res, circ = self.res, self.circ
        per = self.per1.get()
        cats, fin = self._series(per, "final")
        sel = self.chips1.sel
        info = res.circuit_info(circ)
        kind = "diario" if per == "diario" else "semanal"
        ov = C.objective_values(res.cfg, circ, kind)
        series, hl = [], []
        if self.mode1.get() == "tot":
            v = np.sum([fin[d] for d in sel], axis=0) if sel else np.zeros(len(cats))
            series.append({"name": "Total seleccionado", "values": v.tolist(), "color": SCEN_COLOR})
            nrec = sum(1 for d in sel if d in info.receptors)
            if ov and nrec == len(sel) and nrec:
                hl = [{"value": ov[2] * nrec, "color": K["bad_fg"], "label": "Máximo"},
                      {"value": ov[1] * nrec, "color": K["muted"], "label": "Promedio (Deseado)"},
                      {"value": ov[0] * nrec, "color": K["warn"], "label": "Mínimo"}]
            allv = v
        else:
            for d in sel:
                series.append({"name": d, "values": fin[d].tolist(), "color": self.colors[d]})
            if ov and sel and all(d in info.receptors for d in sel):
                hl = [{"value": ov[2], "color": K["bad_fg"], "label": "Máximo"},
                      {"value": ov[1], "color": K["muted"], "label": "Promedio (Deseado)"},
                      {"value": ov[0], "color": K["warn"], "label": "Mínimo"}]
            allv = np.sum([fin[d] for d in sel], axis=0) if sel else np.zeros(len(cats))
        self.ch1.xlabel = "Día" if per == "diario" else "Semana"
        self.ch1.set_data(cats, series, hl)
        self.c1.title.configure(text=f"Material {'Diario' if per == 'diario' else 'Semanal'} por Destino Seleccionado (t)")
        n = len(allv)
        lab = "Días" if per == "diario" else "Sem"
        vals = [(f"Total {n} {lab}", fmt(float(np.sum(allv)))),
                ("Promedio " + ("Día" if per == "diario" else "Semana"), fmt(float(np.mean(allv))) if n else "0"),
                ("Máximo", fmt(float(np.max(allv))) if n else "0"), ("Mínimo", fmt(float(np.min(allv))) if n else "0")]
        for card, (t, v) in zip(self.stat_cards, vals):
            card.parts[2].configure(text=t)
            _set_kpi(card, v)

    def _draw2(self):
        per = self.per2.get()
        cats, fin = self._series(per, "final")
        _, base = self._series(per, "base")
        sel = self.chips2.sel
        z = np.zeros(len(cats))
        a = np.sum([base[d] for d in sel], axis=0) if sel else z
        b = np.sum([fin[d] for d in sel], axis=0) if sel else z
        name = self.res.cfg["general"]["nombre"] or "Escenario"
        self.ch2.xlabel = "Día" if per == "diario" else "Semana"
        self.ch2.set_data(cats, [{"name": "Plan", "values": a.tolist(), "color": PLAN_COLOR},
                                 {"name": name, "values": b.tolist(), "color": SCEN_COLOR}])
        self.ch3.set_data(["Total"], [{"name": "Plan", "values": [float(a.sum())], "color": PLAN_COLOR},
                                      {"name": name, "values": [float(b.sum())], "color": SCEN_COLOR}])


# ---------------------------------------------------------------------------
class TableView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        top = tk.Frame(self, bg=K["bg"])
        top.pack(fill="x", padx=14, pady=(10, 4))
        label(top, "Vista por período:", F["base"], K["muted"], bg=K["bg"]).pack(side="left")
        self.per = Segmented(top, [("semanal", "Semanal"), ("diario", "Diario")], "semanal", lambda v: self._draw(), pady=2)
        self.per.pack(side="left", padx=8)
        label(top, "Clic derecho sobre una tabla para copiarla. Verde: recibe más que el Plan · Rojo: recibe menos.",
              F["small"], K["muted"], bg=K["bg"]).pack(side="right")
        body = tk.Frame(self, bg=K["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=(4, 14))
        body.grid_columnconfigure(0, weight=1, uniform="t")
        body.grid_columnconfigure(1, weight=1, uniform="t")
        body.grid_rowconfigure(1, weight=1)
        self.t1 = label(body, "Plan por Semana y Destino", F["section"], bg=K["bg"])
        self.t1.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.t2 = label(body, "", F["section"], bg=K["bg"])
        self.t2.grid(row=0, column=1, sticky="w", pady=(0, 4), padx=(10, 0))
        self.g1 = DataGrid(body, [])
        self.g1.grid(row=1, column=0, sticky="nsew")
        self.g2 = DataGrid(body, [], cell_style=self._style)
        self.g2.grid(row=1, column=1, sticky="nsew", padx=(10, 0))

    def update(self, res, circ):
        self.res, self.circ = res, circ
        self._draw()

    def _style(self, row, ci):
        if ci == 0:
            return None
        idx = row[-1]
        b = self.base_rows[idx][ci]
        v = row[ci]
        if v > b + 0.5:
            return K["green_cell"], K["ok_fg"]
        if v < b - 0.5:
            return K["red_cell"], K["bad_fg"]
        return None

    def _draw(self):
        res = self.res
        info = res.circuit_info(self.circ)
        dn = res.dests()
        per = self.per.get()
        if per == "diario":
            B, Fm = res.day_dest("base"), res.day_dest("final")
            labels = [_date(o) for o in res.days()]
            pname = "Día"
        else:
            B, Fm = res.week_dest("base"), res.week_dest("final")
            labels = [str(i) for i in range(1, 53)]
            pname = "Semana"
        cols = [dn.index(d) for d in info.dests]
        name = res.cfg["general"]["nombre"] or "Escenario"
        self.t1.configure(text=f"Plan por {pname} y Destino (t)")
        self.t2.configure(text=f"{name} por {pname} y Destino (t)")
        columns = [{"title": pname, "align": "w", "width": 90 if per == "diario" else 70}] + \
                  [{"title": d, **NUM} for d in info.dests]
        gh = [("Destino", 1, len(info.dests))]
        self.base_rows = [[labels[i]] + [float(B[i, j]) for j in cols] + [i] for i in range(len(labels))]
        fin_rows = [[labels[i]] + [float(Fm[i, j]) for j in cols] + [i] for i in range(len(labels))]
        tb = ["Total"] + [float(B[:, j].sum()) for j in cols] + [-1]
        tf = ["Total"] + [float(Fm[:, j].sum()) for j in cols] + [-1]
        for g, rows, tot in ((self.g1, self.base_rows, tb), (self.g2, fin_rows, tf)):
            g.set_columns(columns, gh)
            g.set_rows(rows, tot, keep_state=False)


# ---------------------------------------------------------------------------
class MaterialsView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        body = tk.Frame(self, bg=K["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=12)
        body.grid_columnconfigure(0, weight=1, uniform="m")
        body.grid_columnconfigure(1, weight=1, uniform="m")
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        self.k1 = Card(body, "Total por Tipo de Material (t)")
        self.k1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.ch1 = BarChart(self.k1.body, height=260)
        self.ch1.pack(fill="both", expand=True)
        self.k2 = Card(body, "Total por Destino (t)")
        self.k2.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.ch2 = BarChart(self.k2.body, horizontal=True, height=280)
        self.ch2.pack(fill="both", expand=True)
        self.k3 = Card(body, "Detalle por Destino y Tipo de Material (t)")
        self.k3.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(6, 0))
        self.grid_ = DataGrid(self.k3.body, [], cell_style=self._style)
        self.grid_.pack(fill="both", expand=True)

    def _style(self, row, ci):
        if ci == 4:
            if row[4] > 0.5:
                return K["green_cell"], K["ok_fg"]
            if row[4] < -0.5:
                return K["red_cell"], K["bad_fg"]
        return None

    def update(self, res, circ):
        plan = res.plan
        info = res.circuit_info(circ)
        name = res.cfg["general"]["nombre"] or "Escenario"
        rm = plan.row_material()
        mats = plan.mat_names
        V0, V1 = plan.V, res.V_bal
        ym = plan.year_mask(res.cfg["general"].get("anio"))
        dcols = {d: plan.vcol(plan.dest_idx[plan.dest_names.index(d)]) for d in info.dests}
        per_mat_a, per_mat_b, rows = [], [], []
        for m in info.materials:
            sel = (rm == mats.index(m)) & ym
            a = sum(float(V0[sel, j].sum()) for j in dcols.values())
            b = sum(float(V1[sel, j].sum()) for j in dcols.values())
            per_mat_a.append(a)
            per_mat_b.append(b)
        for d, j in dcols.items():
            for m in info.materials:
                sel = (rm == mats.index(m)) & ym
                a, b = float(V0[sel, j].sum()), float(V1[sel, j].sum())
                if a > 0.5 or b > 0.5:
                    rows.append([d, m, a, b, b - a])
        self.k1.title.configure(text=f"{circ}: Total por Tipo de Material (t)")
        self.ch1.set_data(info.materials, [{"name": "Plan", "values": per_mat_a, "color": PLAN_COLOR},
                                           {"name": name, "values": per_mat_b, "color": SCEN_COLOR}])
        self.k2.title.configure(text=f"{circ}: Total por Destino (t)")
        ta = [sum(r[2] for r in rows if r[0] == d) for d in info.dests]
        tb = [sum(r[3] for r in rows if r[0] == d) for d in info.dests]
        self.ch2.configure(height=max(220, 40 * len(info.dests) + 60))
        self.ch2.set_data(info.dests, [{"name": "Plan", "values": ta, "color": PLAN_COLOR},
                                       {"name": name, "values": tb, "color": SCEN_COLOR}])
        self.grid_.set_columns([{"title": "Destino", "filter": True}, {"title": "Tipo", "filter": True},
                                {"title": "Plan", **NUM}, {"title": name, **NUM},
                                {"title": "Diferencia", **NUM, "fmt": lambda v: fmt_signed(v)}])
        tot = ["Total", "", sum(r[2] for r in rows), sum(r[3] for r in rows), sum(r[4] for r in rows)]
        self.grid_.set_rows(rows, tot, keep_state=False)


# ---------------------------------------------------------------------------
class MineView(tk.Frame):
    """Reporte dinámico semana a semana con filtros (estilo «Plan de Mina» de SimA)."""

    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        self.page = page
        self.res = None
        bar = tk.Frame(self, bg=K["panel"])
        bar.pack(fill="x")
        tk.Frame(self, bg=K["border"], height=1).pack(fill="x")
        self.bar = bar
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        b = sf.body
        self.kpis = tk.Frame(b, bg=K["bg"])
        self.kpis.pack(fill="x", padx=12, pady=(10, 4))
        self.cards = []
        colors = [K["primary"], K["accent"], "#E36209", "#8250DF"]
        for i, t in enumerate(("Tonelaje Total", "Tonelaje Promedio", "Tonelaje Máximo", "Tonelaje Mínimo")):
            outer = tk.Frame(self.kpis, bg=K["border"])
            outer.grid(row=0, column=i, sticky="nsew", padx=(0, 8))
            self.kpis.grid_columnconfigure(i, weight=1, uniform="k")
            tk.Frame(outer, bg=colors[i], height=3).pack(fill="x", padx=1, pady=(1, 0))
            inn = tk.Frame(outer, bg=K["panel"])
            inn.pack(fill="both", expand=True, padx=1, pady=(0, 1))
            left = tk.Frame(inn, bg=K["panel"])
            left.pack(side="left", fill="y", padx=12, pady=8)
            tl = label(left, t, F["small"], K["muted"])
            tl.pack(anchor="w")
            v = label(left, "", F["kpi"])
            v.pack(anchor="w")
            s = label(left, "", F["small"], colors[i])
            s.pack(anchor="w")
            sp = Sparkline(inn, width=150, height=46, color=colors[i])
            sp.pack(side="right", padx=10, pady=8)
            self.cards.append((tl, v, s, sp))
        self.ck = Card(b, "Tonelaje por Semana y Destino (t)")
        self.ck.pack(fill="x", padx=12, pady=6)
        self.chart = BarChart(self.ck.body, stacked=True, height=380)
        self.chart.pack(fill="both", expand=True)
        self.ct = Card(b, "Tonelaje por Fase, Material y Semana (t)")
        self.ct.pack(fill="x", padx=12, pady=(6, 14))
        self.table = DataGrid(self.ct.body, [], height=260, stretch=False, min_col=64)
        self.table.pack(fill="both", expand=True)

    def _build_bar(self, res):
        for w in self.bar.winfo_children():
            w.destroy()
        plan, cfg = res.plan, res.cfg
        b = tk.Frame(self.bar, bg=K["panel"])
        b.pack(fill="x")
        b2 = tk.Frame(self.bar, bg=K["panel"])
        b2.pack(fill="x")
        self.per = Segmented(b, [("dia", "Día"), ("sem", "Semana"), ("mes", "Mes")], "sem", lambda v: self.redraw(),
                             pady=2, padx=10)
        self.per.pack(side="left", padx=(10, 12), pady=6)
        ym = plan.year_mask(cfg["general"].get("anio"))
        months = sorted({_dt.date.fromordinal(int(o)).month for o in plan.date_ord[ym]})
        self.f_mes = FilterButton(b, "Mes", [MONTHS[m - 1] for m in months], self.redraw, "Todos")
        self.f_mes.pack(side="left", padx=4)
        self.f_fase = FilterButton(b, "Fase", plan.detected_phases(), self.redraw)
        self.f_fase.pack(side="left", padx=4)
        self.f_tmat = FilterButton(b, "Tipo de Material", ["Mineral", "Desmonte", "N/A"], self.redraw, "Todos")
        self.f_tmat.pack(side="left", padx=4)
        self.f_mat = FilterButton(b, "Material", C.detected_materials(plan), self.redraw, "Todos")
        self.f_mat.pack(side="left", padx=4)
        self.f_tdest = FilterButton(b, "Tipo de Destino", ["Mineral", "Desmonte", "N/A"], self.redraw, "Todos")
        self.f_tdest.pack(side="left", padx=4)
        self.f_dest = FilterButton(b, "Destino", C.detected_destinations(plan), self.redraw, "Todos")
        self.f_dest.pack(side="left", padx=4)
        right = tk.Frame(b2, bg=K["panel"])
        right.pack(side="left", padx=10, pady=(0, 6))
        label(right, "Apilar por", F["base"], K["muted"]).pack(side="left", padx=(0, 4))
        self.stack = Segmented(right, [("dest", "Destino"), ("mat", "Material"), ("fase", "Fase")], "dest",
                               lambda v: self.redraw(), pady=2, padx=8)
        self.stack.pack(side="left", padx=(0, 12))
        label(right, "Fuente", F["base"], K["muted"]).pack(side="left", padx=(0, 4))
        self.src = Segmented(right, [("plan", "Plan"), ("res", "Escenario")], "res", lambda v: self.redraw(), pady=2,
                             padx=8)
        self.src.pack(side="left")
        Btn(right, "✕ Limpiar Filtros", self._clear, kind="subtle", padx=6).pack(side="left", padx=12)

    def _clear(self):
        for f in (self.f_mes, self.f_fase, self.f_tmat, self.f_mat, self.f_tdest, self.f_dest):
            f.reset()
        self.redraw()

    def update(self, res, circ):
        if self.res is not res:
            self.res = res
            self._build_bar(res)
        self.redraw()

    def redraw(self):
        res = self.res
        plan, cfg = res.plan, res.cfg
        V = res.V if self.src.get() == "res" else plan.V
        ym = plan.year_mask(cfg["general"].get("anio"))
        rm = plan.row_material()
        mats = plan.mat_names
        months_sel = {MONTHS.index(m) + 1 for m in self.f_mes.selected()}
        dates = plan.date_ord
        month_of = np.array([_dt.date.fromordinal(int(o)).month if o else 0 for o in dates])
        mask = ym & np.isin(month_of, list(months_sel))
        ph_sel = self.f_fase.selected()
        mask &= np.array([p in ph_sel for p in plan.phase])
        mat_sel = self.f_mat.selected()
        tmat_sel = self.f_tmat.selected()
        row_m = np.array([mats[k] if k >= 0 else "" for k in rm], dtype=object)
        row_t = np.array([cfg["materiales"].get(m, "N/A") if m else "N/A" for m in row_m], dtype=object)
        mask &= np.isin(row_m, list(mat_sel)) & np.isin(row_t, list(tmat_sel))
        dests = [d for d in C.detected_destinations(plan) if d in self.f_dest.selected()
                 and cfg["destinos"].get(d, {}).get("tipo", "N/A") in self.f_tdest.selected()]
        idx = np.nonzero(mask)[0]
        cols = [plan.vcol(plan.dest_idx[plan.dest_names.index(d)]) for d in dests]
        X = V[np.ix_(idx, cols)] if len(idx) and cols else np.zeros((len(idx), len(cols)))
        per = self.per.get()
        if per == "sem":
            keys = list(range(1, 53))
            pk = plan.week[idx]
            labels = [f"Sem {k}" for k in keys]
            pname = "Semana"
        elif per == "mes":
            keys = sorted(months_sel)
            pk = month_of[idx]
            labels = [MONTHS[k - 1] for k in keys]
            pname = "Mes"
        else:
            keys = sorted(set(dates[ym].tolist()))
            pk = dates[idx]
            labels = [_dt.date.fromordinal(int(k)).strftime("%d/%m") for k in keys]
            pname = "Día"
        kpos = {k: i for i, k in enumerate(keys)}
        pidx = np.array([kpos.get(int(k), -1) for k in pk], dtype=int)
        ok = pidx >= 0
        stack = self.stack.get()
        if stack == "dest":
            groups = dests
            M = np.zeros((len(keys), len(dests)))
            if ok.any():
                np.add.at(M, pidx[ok], X[ok])
        else:
            rowsum = X.sum(axis=1) if X.size else np.zeros(len(idx))
            if stack == "mat":
                gv = row_m[idx]
                groups = [m for m in C.detected_materials(plan) if m in mat_sel]
            else:
                gv = np.array([plan.phase[i] for i in idx], dtype=object)
                groups = [p for p in plan.detected_phases() if p in ph_sel]
            gpos = {g: i for i, g in enumerate(groups)}
            gi = np.array([gpos.get(g, -1) for g in gv], dtype=int)
            M = np.zeros((len(keys), len(groups)))
            sel = ok & (gi >= 0)
            if sel.any():
                np.add.at(M, (pidx[sel], gi[sel]), rowsum[sel])
        if stack == "mat":
            colors = {g: (MINERAL_COLOR if cfg["materiales"].get(g) == "Mineral" else DESMONTE_COLOR) for g in groups}
            # tonos distintos por material dentro de cada tipo
            for i, g in enumerate(groups):
                colors[g] = SERIES[i % len(SERIES)]
        else:
            colors = {g: SERIES[i % len(SERIES)] for i, g in enumerate(groups)}
        series = [{"name": g, "values": M[:, i].tolist(), "color": colors[g]} for i, g in enumerate(groups)
                  if M[:, i].sum() > 0]
        stack_name = {"dest": "Destino", "mat": "Material", "fase": "Fase"}[stack]
        self.ck.title.configure(text=f"Tonelaje por {pname} y {stack_name} (t)")
        self.chart.set_data(labels, series)
        tot = M.sum(axis=1)
        nz = tot[tot > 0]
        mx = int(np.argmax(tot)) if len(tot) else 0
        mn_i = int(np.argmin(np.where(tot > 0, tot, np.inf))) if len(nz) else 0
        unit = {"sem": "Semanal", "mes": "Mensual", "dia": "Diario"}[per]
        vals = [("Tonelaje Movido Total", f"{tot.sum() / 1e6:,.2f} Mt",
                 f"{len(series)} {stack_name.lower()}{'es' if stack_name == 'Material' else 's'} · "
                 f"{len(ph_sel)} fases", None, False),
                (f"Tonelaje Promedio {unit}", f"{(nz.mean() if len(nz) else 0) / 1e3:,.1f} kt",
                 f"{len(nz)} {pname.lower()}s con carga", None, True),
                (f"Tonelaje Máximo {unit}", f"{(tot.max() if len(tot) else 0) / 1e3:,.1f} kt",
                 labels[mx] if len(tot) else "", mx, False),
                (f"Tonelaje Mínimo {unit}", f"{(nz.min() if len(nz) else 0) / 1e3:,.1f} kt",
                 labels[mn_i] if len(nz) else "", mn_i, False)]
        for (tl, v, s, sp), (t, val, sub, mark, avg) in zip(self.cards, vals):
            tl.configure(text=t)
            v.configure(text=val)
            s.configure(text=sub)
            sp.set(tot.tolist(), mark, avg)
        # tabla Fase × Material × período
        fases = [p for p in plan.detected_phases() if p in ph_sel]
        rowsum = X.sum(axis=1) if X.size else np.zeros(len(idx))
        rows = []
        mat_list = [m for m in C.detected_materials(plan) if m in mat_sel]
        ph_idx = np.array([plan.phase[i] for i in idx], dtype=object)
        mm = row_m[idx]
        for fz in fases:
            for m in mat_list:
                s = ok & (ph_idx == fz) & (mm == m)
                if not s.any():
                    continue
                v = np.zeros(len(keys))
                np.add.at(v, pidx[s], rowsum[s])
                if v.sum() <= 0:
                    continue
                rows.append([fz, m] + v.tolist() + [float(v.sum())])
        cols = [{"title": "Fase", "filter": True, "width": 90}, {"title": "Material", "filter": True, "width": 80}] + \
               [{"title": l, **NUM} for l in labels] + [{"title": "Total", **NUM, "width": 110}]
        total = ["Total General", ""] + [float(sum(r[2 + i] for r in rows)) for i in range(len(keys))] + \
                [float(sum(r[-1] for r in rows))]
        self.ct.title.configure(text=f"Tonelaje por Fase, Material y {pname} (t)")
        self.table.set_columns(cols)
        self.table.set_rows(rows, total, keep_state=False)


# ---------------------------------------------------------------------------
class ReorderView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        self.res = None
        bar = tk.Frame(self, bg=K["panel"])
        bar.pack(fill="x")
        tk.Frame(self, bg=K["border"], height=1).pack(fill="x")
        self.src = Segmented(bar, [("plan", "Plan (Orden Inicial)"), ("res", "Resultado (Reordenado)")], "res",
                             lambda v: self.redraw(), pady=2)
        self.src.pack(side="left", padx=10, pady=6)
        label(bar, "Semanas", F["base"], K["muted"]).pack(side="left", padx=(16, 4))
        self.w0 = ttk.Spinbox(bar, from_=1, to=52, width=4, command=self.redraw)
        self.w0.set("1")
        self.w0.pack(side="left")
        label(bar, "a", F["base"], K["muted"]).pack(side="left", padx=4)
        self.w1 = ttk.Spinbox(bar, from_=1, to=52, width=4, command=self.redraw)
        self.w1.set("52")
        self.w1.pack(side="left")
        for w in (self.w0, self.w1):
            w.bind("<Return>", lambda e: self.redraw())
            w.bind("<FocusOut>", lambda e: self.redraw())
        Btn(bar, "1 – 6", lambda: self._range(1, 6), padx=8, pady=2).pack(side="left", padx=(8, 2))
        Btn(bar, "Todas", lambda: self._range(1, 52), padx=8, pady=2).pack(side="left", padx=2)
        self.order = Segmented(bar, [("top", "Primer Polígono Arriba"), ("bottom", "Primer Polígono Abajo")], "top",
                               lambda v: self.redraw(), pady=2, padx=8)
        self.order.pack(side="right", padx=10)
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        b = sf.body
        self.note = autowrap(label(b, "", F["base"], K["muted"], bg=K["bg"], anchor="w", justify="left"))
        self.note.pack(fill="x", padx=14, pady=(10, 2))
        self.kpis = tk.Frame(b, bg=K["bg"])
        self.kpis.pack(fill="x", padx=14, pady=(4, 4))
        self.kc = []
        for i, t in enumerate(("Polígonos (Semanas Visibles)", "Inician con Mineral", "Inician con Desmonte",
                               "Intercambios de Filas", "Desvío vs Objetivo")):
            k = _kpi(self.kpis, t)
            k.grid(row=0, column=i, sticky="nsew", padx=(0, 8))
            self.kpis.grid_columnconfigure(i, weight=1, uniform="k")
            self.kc.append(k)
        self.c1 = Card(b, "Material por Polígono y Registro (Mt)")
        self.c1.pack(fill="x", padx=14, pady=6)
        self.chart = SegmentChart(self.c1.body, height=420, unit="Mt", yfmt=lambda v: f"{v:,.0f}" if v >= 10 else f"{v:,.1f}",
                                  xlabel="Semana", ylabel="Material (Mt)")
        self.chart.pack(fill="both", expand=True)
        self.c2 = Card(b, "Polígonos que Inician con Mineral por Semana (%)")
        self.c2.pack(fill="x", padx=14, pady=6)
        self.line = LineChart(self.c2.body, height=240, yfmt=lambda v: f"{v:,.0f} %", xlabel="Semana")
        self.line.fixed = (0, 100)
        self.line.pack(fill="both", expand=True)
        self.c3 = Card(b, "Resumen Semanal del Reordenamiento")
        self.c3.pack(fill="x", padx=14, pady=(6, 14))
        self.table = DataGrid(self.c3.body, [{"title": h, **({} if i == 0 else NUM)} for i, h in enumerate(REORDER_HEADERS)],
                              height=300, stretch=True, min_col=70)
        self.table.pack(fill="both", expand=True)

    def _range(self, a, b):
        self.w0.set(str(a))
        self.w1.set(str(b))
        self.redraw()

    def update(self, res, circ):
        self.res = res
        from .engine import row_types
        self.types = row_types(res.plan, res.cfg)
        self.redraw()
        self.table.set_rows(reorder_rows(res), None, keep_state=False)

    def redraw(self):
        res = self.res
        if res is None:
            return
        plan, cfg = res.plan, res.cfg
        try:
            a, b = sorted((max(1, min(52, int(self.w0.get()))), max(1, min(52, int(self.w1.get())))))
        except ValueError:
            a, b = 1, 52
        use_res = self.src.get() == "res"
        perm = res.perm if use_res else np.arange(plan.n)
        tot = plan.V[:, 0]
        types = self.types
        rm = plan.row_material()
        mats = plan.mat_names
        ym = plan.year_mask(cfg["general"].get("anio"))
        enabled = {p for p in plan.detected_phases() if cfg["fases"].get(p, True)}
        bars = {w: [] for w in range(a, b + 1)}
        n_poly = n_m = n_d = 0
        for (s, e) in plan.polygon_blocks():
            w = int(plan.week[s])
            if not (a <= w <= b) or not ym[s] or plan.phase[s] not in enabled:
                continue
            first = True
            start_t = None
            pos = 0
            for r in range(s, e):
                src = perm[r]
                t = types[src]
                if t not in ("M", "D"):
                    continue
                pos += 1
                if start_t is None:
                    start_t = t
                col = MINERAL_COLOR if t == "M" else DESMONTE_COLOR
                bars[w].append((tot[src] / 1e6, col, {"poly": plan.poly[r], "sec": fmt(plan.sec[r]),
                                                      "material": mats[rm[src]] if rm[src] >= 0 else "",
                                                      "tipo": "Mineral" if t == "M" else "Desmonte",
                                                      "t": float(tot[src]), "pos": pos, "poly_start": first}))
                first = False
            if start_t:
                n_poly += 1
                n_m += start_t == "M"
                n_d += start_t == "D"
        cats = [str(w) for w in range(a, b + 1)]
        self.chart.set_data(cats, [bars[w] for w in range(a, b + 1)],
                            [("Mineral", MINERAL_COLOR, "box"), ("Desmonte", DESMONTE_COLOR, "box")],
                            top_first=self.order.get() == "top")
        ex = cfg["experimento"]
        has = bool(res.reorder_table)
        self.c1.title.configure(text=f"Material por Polígono y Registro: Semanas {a} a {b} (Mt) · "
                                     f"{'Resultado' if use_res else 'Plan'}")
        if has:
            pct = float(ex["pct_mineral"])
            base = "polígonos con mineral y desmonte" if ex.get("base_pct", "elegibles") == "elegibles" \
                else "todos los polígonos de la semana"
            self.note.configure(text=f"Objetivo: {pct:g} % de polígonos inician con mineral y {100 - pct:g} % con "
                                     f"desmonte (base: {base}). Cada barra es una semana; los polígonos se apilan en el "
                                     f"orden del plan y cada segmento es un registro (fila). Solo cambia el orden de "
                                     f"mineral y desmonte dentro de cada polígono.", fg=K["muted"])
        else:
            self.note.configure(text="El experimento ejecutado no incluye Reordenamiento de Filas: Plan y Resultado "
                                     "muestran el mismo orden. Seleccione «2. Reordenamiento de Filas» u «4. Optimización "
                                     "Integral» en Función Objetivo ▸ Experimentos.", fg=K["warn"])
        tbl = [t for t in res.reorder_table if a <= t["semana"] <= b]
        sw = sum(t["intercambios"] for t in tbl)
        dev = sum(abs(t["diferencia"]) for t in tbl)
        _set_kpi(self.kc[0], f"{n_poly:,}")
        _set_kpi(self.kc[1], f"{n_m:,}  ({100 * n_m / n_poly:,.1f} %)" if n_poly else "0")
        _set_kpi(self.kc[2], f"{n_d:,}  ({100 * n_d / n_poly:,.1f} %)" if n_poly else "0")
        _set_kpi(self.kc[3], f"{sw:,}" if has else "—")
        _set_kpi(self.kc[4], f"{dev:,.1f} polígonos" if has else "—")
        if has:
            weeks = [t["semana"] for t in res.reorder_table]
            pa = [100 * (t["mineral_antes"] - (t["solo_mineral"] if t["base"] == t["ambos"] else 0)) / t["base"]
                  if t["base"] else None for t in res.reorder_table]
            pb = [t["pct_mineral"] if t["base"] else None for t in res.reorder_table]
            obj = [float(ex["pct_mineral"]) if t["base"] else None for t in res.reorder_table]
            self.line.set_data([str(w) for w in weeks],
                               [{"name": "Plan", "values": pa, "color": PLAN_COLOR},
                                {"name": "Resultado", "values": pb, "color": SCEN_COLOR},
                                {"name": "Objetivo", "values": obj, "color": K["bad_fg"], "dash": (4, 3), "width": 1.5}])
        else:
            self.line.set_data([], [])


# ---------------------------------------------------------------------------
class ValidationView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        body = tk.Frame(self, bg=K["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=12)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        c1 = Card(body, "Validaciones (Reglas Rígidas y Metas)")
        c1.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.g1 = DataGrid(c1.body, [{"title": "Indicador", "max": 420}, {"title": "Circuito", "filter": True},
                                     {"title": "Estado", "align": "center", "filter": True}, {"title": "Detalle", "max": 700}],
                           cell_style=self._st1, height=290)
        self.g1.pack(fill="both", expand=True)
        self.c2 = Card(body, "Estado por Período y Receptor")
        self.c2.grid(row=1, column=0, sticky="nsew")
        self.per = Segmented(self.c2.head, [("semanal", "Semanal"), ("diario", "Diario")], "semanal",
                             lambda v: self._fill2(), pady=2)
        self.per.pack(side="left", padx=12)
        self.cnt = label(self.c2.head, "", F["small"], K["muted"])
        self.cnt.pack(side="right")
        self.g2 = DataGrid(self.c2.body, [], cell_style=self._st2, height=320,
                           status=lambda a, b: self.cnt.configure(text=f"{a:,} de {b:,} registros"))
        self.g2.pack(fill="both", expand=True)

    def _st1(self, row, ci):
        if ci == 2:
            return (K["ok_bg"], K["ok_fg"]) if row[2] == "Ok" else (K["bad_bg"], K["bad_fg"])
        return None

    def _st2(self, row, ci):
        if ci == len(row) - 1:
            return (K["ok_bg"], K["ok_fg"]) if row[ci] == "Ok" else (K["bad_bg"], K["bad_fg"])
        return None

    def update(self, res, circ):
        self.res, self.circ = res, circ
        rows = [[v["indicador"], v["circuito"], v["estado"], v["detalle"]] for v in res.validations]
        self.g1.set_rows(rows, None, keep_state=False)
        self.per.set_enabled(circ in res.daily_status)
        if circ not in res.daily_status:
            self.per.set("semanal")
        self._fill2()

    def _fill2(self):
        res, circ = self.res, self.circ
        daily = self.per.get() == "diario"
        src = (res.daily_status if daily else res.status).get(circ, [])
        self.c2.title.configure(text=f"{circ}: Estado por {'Día' if daily else 'Semana'} y Receptor (t)")
        cols = [{"title": "Día" if daily else "Semana", "filter": True}, {"title": "Receptor", "filter": True},
                {"title": "Plan", **NUM}, {"title": "Escenario", **NUM}, {"title": "Mínimo", **NUM},
                {"title": "Promedio", **NUM}, {"title": "Máximo", **NUM},
                {"title": "Dif. vs Promedio", **NUM, "fmt": fmt_signed}, {"title": "Estado", "align": "center", "filter": True}]
        rows = [[r["periodo"], r["receptor"], r["plan"], r["resultado"], r["min"], r["prom"], r["max"],
                 r["resultado"] - r["prom"], r["estado"]] for r in src]
        self.g2.set_columns(cols)
        self.g2.set_rows(rows, None, keep_state=False)


# ---------------------------------------------------------------------------
class MovesView(tk.Frame):
    def __init__(self, parent, page):
        super().__init__(parent, bg=K["bg"])
        top = tk.Frame(self, bg=K["bg"])
        top.pack(fill="x", padx=14, pady=(10, 4))
        self.t = label(top, "Movimientos", F["section"], bg=K["bg"])
        self.t.pack(side="left")
        self.cnt = label(top, "", F["small"], K["muted"], bg=K["bg"])
        self.cnt.pack(side="right")
        cols = []
        for h in MOVE_HEADERS:
            c = {"title": h}
            if h in ("Fila Excel", "Semana", "# Sec", "Toneladas"):
                c.update(NUM)
            if h in ("Semana", "Fase", "Polígono / Origen", "Material", "Etapa", "Desde", "Hacia", "Fecha"):
                c["filter"] = True
            cols.append(c)
        self.grid_ = DataGrid(self, cols, status=lambda a, b: self.cnt.configure(text=f"{a:,} de {b:,} movimientos"))
        self.grid_.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def update(self, res, circ):
        info = res.circuit_info(circ)
        ds = set(info.dests)
        rows = [r for r in moves_rows(res) if r[8] in ds]
        self.t.configure(text=f"{circ}: Movimientos (traslados dentro de cada fila)")
        self.grid_.set_rows(rows, None, keep_state=False)
