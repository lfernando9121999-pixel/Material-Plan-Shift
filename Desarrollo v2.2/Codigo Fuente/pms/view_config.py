"""Pestañas Restricciones y Función Objetivo."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import config as C
from .dialogs import MatrixDialog
from .theme import C as K, F, MINERAL_COLOR, DESMONTE_COLOR
from .widgets import Btn, Card, Check, PriorityList, ScrollFrame, Segmented, autowrap, label, set_tree_state

CIRC_COLOR = {"Mineral": MINERAL_COLOR, "Desmonte": DESMONTE_COLOR}

MODE_HELP = {
    "fijo": "Garantiza que el material de cada receptor sea el valor asignado (forzado). Minimiza los movimientos "
            "y las brechas para acercar cada receptor a su banda semanal.",
    "balanceado": "Si algún receptor está limitado para recibir material, se balancea en función del total de "
                  "receptores. Con dos o más receptores agrega una preferencia de reparto parejo; no obliga a "
                  "dejarlos iguales, pero cumple el objetivo total.",
}
GRAN_HELP = {
    "semanal": "Se aplica a cada receptor del circuito. Mt se convierte a toneladas multiplicando por 1 000 000.",
    "diario": "Tras el cálculo semanal, intenta llenar días bajos y drenar días altos dentro de la misma semana. "
              "El presupuesto es el menor entre faltante y exceso. Conserva los totales semanales y anuales; si no "
              "cierra una semana, revierte ese suavizado.",
}


def _wrap_checks(parent, items, on_change, bg):
    """Casillas que fluyen en varias filas."""
    for w in parent.winfo_children():
        w.destroy()
    row = None
    checks = {}
    for i, (name, val) in enumerate(items):
        if i % 6 == 0:
            row = tk.Frame(parent, bg=bg)
            row.pack(fill="x", pady=2)
        ch = Check(row, name, val, lambda v, n=name: on_change(n, v), bg=bg)
        ch.pack(side="left", padx=(0, 22))
        checks[name] = ch
    return checks


# ===========================================================================
class RestrictionsPage(tk.Frame):
    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        body = sf.body
        ph = Card(body, "Fases en Evaluación")
        ph.pack(fill="x", padx=14, pady=(12, 8))
        label(ph.body, "Registros únicos de la columna Fase (las filas con Fase vacía o 0 no se consideran).",
              F["small"], K["muted"]).pack(anchor="w", pady=(0, 6))
        self.ph_box = tk.Frame(ph.body, bg=K["panel"])
        self.ph_box.pack(fill="x")

        grid = tk.Frame(body, bg=K["bg"])
        grid.pack(fill="x", padx=14, pady=4)
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")
        self.cards = {}
        for i, circ in enumerate(C.CIRCUITS):
            outer = tk.Frame(grid, bg=K["border"])
            outer.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 6 if i == 0 else 0))
            inner = tk.Frame(outer, bg=K["panel"])
            inner.pack(fill="both", expand=True, padx=1, pady=1)
            bar = tk.Frame(inner, bg=CIRC_COLOR[circ], height=3)
            bar.pack(fill="x")
            head = tk.Frame(inner, bg=K["panel"])
            head.pack(fill="x", padx=12, pady=(10, 4))
            ttl = label(head, circ.upper(), F["section"])
            ttl.pack(side="left")
            chk = Check(head, "Activar Balanceo", True, lambda v, c=circ: self._activate(c, v), font=F["small"])
            chk.pack(side="right")
            content = tk.Frame(inner, bg=K["panel"])
            content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            self.cards[circ] = {"inner": inner, "bar": bar, "head": head, "title": ttl, "check": chk,
                                "content": content}

        rules = Card(body, "Reglas Rígidas Aplicadas por el Programa")
        rules.pack(fill="x", padx=14, pady=(8, 14))
        for t in (
            "Oferta y devolución: en una semana, cada donante cede como máximo su tonelaje disponible de cada material; "
            "cada receptor devuelve como máximo su tonelaje base de cada material.",
            "Intercambio directo entre receptores: solo con el excedente de un receptor por encima de su objetivo semanal.",
            "Conservación de masa: el total de cada fila no cambia; las columnas de material no cambian; el total anual de "
            "cada donante y de cada receptor se conserva exactamente (cambia la distribución semanal, el neto anual es cero).",
            "Cada fila tiene un único material, que puede ir a varios destinos (no al revés).",
            "Matriz de Material por Destino: una combinación desmarcada no se modifica nunca.",
        ):
            r = tk.Frame(rules.body, bg=K["panel"])
            r.pack(fill="x", pady=2)
            label(r, "•", F["bold"], K["accent"]).pack(side="left", anchor="n", padx=(0, 6))
            autowrap(label(r, t, F["base"], K["text"], justify="left", anchor="w")).pack(side="left", fill="x", expand=True)
        self.refresh()

    def _activate(self, circ, v):
        self.ws.cfg["circuitos"][circ]["activo"] = v
        self.ws.changed(refresh=False)
        self.ws.stale.update(k for k in ("obj", "inputs") if k in self.ws.pages)
        self._fill_card(circ, self.cards[circ])

    def _phase(self, name, v):
        self.ws.cfg["fases"][name] = v
        self.ws.changed(refresh=False)
        self.ws.stale.update(k for k in ("obj", "inputs") if k in self.ws.pages)

    def refresh(self):
        key = self.ws.struct_key()
        if key == getattr(self, "_key", None):
            return
        self._key = key
        plan, cfg = self.ws.plan, self.ws.cfg
        if plan is None:
            for w in self.ph_box.winfo_children():
                w.destroy()
            label(self.ph_box, "Sin datos: seleccione el Input para Análisis.", F["base"], K["muted"]).pack(anchor="w")
        else:
            _wrap_checks(self.ph_box, [(p, cfg["fases"].get(p, True)) for p in plan.detected_phases()], self._phase,
                         K["panel"])
        for circ, d in self.cards.items():
            self._fill_card(circ, d)

    def _fill_card(self, circ, d):
        plan, cfg = self.ws.plan, self.ws.cfg
        cont = d["content"]
        for w in cont.winfo_children():
            w.destroy()
        active = cfg["circuitos"][circ]["activo"]
        d["check"].set(active)
        info = C.circuit_info(plan, cfg, circ) if plan is not None else None
        has = info is not None and bool(info.receptors)
        en = active and has
        bg = K["panel"] if en else K["inactive_bg"]
        for k in ("inner", "head", "content"):
            d[k].configure(bg=bg)
        d["title"].configure(bg=bg, fg=K["text"] if en else K["disabled"])
        d["check"].set_bg(bg)
        d["check"].set_enabled(has)
        d["bar"].configure(bg=CIRC_COLOR[circ] if en else K["border"])
        if info is None:
            label(cont, "Sin datos.", F["base"], K["disabled"], bg=bg).pack(anchor="w")
            return
        if not has:
            label(cont, "Sin receptores asignados (Inputs ▸ Configuración de Destinos).", F["base"], K["disabled"],
                  bg=bg).pack(anchor="w")
            return

        def line(title, items):
            r = tk.Frame(cont, bg=bg)
            r.pack(fill="x", pady=2)
            label(r, f"{title}:", F["bold"], K["text"] if en else K["disabled"], bg=bg, width=12, anchor="w").pack(side="left")
            autowrap(label(r, ", ".join(items) if items else "—", F["base"], K["text"] if en else K["disabled"], bg=bg,
                           justify="left", anchor="w")).pack(side="left", fill="x", expand=True)
        line("Receptores", info.receptors)
        line("Donantes", info.donors)
        line("Materiales", info.materials)
        tot = len(info.dests) * len(info.materials)
        ok = sum(1 for x in info.dests for m in info.materials if C.allowed(cfg, circ, x, m))
        r = tk.Frame(cont, bg=bg)
        r.pack(fill="x", pady=(10, 0))
        b = Btn(r, "Matriz de Material por Destino", lambda: self._matrix(circ))
        b.pack(side="left")
        b.set_enabled(en)
        label(r, f"{ok} de {tot} combinaciones habilitadas", F["small"], K["muted"] if en else K["disabled"],
              bg=bg).pack(side="left", padx=10)

    def _matrix(self, circ):
        def apply(mat):
            self.ws.cfg["circuitos"][circ]["matriz"] = mat
            self.ws.changed(refresh=False)
            self._fill_card(circ, self.cards[circ])
        MatrixDialog(self, self.ws.plan, self.ws.cfg, circ, apply)


# ===========================================================================
class ObjectivePage(tk.Frame):
    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        strip = tk.Frame(self, bg=K["panel"])
        strip.pack(fill="x")
        self.sub = {}
        self.cur = None
        self.pages = {}
        for key, text in (("meta", "Meta Física"), ("exp", "Experimentos")):
            lb = tk.Label(strip, text=text, font=F["base"], bg=K["panel"], fg=K["text"], padx=14, pady=7, cursor="hand2")
            lb.pack(side="left")
            lb.bind("<ButtonRelease-1>", lambda e, k=key: self.show(k))
            self.sub[key] = lb
        tk.Frame(self, bg=K["border"], height=1).pack(fill="x")
        self.host = tk.Frame(self, bg=K["bg"])
        self.host.pack(fill="both", expand=True)
        self.pages["meta"] = MetaPage(self.host, ws)
        self.pages["exp"] = ExperimentsPage(self.host, ws)
        self.show("meta")

    def show(self, key):
        if self.cur:
            self.pages[self.cur].pack_forget()
        self.cur = key
        self.pages[key].pack(fill="both", expand=True)
        for k, lb in self.sub.items():
            on = k == key
            lb.configure(font=F["bold"] if on else F["base"], fg=K["accent"] if on else K["text"])

    def refresh(self):
        for p in self.pages.values():
            p.refresh()


class MetaPage(tk.Frame):
    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        self.grid_ = tk.Frame(sf.body, bg=K["bg"])
        self.grid_.pack(fill="both", expand=True, padx=14, pady=12)
        self.grid_.grid_columnconfigure(0, weight=1, uniform="m")
        self.grid_.grid_columnconfigure(1, weight=1, uniform="m")
        self.blocks = {}
        self.refresh()

    def refresh(self):
        key = self.ws.struct_key()
        if key == getattr(self, "_key", None) and self.blocks:
            for b in self.blocks.values():
                b._refresh_state()          # solo textos dependientes (p. ej. año)
            return
        self._key = key
        for w in self.grid_.winfo_children():
            w.destroy()
        for i, circ in enumerate(C.CIRCUITS):
            self.blocks[circ] = CircuitObjective(self.grid_, self.ws, circ)
            self.blocks[circ].grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 6 if i == 0 else 0))


class CircuitObjective(tk.Frame):
    def __init__(self, parent, ws, circ):
        super().__init__(parent, bg=K["border"])
        self.ws, self.circ = ws, circ
        cfg, plan = ws.cfg, ws.plan
        cc = cfg["circuitos"][circ]
        info = C.circuit_info(plan, cfg, circ) if plan is not None else None
        self.enabled = bool(cc["activo"] and info is not None and info.receptors)
        bg = K["panel"] if self.enabled else K["inactive_bg"]
        inner = tk.Frame(self, bg=bg)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(inner, bg=CIRC_COLOR[circ] if self.enabled else K["border"], height=3).pack(fill="x")
        head = tk.Frame(inner, bg=bg)
        head.pack(fill="x", padx=14, pady=(10, 2))
        label(head, circ.upper(), F["section"], K["text"] if self.enabled else K["disabled"], bg=bg).pack(side="left")
        if not self.enabled:
            why = ("Balanceo desactivado en Restricciones" if not cc["activo"]
                   else "Sin receptores asignados (Inputs ▸ Configuración de Destinos)")
            label(head, f"  ·  Inactivo: {why}", F["small"], K["disabled"], bg=bg).pack(side="left")
        body = tk.Frame(inner, bg=bg)
        body.pack(fill="both", expand=True, padx=14, pady=(4, 14))
        self.body = body

        def sec(text):
            label(body, text, F["bold"], K["text"], bg=bg).pack(anchor="w", pady=(10, 4))

        sec("Modo de Cumplimiento")
        self.mode = Segmented(body, [("fijo", "Objetivo Fijo"), ("balanceado", "Balanceado")], cc["modo"], self._mode,
                              padx=22)
        self.mode.pack(anchor="w")
        self.mode_help = autowrap(label(body, MODE_HELP[cc["modo"]], F["small"], K["muted"], bg=bg, justify="left",
                                        anchor="w"))
        self.mode_help.pack(fill="x", pady=(4, 0))

        sec("Nivel de Granularidad")
        self.gran = Segmented(body, [("semanal", "Semanal"), ("diario", "Diario")], cc["granularidad"], self._gran,
                              padx=22)
        self.gran.pack(anchor="w")
        self.gran_help = autowrap(label(body, GRAN_HELP[cc["granularidad"]], F["small"], K["muted"], bg=bg,
                                        justify="left", anchor="w"))
        self.gran_help.pack(fill="x", pady=(4, 6))

        boxes = tk.Frame(body, bg=bg)
        boxes.pack(fill="x", pady=4)
        boxes.grid_columnconfigure(0, weight=1, uniform="x")
        boxes.grid_columnconfigure(1, weight=1, uniform="x")
        self.entries = {}
        self.box_frames = {}
        for j, (kind, title, unit) in enumerate((("semanal", "SEMANAL", "Mt/sem por receptor"),
                                                  ("diario", "DIARIO", "Mt/día por receptor"))):
            fr = tk.Frame(boxes, bg=K["border"])
            fr.grid(row=0, column=j, sticky="nsew", padx=(0 if j == 0 else 5, 5 if j == 0 else 0))
            fi = tk.Frame(fr, bg=bg)
            fi.pack(fill="both", expand=True, padx=1, pady=1)
            label(fi, title, F["bold"], bg=bg).pack(anchor="w", padx=10, pady=(8, 0))
            label(fi, unit, F["small"], K["muted"], bg=bg).pack(anchor="w", padx=10)
            for key, txt in (("max", "Máximo"), ("prom", "Promedio (Deseado)"), ("min", "Mínimo")):
                r = tk.Frame(fi, bg=bg)
                r.pack(fill="x", padx=10, pady=3)
                label(r, txt, F["base"], bg=bg, width=18, anchor="w").pack(side="left")
                e = ttk.Entry(r, width=10, justify="right")
                v = cc[kind].get(key)
                e.insert(0, "" if v is None else f"{v}")
                e.pack(side="left")
                e.bind("<KeyRelease>", lambda ev, k=kind, kk=key, e=e: self._value(k, kk, e))
                e.bind("<FocusOut>", lambda ev, k=kind, kk=key, e=e: self._value(k, kk, e))
                label(r, "Mt", F["small"], K["muted"], bg=bg).pack(side="left", padx=4)
                self.entries[(kind, key)] = e
            tk.Frame(fi, bg=bg, height=6).pack()
            self.box_frames[kind] = (fr, fi)
        self.err = label(body, "", F["small"], K["required"], bg=bg, anchor="w")
        self.err.pack(fill="x")
        self.annual = autowrap(label(body, "", F["small"], K["muted"], bg=bg, anchor="w", justify="left"))
        self.annual.pack(fill="x", pady=(2, 0))

        tk.Frame(body, bg=K["border"], height=1).pack(fill="x", pady=(12, 8))
        ph = tk.Frame(body, bg=bg)
        ph.pack(fill="x")
        label(ph, "Priorización", F["section"], bg=bg).pack(anchor="w")
        autowrap(label(ph, "Orden de búsqueda por receptor: 1. Fase → 2. Donantes → 3. Materiales. Arrastre ≡ (o "
                           "Alt+↑/↓) para ordenar; la casilla habilita el elemento y el interruptor activa el bloque.",
                       F["small"], K["muted"], bg=bg, justify="left", anchor="w")).pack(fill="x")
        sel = tk.Frame(body, bg=bg)
        sel.pack(fill="x", pady=(8, 6))
        label(sel, "Receptor", F["base"], bg=bg).pack(side="left", padx=(0, 8))
        recs = info.receptors if info else []
        self.rec = ttk.Combobox(sel, state="readonly", values=recs, width=24)
        self.rec.pack(side="left")
        self.rec.bind("<<ComboboxSelected>>", lambda e: self._show_prio())
        self.copy_btn = Btn(sel, "Copiar a Todos los Receptores", self._copy_all,
                            tip="Copia el orden y la selección del receptor actual a los demás receptores del circuito")
        self.copy_btn.pack(side="left", padx=8)
        lists = tk.Frame(body, bg=bg)
        lists.pack(fill="both", expand=True)
        self.lists = {}
        for j, (key, title) in enumerate(C.PRIO_BLOCKS):
            lists.grid_columnconfigure(j, weight=1, uniform="p")
            pl = PriorityList(lists, title, lambda items, act, k=key: self._prio_changed(k, items, act))
            pl.grid(row=0, column=j, sticky="nsew", padx=(0 if j == 0 else 4, 0))
            self.lists[key] = pl
        if recs:
            self.rec.set(recs[0])
        self._show_prio()
        self._refresh_state()
        if not self.enabled:
            set_tree_state(body, False)
            for pl in self.lists.values():
                pl.set_enabled(False)
            self.copy_btn.set_enabled(False)

    # ---- eventos ------------------------------------------------------------
    def _mode(self, v):
        self.ws.cfg["circuitos"][self.circ]["modo"] = v
        self.mode_help.configure(text=MODE_HELP[v])
        self.ws.changed(refresh=False)

    def _gran(self, v):
        self.ws.cfg["circuitos"][self.circ]["granularidad"] = v
        self.gran_help.configure(text=GRAN_HELP[v])
        self._refresh_state()
        self.ws.changed(refresh=False)

    def _value(self, kind, key, e):
        t = e.get().strip().replace(",", ".")
        cc = self.ws.cfg["circuitos"][self.circ]
        try:
            v = float(t) if t else None
        except ValueError:
            v = None
        if cc[kind].get(key) != v:
            cc[kind][key] = v
            self.ws.changed(refresh=False)
        self._refresh_state()

    def _refresh_state(self):
        cc = self.ws.cfg["circuitos"][self.circ]
        daily = cc["granularidad"] == "diario"
        fr, fi = self.box_frames["diario"]
        if self.enabled:
            set_tree_state(fi, daily)
            fr.configure(bg=K["accent"] if daily else K["border"])
            self.box_frames["semanal"][0].configure(bg=K["accent"] if not daily else K["border"])
        errs = []
        for kind in ("semanal", "diario"):
            if kind == "diario" and not daily:
                continue
            if C.objective_values(self.ws.cfg, self.circ, kind) is None:
                errs.append(f"Revise la meta {kind}: debe cumplirse Mínimo ≤ Promedio ≤ Máximo (valores ≥ 0).")
        self.err.configure(text="  ".join(errs) if self.enabled else "")
        plan = self.ws.plan
        info = C.circuit_info(plan, self.ws.cfg, self.circ) if plan is not None else None
        ov = C.objective_values(self.ws.cfg, self.circ, "semanal")
        if info and info.receptors and ov:
            n = len(info.receptors)
            ym = plan.year_mask(self.ws.cfg["general"].get("anio"))
            D = plan.dest_matrix()
            base = sum(D[ym, plan.dest_names.index(r)].sum() for r in info.receptors)
            self.annual.configure(text=f"≈ {ov[1] * n * 52 / 1e6:,.1f} Mt/año deseado ({n} receptor"
                                       f"{'es' if n > 1 else ''} × 52 semanas)   ·   Plan base de receptores: "
                                       f"{base / 1e6:,.1f} Mt/año (se conserva exactamente)")
        else:
            self.annual.configure(text="")

    def _show_prio(self):
        r = self.rec.get()
        prio = self.ws.cfg["circuitos"][self.circ]["prioridad"].get(r, {})
        for key, pl in self.lists.items():
            blk = prio.get(key, {"activo": True, "items": []})
            pl.set_items(blk["items"], blk.get("activo", True))

    def _prio_changed(self, key, items, active):
        r = self.rec.get()
        if not r:
            return
        blk = self.ws.cfg["circuitos"][self.circ]["prioridad"].setdefault(r, {}).setdefault(key, {})
        blk["items"] = [list(x) for x in items]
        blk["activo"] = active
        self.ws.changed(refresh=False)

    def _copy_all(self):
        r = self.rec.get()
        pr = self.ws.cfg["circuitos"][self.circ]["prioridad"]
        if r not in pr:
            return
        import copy
        for other in list(pr):
            if other != r:
                pr[other] = copy.deepcopy(pr[r])
        self.ws.changed(refresh=False)
        self.ws.app.notify(f"Priorización de {r} copiada a los demás receptores")


# ===========================================================================
class ExperimentsPage(tk.Frame):
    """Tarjetas de experimentos. Se construyen una sola vez: seleccionar una tarjeta solo repinta
    (sin destruir widgets), para que el cambio sea instantáneo y sin parpadeo."""

    DESCS = {
        "convencional": "Balance de materiales por programa lineal (52 semanas a la vez): mueve tonelaje entre "
                        "donantes y receptores dentro de cada fila para acercar cada receptor a su meta, respetando "
                        "las reglas rígidas y la priorización. Sin opciones adicionales.",
        "reordenamiento": "Convencional + Reordenamiento de Filas: dentro de cada polígono permuta el contenido "
                          "completo de los registros (desde «Total Material» hasta el último material) para "
                          "controlar si el polígono inicia con mineral o con desmonte. No cambia toneladas, semana, "
                          "fase, malla, polígono ni # Sec.",
        "aleatoria": "Convencional + Asignación Balanceada Aleatoria: reparte de nuevo, al azar, el tonelaje de cada "
                     "fila entre los destinos del circuito según el grado de apertura; los totales por semana, "
                     "material, fase y destino se reajustan para seguir cumpliendo objetivos y reglas rígidas.",
        "integral": "Optimización Integral: Convencional + Asignación Balanceada Aleatoria + Reordenamiento de "
                    "Filas (en ese orden), con los inputs de ambas opciones.",
    }

    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        self.body = sf.body
        self.cards = {}
        self.syncers = []
        self.prio_labels = []
        self._build()
        self._paint()

    def _build(self):
        label(self.body, "Seleccione el experimento (selección única) y pulse «Ejecutar Experimento».", F["base"],
              K["muted"], bg=K["bg"]).pack(anchor="w", padx=16, pady=(12, 4))
        for key, title in C.EXPERIMENTS.items():
            outer = tk.Frame(self.body, bg=K["border"])
            outer.pack(fill="x", padx=14, pady=5)
            inner = tk.Frame(outer, bg=K["panel"])
            inner.pack(fill="both", expand=True, padx=2, pady=2)
            head = tk.Frame(inner, bg=K["panel"], cursor="hand2")
            head.pack(fill="x", padx=12, pady=(10, 2))
            cv = tk.Canvas(head, width=16, height=16, bg=K["panel"], highlightthickness=0)
            cv.pack(side="left", padx=(0, 8))
            label(head, title, F["section"], bg=K["panel"]).pack(side="left")
            d = autowrap(label(inner, self.DESCS[key], F["base"], K["muted"], bg=K["panel"], justify="left",
                               anchor="w"))
            d.pack(fill="x", padx=36, pady=(0, 8))
            for w in (head, cv, d, inner) + tuple(head.winfo_children()):
                w.bind("<ButtonRelease-1>", lambda e, k=key: self._select(k))
            opts = tk.Frame(inner, bg=K["panel"])
            opts.pack(fill="x", padx=36, pady=(0, 10))
            if key in ("reordenamiento", "integral"):
                self._reorder_inputs(opts, K["panel"])
            if key in ("aleatoria", "integral"):
                self._random_inputs(opts, K["panel"])
            self.cards[key] = {"outer": outer, "inner": inner, "radio": cv, "opts": opts, "sel": None}
        foot = tk.Frame(self.body, bg=K["bg"])
        foot.pack(fill="x", padx=14, pady=(10, 18))
        Btn(foot, "▶  Ejecutar Experimento", self.ws.run, kind="primary", padx=26, pady=8, font=F["title"],
            tip="Ejecuta el experimento seleccionado (F5)").pack(side="right")
        self.status = label(foot, "", F["base"], K["muted"], bg=K["bg"])
        self.status.pack(side="right", padx=12)

    def refresh(self):
        for fn in self.syncers:
            fn()
        self._paint()

    def _paint(self):
        cur = self.ws.cfg["experimento"]["tipo"]
        for key, c in self.cards.items():
            sel = key == cur
            if c["sel"] == sel:
                continue
            c["sel"] = sel
            bg = K["accent_soft"] if sel else K["panel"]
            c["outer"].configure(bg=K["accent"] if sel else K["border"])
            _recolor(c["inner"], bg)
            cv = c["radio"]
            cv.delete("all")
            cv.create_oval(2, 2, 14, 14, outline=K["accent"] if sel else K["muted"], width=1.5)
            if sel:
                cv.create_oval(5, 5, 11, 11, fill=K["accent"], outline="")
            set_tree_state(c["opts"], sel)

    def _select(self, key):
        if self.ws.cfg["experimento"]["tipo"] != key:
            self.ws.cfg["experimento"]["tipo"] = key
            self.ws.changed(refresh=False)
            for fn in self.syncers:
                fn()
            self._paint()

    def _reorder_inputs(self, parent, bg):
        ex = self.ws.cfg["experimento"]
        r = tk.Frame(parent, bg=bg)
        r.pack(fill="x", pady=3)
        label(r, "Polígonos que inician con mineral (%)", F["base"], bg=bg).pack(side="left")
        e = ttk.Spinbox(r, from_=0, to=100, increment=5, width=7, justify="right")
        e.set(f"{float(ex['pct_mineral']):g}")
        e.pack(side="left", padx=8)
        out = label(r, "", F["bold"], bg=bg)

        def upd(*_):
            try:
                v = float(e.get().replace(",", "."))
                if not 0 <= v <= 100:
                    raise ValueError
                txt, fg = f"Polígonos que inician con desmonte (%):  {100 - v:g}", K["text"]
                if v != ex["pct_mineral"]:
                    ex["pct_mineral"] = v
                    self.ws.changed(refresh=False)
            except ValueError:
                txt, fg = "Ingrese un valor entre 0 y 100", K["required"]
            if out.cget("text") != txt:
                out.configure(text=txt, fg=fg)
        e.configure(command=upd)
        e.bind("<KeyRelease>", upd)
        out.pack(side="left", padx=16)
        upd()

        def sync_pct():
            v = f"{float(ex['pct_mineral']):g}"
            if e.get() != v:
                e.set(v)
                upd()
        self.syncers.append(sync_pct)
        r2 = tk.Frame(parent, bg=bg)
        r2.pack(fill="x", pady=3)
        label(r2, "Base del porcentaje", F["base"], bg=bg).pack(side="left", padx=(0, 8))
        seg = Segmented(r2, [("elegibles", "Polígonos con mineral y desmonte"), ("todos", "Todos los polígonos de la semana")],
                        ex.get("base_pct", "elegibles"), lambda v: self._set("base_pct", v), padx=10, pady=2)
        seg.pack(side="left")
        self.syncers.append(lambda: seg.set(ex.get("base_pct", "elegibles")))
        r3 = tk.Frame(parent, bg=bg)
        r3.pack(fill="x", pady=(6, 3))
        Btn(r3, "Priorización de Destinos en la Permutación…", self.open_dest_priority,
            tip="Orden de los registros dentro de cada polígono (de arriba hacia abajo) según su destino, para los "
                "polígonos que inician con desmonte y los que inician con mineral").pack(side="left")
        pl = label(r3, "", F["small"], K["muted"], bg=bg, anchor="w")
        pl.pack(side="left", padx=10)
        self.prio_labels.append(pl)
        self.syncers.append(self._prio_summary)
        self._prio_summary()
        autowrap(label(parent, "Los polígonos con un solo tipo de material conservan su inicio. Si una semana no permite la "
                               "proporción exacta, se aplica el reparto factible más cercano y se reporta la diferencia.",
                       F["small"], K["muted"], bg=bg, justify="left", anchor="w")).pack(fill="x", pady=(2, 4))

    def _prio_summary(self):
        pd = self.ws.cfg["experimento"].get("prio_destinos") or {}
        if not pd.get("activo"):
            txt = "Priorización de destinos: desactivada (intercambio mínimo del primer registro)"
        else:
            parts = []
            for key, name in (("desmonte", "Inicio Desmonte"), ("mineral", "Inicio Mineral")):
                blk = pd.get(key) or {}
                items = [n for n, on in blk.get("items", []) if on]
                if blk.get("activo", True) and items:
                    parts.append(f"{name}: " + " → ".join(items[:4]) + (" → …" if len(items) > 4 else ""))
                else:
                    parts.append(f"{name}: sin priorización")
            txt = "Activa · " + "   |   ".join(parts)
        for pl in self.prio_labels:
            if pl.cget("text") != txt:
                pl.configure(text=txt)

    def open_dest_priority(self, first_time=False, after=None):
        from .dialogs import DestPriorityDialog
        if self.ws.plan is None:
            return

        def apply(state):
            self.ws.cfg["experimento"]["prio_destinos"] = state
            self.ws.changed(refresh=False)
            self._prio_summary()
        DestPriorityDialog(self, self.ws.plan, self.ws.cfg, apply, first_time=first_time)
        if after:
            after()

    def _random_inputs(self, parent, bg):
        ex = self.ws.cfg["experimento"]
        r = tk.Frame(parent, bg=bg)
        r.pack(fill="x", pady=3)
        label(r, "Grado de Apertura y Asignación de Destinos", F["base"], bg=bg).pack(side="left", padx=(0, 8))
        seg = Segmented(r, list(C.APERTURAS.items()), ex.get("apertura", "moderado"), lambda v: self._set("apertura", v),
                        padx=16, pady=2)
        seg.pack(side="left")
        self.syncers.append(lambda: seg.set(ex.get("apertura", "moderado")))
        label(r, "Semilla", F["base"], bg=bg).pack(side="left", padx=(24, 6))
        s = ttk.Spinbox(r, from_=0, to=10 ** 9, width=8, justify="right")
        s.set(str(ex.get("semilla", 1)))
        s.pack(side="left")

        def seed(*_):
            try:
                v = int(s.get())
            except ValueError:
                return
            if v != ex.get("semilla"):
                ex["semilla"] = v
                self.ws.changed(refresh=False)
        s.configure(command=seed)
        s.bind("<KeyRelease>", seed)

        def sync_seed():
            if s.get() != str(ex.get("semilla", 1)):
                s.set(str(ex.get("semilla", 1)))
        self.syncers.append(sync_seed)
        autowrap(label(parent, "Estricto: el material de cada fila se reparte en los menos destinos posibles · Moderado: en la "
                               "mitad de los destinos posibles · Flexible: en la máxima cantidad de destinos posibles. La "
                               "misma semilla reproduce el mismo resultado.", F["small"], K["muted"], bg=bg,
                       justify="left", anchor="w")).pack(fill="x", pady=(2, 4))

    def _set(self, k, v):
        self.ws.cfg["experimento"][k] = v
        self.ws.changed(refresh=False)
        for fn in self.syncers:
            fn()


def _recolor(w, bg):
    """Cambia el fondo de un bloque sin reconstruirlo."""
    if isinstance(w, Check):
        w.set_bg(bg)
        return
    if isinstance(w, Segmented):
        return
    if isinstance(w, (tk.Frame, tk.Label, tk.Canvas)) and not isinstance(w, Btn):
        try:
            w.configure(bg=bg)
        except tk.TclError:
            pass
    for c in w.winfo_children():
        _recolor(c, bg)
