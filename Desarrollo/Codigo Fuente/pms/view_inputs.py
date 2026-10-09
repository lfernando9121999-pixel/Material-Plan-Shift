"""Pestaña Inputs."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from . import config as C
from .dialogs import DestinationsDialog, MaterialsDialog, PhasesDialog
from .plan import ROLE_LABELS
from .theme import C as K, F, MINERAL_COLOR, DESMONTE_COLOR
from .widgets import Btn, Card, ScrollFrame, label

DESC_MAX = 500


def _colname(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class InputsPage(tk.Frame):
    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["bg"])
        self.ws = ws
        sf = ScrollFrame(self, bg=K["bg"])
        sf.pack(fill="both", expand=True)
        body = sf.body
        self._loading = False

        # ---- General ------------------------------------------------------------
        card = Card(body, "General")
        card.pack(fill="x", padx=14, pady=(12, 8))
        g = card.body
        g.grid_columnconfigure(1, weight=1)

        def req(row, text, required=True):
            f = tk.Frame(g, bg=K["panel"])
            f.grid(row=row, column=0, sticky="nw", pady=6, padx=(0, 16))
            label(f, text, F["base"]).pack(side="left")
            if required:
                label(f, " *", F["bold"], K["required"]).pack(side="left")

        req(0, "Input para Análisis")
        r0 = tk.Frame(g, bg=K["panel"])
        r0.grid(row=0, column=1, sticky="w", pady=6)
        self.btn_file = Btn(r0, "Seleccionar Archivo…", ws.choose_file, kind="accent",
                            tip="Importar el Excel (.xlsx / .xlsm) desde el Escritorio u otra carpeta")
        self.btn_file.pack(side="left")
        self.file_lbl = label(r0, "Sin archivo seleccionado", F["base"], K["muted"])
        self.file_lbl.pack(side="left", padx=10)

        req(1, "Hoja para Análisis")
        self.sheet = ttk.Combobox(g, state="readonly", width=36)
        self.sheet.grid(row=1, column=1, sticky="w", pady=6)
        self.sheet.bind("<<ComboboxSelected>>", lambda e: ws.choose_sheet(self.sheet.get()))

        req(2, "Nombre del Escenario")
        self.name = ttk.Entry(g, width=60)
        self.name.grid(row=2, column=1, sticky="ew", pady=6)
        self.name.bind("<KeyRelease>", self._name_changed)

        req(3, "Año")
        r3 = tk.Frame(g, bg=K["panel"])
        r3.grid(row=3, column=1, sticky="w", pady=6)
        self.year = ttk.Spinbox(r3, from_=1900, to=2200, width=8, command=self._year_changed)
        self.year.pack(side="left")
        self.year.bind("<KeyRelease>", lambda e: self._year_changed())
        self.year_hint = label(r3, "", F["small"], K["muted"])
        self.year_hint.pack(side="left", padx=10)

        req(4, "Descripción", required=False)
        r4 = tk.Frame(g, bg=K["panel"])
        r4.grid(row=4, column=1, sticky="ew", pady=6)
        self.desc = tk.Text(r4, height=3, wrap="word", bg=K["input"], fg=K["text"], insertbackground=K["text"],
                            relief="flat", highlightthickness=1, highlightbackground=K["border"],
                            highlightcolor=K["accent"], font=F["base"], padx=6, pady=4)
        self.desc.pack(fill="x")
        self.desc.bind("<KeyRelease>", self._desc_changed)
        self.desc_count = label(r4, f"0 / {DESC_MAX} Caracteres (sin Espacios)", F["small"], K["muted"])
        self.desc_count.pack(anchor="e", pady=(2, 0))

        # ---- Detección de Datos -------------------------------------------------
        det = Card(body, "Detección de Datos")
        det.pack(fill="x", padx=14, pady=8)
        self.det_info = label(det.body, "Seleccione un archivo y una hoja para detectar la tabla principal (celda «# Sec»).",
                              F["base"], K["muted"], justify="left", anchor="w")
        self.det_info.pack(fill="x")
        self.det_table = tk.Frame(det.body, bg=K["panel"])
        self.det_table.pack(fill="x", pady=(8, 4))

        bar = tk.Frame(det.body, bg=K["panel"])
        bar.pack(fill="x", pady=(8, 4))
        self.btn_ph = Btn(bar, "A. Configuración de Fases", self._phases)
        self.btn_ph.pack(side="left", padx=(0, 8))
        self.btn_de = Btn(bar, "B. Configuración de Destinos", self._dests)
        self.btn_de.pack(side="left", padx=(0, 8))
        self.btn_ma = Btn(bar, "C. Configuración de Materiales", self._mats)
        self.btn_ma.pack(side="left", padx=(0, 8))
        self.cfg_hint = label(bar, "", F["small"], K["muted"])
        self.cfg_hint.pack(side="left", padx=8)

        blocks = tk.Frame(det.body, bg=K["panel"])
        blocks.pack(fill="x", pady=(10, 0))
        blocks.grid_columnconfigure(0, weight=1, uniform="b")
        blocks.grid_columnconfigure(1, weight=1, uniform="b")
        self.blocks = {}
        for i, (circ, col) in enumerate((("Mineral", MINERAL_COLOR), ("Desmonte", DESMONTE_COLOR))):
            outer = tk.Frame(blocks, bg=K["border"])
            outer.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 6 if i == 0 else 0))
            inner = tk.Frame(outer, bg=K["panel"])
            inner.pack(fill="both", expand=True, padx=1, pady=1)
            top = tk.Frame(inner, bg=col, height=3)
            top.pack(fill="x")
            head = label(inner, circ.upper(), F["section"])
            head.pack(anchor="w", padx=12, pady=(8, 2))
            txt = label(inner, "", F["base"], justify="left", anchor="w")
            txt.pack(fill="x", padx=12, pady=(0, 10))
            self.blocks[circ] = (outer, inner, top, head, txt, col)
        self.refresh()

    # ---- eventos ------------------------------------------------------------
    def _name_changed(self, _e=None):
        if self._loading:
            return
        v = self.name.get()
        if v != self.ws.cfg["general"]["nombre"]:
            self.ws.cfg["general"]["nombre"] = v
            self.ws.changed(results=False, refresh=False)

    def _year_changed(self):
        if self._loading:
            return
        try:
            y = int(self.year.get())
        except ValueError:
            return
        if y != self.ws.cfg["general"].get("anio"):
            self.ws.cfg["general"]["anio"] = y
            self.ws.changed()

    def _desc_changed(self, _e=None):
        txt = self.desc.get("1.0", "end-1c")
        n = len("".join(txt.split()))
        if n > DESC_MAX:
            # recorta hasta cumplir el máximo (sin contar espacios)
            while len("".join(txt.split())) > DESC_MAX:
                txt = txt[:-1]
            self.desc.delete("1.0", "end")
            self.desc.insert("1.0", txt)
            n = DESC_MAX
        self.desc_count.configure(text=f"{n} / {DESC_MAX} Caracteres (sin Espacios)",
                                  fg=K["required"] if n >= DESC_MAX else K["muted"])
        if not self._loading and txt != self.ws.cfg["general"]["descripcion"]:
            self.ws.cfg["general"]["descripcion"] = txt
            self.ws.changed(results=False, refresh=False)

    def _phases(self):
        if self.ws.plan is None:
            return
        PhasesDialog(self, self.ws.plan, self.ws.cfg, self._apply_phases)

    def _apply_phases(self, st):
        self.ws.cfg["fases"].update(st)
        self.ws.changed()

    def _dests(self):
        if self.ws.plan is None:
            return
        DestinationsDialog(self, self.ws.plan, self.ws.cfg, self._apply_dests)

    def _apply_dests(self, st):
        self.ws.cfg["destinos"] = st
        C.refresh_circuits(self.ws.plan, self.ws.cfg)
        self.ws.changed()

    def _mats(self):
        if self.ws.plan is None:
            return
        MaterialsDialog(self, self.ws.plan, self.ws.cfg, self._apply_mats)

    def _apply_mats(self, st):
        self.ws.cfg["materiales"] = st
        C.refresh_circuits(self.ws.plan, self.ws.cfg)
        self.ws.changed()

    # ---- refresco -----------------------------------------------------------
    def refresh(self):
        ws, cfg = self.ws, self.ws.cfg
        self._loading = True
        plan = ws.plan
        path = cfg["general"].get("archivo")
        if plan is not None:
            size = plan.file_size / 1024 / 1024
            self.file_lbl.configure(text=f"{os.path.basename(plan.path)}   ·   {size:,.1f} MB   ·   {plan.n:,} filas",
                                    fg=K["text"])
        elif path:
            miss = "" if os.path.exists(path) else "   (no encontrado)"
            self.file_lbl.configure(text=os.path.basename(path) + miss, fg=K["muted"])
        else:
            self.file_lbl.configure(text="Sin archivo seleccionado", fg=K["muted"])
        self.sheet.configure(values=ws.sheets)
        self.sheet.set(cfg["general"].get("hoja") or "")
        if self.name.get() != cfg["general"]["nombre"]:
            self.name.delete(0, "end")
            self.name.insert(0, cfg["general"]["nombre"])
        y = cfg["general"].get("anio")
        self.year.delete(0, "end")
        if y:
            self.year.insert(0, str(y))
        if plan is not None:
            det = plan.detect_year()
            self.year_hint.configure(text=f"Detectado en «{plan.headers[plan.roles['fecha']]}»: {det}"
                                     if "fecha" in plan.roles and det else "")
        cur = self.desc.get("1.0", "end-1c")
        if cur != cfg["general"]["descripcion"]:
            self.desc.delete("1.0", "end")
            self.desc.insert("1.0", cfg["general"]["descripcion"])
        self._loading = False
        self._desc_changed()
        self._refresh_detection()

    def _refresh_detection(self):
        plan, cfg = self.ws.plan, self.ws.cfg
        for w in self.det_table.winfo_children():
            w.destroy()
        on = plan is not None
        for b in (self.btn_ph, self.btn_de, self.btn_ma):
            b.set_enabled(on)
        if not on:
            self.det_info.configure(text="Seleccione un archivo y una hoja para detectar la tabla principal (celda «# Sec»).")
            self.cfg_hint.configure(text="")
            for circ, (outer, inner, top, head, txt, col) in self.blocks.items():
                self._paint_block(circ, False, "Sin datos")
            return
        cell = f"{_colname(plan.first_col)}{plan.header_row}"
        last = _colname(plan.first_col + len(plan.headers) - 1)
        self.det_info.configure(
            text=f"Tabla detectada desde la celda «# Sec» ({cell}) hasta la columna {last}: "
                 f"{len(plan.headers)} columnas y {plan.n:,} filas con datos."
                 + (f"   ({plan.detection_note})" if plan.detection_note else ""))
        rows = []
        for role, title in ROLE_LABELS.items():
            if role in plan.roles:
                i = plan.roles[role]
                rows.append((title, f"{_colname(plan.first_col + i)} ({i + 1})", plan.headers[i]))
        d0, d1 = plan.dest_idx[0], plan.dest_idx[-1]
        m0, m1 = plan.mat_idx[0], plan.mat_idx[-1]
        nd = len(C.detected_destinations(plan))
        nm = len(C.detected_materials(plan))
        rows.append(("Destinos", f"{_colname(plan.first_col + d0)}–{_colname(plan.first_col + d1)} ({d0 + 1}–{d1 + 1})",
                     f"{len(plan.dest_idx)} columnas · {nd} con tonelaje > 0"))
        rows.append(("Materiales", f"{_colname(plan.first_col + m0)}–{_colname(plan.first_col + m1)} ({m0 + 1}–{m1 + 1})",
                     f"{len(plan.mat_idx)} columnas · {nm} con tonelaje > 0"))
        rows.append(("Propiedades", "otras columnas", f"{len(plan.prop_idx)} columnas"))
        t = self.det_table
        for j, h in enumerate(("Campo", "Columna (N°)", "Encabezado / Detalle")):
            tk.Label(t, text=h, font=F["bold"], bg=K["header"], fg=K["text"], anchor="w", padx=8, pady=4).grid(
                row=0, column=j, sticky="nsew")
        for i, r in enumerate(rows, 1):
            bg = K["alt"] if i % 2 == 0 else K["panel"]
            for j, v in enumerate(r):
                tk.Label(t, text=v, font=F["base"], bg=bg, fg=K["text"], anchor="w", padx=8, pady=3).grid(
                    row=i, column=j, sticky="nsew")
        t.grid_columnconfigure(2, weight=1)
        nph = sum(1 for p in plan.detected_phases() if cfg["fases"].get(p, True))
        self.cfg_hint.configure(text=f"Fases: {nph}/{len(plan.detected_phases())} habilitadas  ·  "
                                     f"Destinos: {nd}  ·  Materiales: {nm}")
        for circ in C.CIRCUITS:
            info = C.circuit_info(plan, cfg, circ)
            if not info.dests and not info.materials:
                self._paint_block(circ, False, "Sin destinos ni materiales asignados (inactivo).")
                continue
            lines = [f"Receptores: {len(info.receptors)}" + (f"  ({', '.join(info.receptors)})" if info.receptors else ""),
                     f"Donantes: {len(info.donors)}" + (f"  ({', '.join(info.donors)})" if info.donors else ""),
                     f"Destinos asignados: {len(info.dests)}",
                     f"Tipos de material asignados: {len(info.materials)}"
                     + (f"  ({', '.join(info.materials)})" if info.materials else "")]
            self._paint_block(circ, True, "\n".join(lines))

    def _paint_block(self, circ, active, text):
        outer, inner, top, head, txt, col = self.blocks[circ]
        bg = K["panel"] if active else K["inactive_bg"]
        inner.configure(bg=bg)
        top.configure(bg=col if active else K["border"])
        head.configure(bg=bg, fg=K["text"] if active else K["disabled"])
        txt.configure(bg=bg, fg=K["text"] if active else K["disabled"], text=text)
