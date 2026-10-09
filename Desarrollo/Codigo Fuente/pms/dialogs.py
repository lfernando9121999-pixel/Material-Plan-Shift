"""Ventanas emergentes de configuración."""
from __future__ import annotations

import copy
import tkinter as tk

from . import APP_NAME, APP_SUBTITLE, RELEASE_DATE, VERSION
from . import config as C
from .theme import C as K, F, MINERAL_COLOR, DESMONTE_COLOR
from .widgets import Btn, Check, ScrollFrame, Segmented, ToolWindow, fmt, label

TYPE_COLORS = {"Mineral": MINERAL_COLOR, "Desmonte": DESMONTE_COLOR, "N/A": "#6E7781"}


def _grid_head(parent, titles, widths):
    h = tk.Frame(parent, bg=K["header"])
    h.pack(fill="x")
    for t, w in zip(titles, widths):
        tk.Label(h, text=t, font=F["bold"], bg=K["header"], fg=K["text"], width=w, anchor="w").pack(
            side="left", padx=8, pady=6)
    return h


class PhasesDialog(ToolWindow):
    def __init__(self, parent, plan, cfg, on_apply):
        super().__init__(parent, "Configuración de Fases", 460, 460)
        self.on_apply = on_apply
        self.state = {p: cfg["fases"].get(p, True) for p in plan.detected_phases()}
        tk.Label(self.body, text="Fases detectadas (registros únicos). Marque las que ingresan a la evaluación.",
                 bg=K["panel"], fg=K["muted"], font=F["base"], wraplength=420, justify="left").pack(
            anchor="w", padx=16, pady=(14, 8))
        tot = {}
        for i, p in enumerate(plan.phase):
            if p:
                tot[p] = tot.get(p, 0.0) + plan.V[i, 0]
        box = tk.Frame(self.body, bg=K["border"])
        box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        inner = tk.Frame(box, bg=K["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        _grid_head(inner, ["Fase", "Material Total (t)"], [22, 18])
        sf = ScrollFrame(inner, bg=K["panel"])
        sf.pack(fill="both", expand=True)
        self.checks = {}
        for i, p in enumerate(self.state):
            r = tk.Frame(sf.body, bg=K["alt"] if i % 2 else K["panel"])
            r.pack(fill="x")
            ch = Check(r, p, self.state[p], lambda v, p=p: self.state.__setitem__(p, v), bg=r.cget("bg"))
            ch.pack(side="left", padx=10, pady=4)
            tk.Label(r, text=fmt(tot.get(p, 0)), bg=r.cget("bg"), fg=K["text"], font=F["base"]).pack(side="right", padx=14)
            self.checks[p] = ch
        Btn(self.left, "Seleccionar Todo", lambda: self._all(True)).pack(side="left", padx=(0, 4))
        Btn(self.left, "Ninguno", lambda: self._all(False)).pack(side="left")
        Btn(self.bar, "Cancelar", self.cancel).pack(side="right", padx=(4, 0))
        Btn(self.bar, "Aceptar", self._ok, kind="primary").pack(side="right")
        self.show()

    def _all(self, v):
        for p, ch in self.checks.items():
            ch.set(v)
            self.state[p] = v

    def _ok(self):
        self.on_apply(dict(self.state))
        self.cancel()


class DestinationsDialog(ToolWindow):
    def __init__(self, parent, plan, cfg, on_apply):
        super().__init__(parent, "Configuración de Destinos", 760, 600)
        self.plan, self.cfg, self.on_apply = plan, cfg, on_apply
        self.state = copy.deepcopy(cfg["destinos"])
        self.orig = copy.deepcopy(cfg["destinos"])
        tk.Label(self.body, text="Destinos detectados (columnas de destino con tonelaje > 0, en el orden del Excel). "
                                 "N/A no ingresa al balanceo. Receptor recibe material; Donante entrega material "
                                 "para cumplir el objetivo.",
                 bg=K["panel"], fg=K["muted"], font=F["base"], wraplength=720, justify="left").pack(
            anchor="w", padx=16, pady=(14, 8))
        box = tk.Frame(self.body, bg=K["border"])
        box.pack(fill="both", expand=True, padx=16)
        inner = tk.Frame(box, bg=K["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        _grid_head(inner, ["Destino", "Material (t)", "Tipo de Destino", "Configuración Destino"], [16, 14, 24, 18])
        self.sf = ScrollFrame(inner, bg=K["panel"])
        self.sf.pack(fill="both", expand=True)
        self.summary = tk.Label(self.body, text="", bg=K["panel"], fg=K["text"], font=F["base"], anchor="w")
        self.summary.pack(fill="x", padx=16, pady=8)
        self.sums = plan.dest_sums()
        self.rows = {}
        self._build()
        Btn(self.left, "Sugerir Tipo por Materiales", self._suggest,
            tip="Asigna Mineral o Desmonte según el tipo del material que recibe mayoritariamente cada destino "
                "(requiere la Configuración de Materiales)").pack(side="left", padx=(0, 4))
        Btn(self.left, "Restablecer", self._reset).pack(side="left")
        Btn(self.bar, "Cancelar", self.cancel).pack(side="right", padx=(4, 0))
        Btn(self.bar, "Aceptar", self._ok, kind="primary").pack(side="right")
        self.show()

    def _build(self):
        for w in self.sf.body.winfo_children():
            w.destroy()
        for i, d in enumerate(C.detected_destinations(self.plan)):
            st = self.state.setdefault(d, {"tipo": "N/A", "rol": "Donante"})
            bg = K["alt"] if i % 2 else K["panel"]
            r = tk.Frame(self.sf.body, bg=bg)
            r.pack(fill="x")
            tk.Label(r, text=d, bg=bg, fg=K["text"], font=F["bold"], width=16, anchor="w").pack(side="left", padx=8, pady=5)
            tk.Label(r, text=fmt(self.sums.get(d, 0)), bg=bg, fg=K["muted"], font=F["base"], width=14, anchor="e").pack(
                side="left", padx=8)
            t = Segmented(r, [(x, x) for x in C.TIPOS], st["tipo"], lambda v, d=d: self._tipo(d, v), colors=TYPE_COLORS,
                          padx=10, pady=2)
            t.pack(side="left", padx=(18, 8))
            ro = Segmented(r, [(x, x) for x in C.ROLES], st["rol"], lambda v, d=d: self._rol(d, v), padx=10, pady=2)
            ro.pack(side="left", padx=8)
            ro.set_enabled(st["tipo"] != "N/A")
            self.rows[d] = (t, ro)
        self._summary()

    def _tipo(self, d, v):
        self.state[d]["tipo"] = v
        self.rows[d][1].set_enabled(v != "N/A")
        self._summary()

    def _rol(self, d, v):
        self.state[d]["rol"] = v
        self._summary()

    def _summary(self):
        parts = []
        for c in C.CIRCUITS:
            rec = sum(1 for d in self.rows if self.state[d]["tipo"] == c and self.state[d]["rol"] == "Receptor")
            don = sum(1 for d in self.rows if self.state[d]["tipo"] == c and self.state[d]["rol"] != "Receptor")
            parts.append(f"{c}: {rec} receptor{'es' if rec != 1 else ''} · {don} donante{'s' if don != 1 else ''}")
        na = sum(1 for d in self.rows if self.state[d]["tipo"] == "N/A")
        self.summary.configure(text="     ".join(parts) + f"     N/A: {na}")

    def _suggest(self):
        sug = C.suggest_destination_types(self.plan, self.cfg)
        if not sug:
            from .widgets import dialog
            dialog(self, "Sin Sugerencias", "Primero asigne el tipo de cada material (Configuración de Materiales).",
                   "info")
            return
        for d, t in sug.items():
            if d in self.state:
                self.state[d]["tipo"] = t
        self._build()

    def _reset(self):
        self.state = copy.deepcopy(self.orig)
        self._build()

    def _ok(self):
        self.on_apply(self.state)
        self.cancel()


class MaterialsDialog(ToolWindow):
    def __init__(self, parent, plan, cfg, on_apply):
        super().__init__(parent, "Configuración de Materiales", 560, 520)
        self.on_apply = on_apply
        self.state = dict(cfg["materiales"])
        self.orig = dict(cfg["materiales"])
        tk.Label(self.body, text="Materiales detectados (columnas de material con tonelaje > 0, en el orden del Excel). "
                                 "N/A no ingresa al balanceo.",
                 bg=K["panel"], fg=K["muted"], font=F["base"], wraplength=520, justify="left").pack(
            anchor="w", padx=16, pady=(14, 8))
        box = tk.Frame(self.body, bg=K["border"])
        box.pack(fill="both", expand=True, padx=16)
        inner = tk.Frame(box, bg=K["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        _grid_head(inner, ["Material", "Material (t)", "Tipo de Material"], [12, 14, 26])
        self.sf = ScrollFrame(inner, bg=K["panel"])
        self.sf.pack(fill="both", expand=True)
        self.summary = tk.Label(self.body, text="", bg=K["panel"], fg=K["text"], font=F["base"], anchor="w")
        self.summary.pack(fill="x", padx=16, pady=8)
        self.plan = plan
        self.sums = plan.mat_sums()
        self._build()
        Btn(self.left, "Restablecer", self._reset).pack(side="left")
        Btn(self.bar, "Cancelar", self.cancel).pack(side="right", padx=(4, 0))
        Btn(self.bar, "Aceptar", self._ok, kind="primary").pack(side="right")
        self.show()

    def _build(self):
        for w in self.sf.body.winfo_children():
            w.destroy()
        self.mats = C.detected_materials(self.plan)
        for i, m in enumerate(self.mats):
            self.state.setdefault(m, "N/A")
            bg = K["alt"] if i % 2 else K["panel"]
            r = tk.Frame(self.sf.body, bg=bg)
            r.pack(fill="x")
            tk.Label(r, text=m, bg=bg, fg=K["text"], font=F["bold"], width=12, anchor="w").pack(side="left", padx=8, pady=5)
            tk.Label(r, text=fmt(self.sums.get(m, 0)), bg=bg, fg=K["muted"], width=14, anchor="e").pack(side="left", padx=8)
            Segmented(r, [(x, x) for x in C.TIPOS], self.state[m], lambda v, m=m: self._set(m, v), colors=TYPE_COLORS,
                      padx=10, pady=2).pack(side="left", padx=18)
        self._summary()

    def _set(self, m, v):
        self.state[m] = v
        self._summary()

    def _summary(self):
        a = sum(1 for m in self.mats if self.state[m] == "Mineral")
        b = sum(1 for m in self.mats if self.state[m] == "Desmonte")
        self.summary.configure(text=f"Mineral: {a} materiales     Desmonte: {b} materiales     "
                                    f"N/A: {len(self.mats) - a - b}")

    def _reset(self):
        self.state = dict(self.orig)
        self._build()

    def _ok(self):
        self.on_apply(self.state)
        self.cancel()


class MatrixDialog(ToolWindow):
    """Matriz de Material por Destino: receptores primero, luego donantes; columnas = materiales."""

    def __init__(self, parent, plan, cfg, circuit, on_apply):
        info = C.circuit_info(plan, cfg, circuit)
        w = max(560, 170 + 80 * len(info.materials))
        h = min(720, 230 + 30 * (len(info.dests) + 2))
        super().__init__(parent, f"Materiales · {circuit}", min(w, 1100), h)
        self.on_apply = on_apply
        self.info = info
        self.orig = copy.deepcopy(cfg["circuitos"][circuit]["matriz"])
        self.state = {d: {m: C.allowed(cfg, circuit, d, m) for m in info.materials} for d in info.dests}
        tk.Label(self.body, text="Marca los materiales que cada destino puede recibir y entregar. Sin marcar: ese "
                                 "material no se toca en ese destino (balanceo y devolución). Clic en el encabezado de "
                                 "una columna para marcarla o desmarcarla completa.",
                 bg=K["panel"], fg=K["muted"], font=F["base"], wraplength=w - 40, justify="left").pack(
            anchor="w", padx=16, pady=(14, 8))
        box = tk.Frame(self.body, bg=K["border"])
        box.pack(fill="both", expand=True, padx=16)
        inner = tk.Frame(box, bg=K["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.sf = ScrollFrame(inner, bg=K["panel"])
        self.sf.pack(fill="both", expand=True)
        self.checks = {}
        g = self.sf.body
        tk.Label(g, text="Destino", font=F["bold"], bg=K["header"], fg=K["text"], anchor="w", padx=8, pady=6).grid(
            row=0, column=0, sticky="nsew")
        for j, m in enumerate(info.materials):
            lb = tk.Label(g, text=m, font=F["bold"], bg=K["header"], fg=K["text"], padx=10, pady=6, cursor="hand2")
            lb.grid(row=0, column=j + 1, sticky="nsew", padx=(1, 0))
            lb.bind("<ButtonRelease-1>", lambda e, m=m: self._col(m))
        r = 1
        for title, group in (("RECEPTORES", info.receptors), ("DONANTES", info.donors)):
            tk.Label(g, text=title, font=F["bold"], bg=K["alt"], fg=K["muted"], anchor="w", padx=8, pady=5).grid(
                row=r, column=0, columnspan=len(info.materials) + 1, sticky="nsew")
            r += 1
            for d in group:
                tk.Label(g, text=d, bg=K["panel"], fg=K["text"], anchor="w", padx=8, pady=4).grid(row=r, column=0,
                                                                                                    sticky="nsew")
                for j, m in enumerate(info.materials):
                    ch = Check(g, "", self.state[d][m], lambda v, d=d, m=m: self._set(d, m, v), bg=K["panel"])
                    ch.grid(row=r, column=j + 1, pady=3)
                    self.checks[(d, m)] = ch
                r += 1
        g.grid_columnconfigure(0, minsize=150)
        Btn(self.bar, "Marcar Todo", lambda: self._all(True)).pack(side="left", padx=4)
        Btn(self.bar, "Marcar Ninguna", lambda: self._all(False)).pack(side="left", padx=4)
        Btn(self.bar, "Restablecer", self._reset).pack(side="left", padx=4)
        Btn(self.bar, "Cerrar", self._ok, kind="primary").pack(side="left", padx=4)
        self.show()

    def _set(self, d, m, v):
        self.state[d][m] = v

    def _col(self, m):
        v = not all(self.state[d][m] for d in self.state)
        for d in self.state:
            self.state[d][m] = v
            self.checks[(d, m)].set(v)

    def _all(self, v):
        for (d, m), ch in self.checks.items():
            self.state[d][m] = v
            ch.set(v)

    def _reset(self):
        for (d, m), ch in self.checks.items():
            v = self.orig.get(d, {}).get(m, True)
            self.state[d][m] = v
            ch.set(v)

    def _ok(self):
        out = {d: {m: v for m, v in ms.items() if not v} for d, ms in self.state.items()}
        self.on_apply({d: ms for d, ms in out.items() if ms})
        self.cancel()

    def cancel(self):
        super().cancel()


class AboutDialog(ToolWindow):
    def __init__(self, parent, logo=None):
        super().__init__(parent, f"Acerca de {APP_NAME}", 420, 250)
        row = tk.Frame(self.body, bg=K["panel"])
        row.pack(fill="both", expand=True, padx=20, pady=20)
        if logo is not None:
            tk.Label(row, image=logo, bg=K["panel"]).pack(side="left", padx=(0, 16), anchor="n")
        t = tk.Frame(row, bg=K["panel"])
        t.pack(side="left", fill="both", expand=True)
        label(t, APP_NAME, F["h1"]).pack(anchor="w")
        label(t, APP_SUBTITLE, F["base"], K["muted"]).pack(anchor="w")
        label(t, f"Versión {VERSION}", F["base"]).pack(anchor="w", pady=(12, 0))
        label(t, f"Fecha de lanzamiento: {RELEASE_DATE}", F["base"], K["muted"]).pack(anchor="w")
        label(t, "Balanceo de materiales por destino · LP HiGHS", F["small"], K["muted"]).pack(anchor="w", pady=(12, 0))
        Btn(self.bar, "Aceptar", self.cancel, kind="primary").pack(side="right")
        self.bind("<Return>", lambda e: self.cancel())
        self.show()
