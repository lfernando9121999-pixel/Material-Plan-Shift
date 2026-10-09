"""Ventana principal de Plan Material Shift."""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import filedialog

from . import APP_NAME, APP_SUBTITLE, PROJECT_EXT, VERSION
from . import config as C
from . import theme
from .theme import C as K, F, px
from .prefs import Prefs, desktop
from .widgets import (IconButton, ProgressWindow, Tooltip, close_popup, dialog, draw_icon, install_wheel, label)


def resource(*parts):
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "pms", "assets", *parts)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", *parts)


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===========================================================================
class Workspace(tk.Frame):
    """Un escenario abierto: su configuración, su plan, sus resultados y sus vistas."""

    TABS = (("inputs", "Inputs"), ("restr", "Restricciones"), ("obj", "Función Objetivo"), ("res", "Resultados"))

    def __init__(self, parent, app, number):
        super().__init__(parent, bg=K["bg"])
        self.app = app
        self.number = number
        self.cfg = C.new_config()
        self.plan = None
        self.sheets = []
        self.result = None
        self.calc_digest = None
        self.path = None
        self.dirty = False
        self.pages = {}
        self.cur = None
        self.stale = set()
        self._build()

    # ---- estado ---------------------------------------------------------------
    @property
    def title(self):
        n = self.cfg["general"]["nombre"].strip()
        if n:
            return n
        if self.path:
            return os.path.splitext(os.path.basename(self.path))[0]
        return "Escenario Sin Título" + (f" {self.number}" if self.number > 1 else "")

    def struct_key(self):
        """Huella de lo que define la estructura de las páginas (para no reconstruirlas sin necesidad)."""
        import json
        c = self.cfg
        return json.dumps([id(self.plan), c["fases"], c["destinos"], c["materiales"], c["general"].get("anio"),
                           {k: v["activo"] for k, v in c["circuitos"].items()}], sort_keys=True)

    def results_state(self):
        if self.result is None:
            return "Sin Ejecutar"
        if C.config_digest(self.cfg) != self.calc_digest:
            return "Desactualizados"
        return "Ejecutado"

    def changed(self, results=True, refresh=True):
        """refresh=True: cambió la estructura (archivo, fases, destinos, materiales o activación):
        las páginas afectadas se actualizan. refresh=False: un valor editado en la propia página."""
        self.dirty = True
        if refresh:
            for k in self.pages:
                if k != self.cur:
                    self.stale.add(k)
            if self.cur in ("inputs", "restr", "obj") and self.cur in self.pages:
                self.pages[self.cur].refresh()
        self.stale.add("res")
        self.app.update_chrome()

    # ---- interfaz -------------------------------------------------------------
    def _build(self):
        self.left = FilesPanel(self, self)
        self.left.pack(side="left", fill="y", padx=(8, 0), pady=8)
        right = tk.Frame(self, bg=K["border"])
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        inner = tk.Frame(right, bg=K["bg"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        strip = tk.Frame(inner, bg=K["panel"])
        strip.pack(fill="x")
        self.tablabels = {}
        for key, text in self.TABS:
            f = tk.Frame(strip, bg=K["panel"])
            f.pack(side="left")
            lb = tk.Label(f, text=text, font=F["tab"], bg=K["panel"], fg=K["text"], padx=14, pady=8, cursor="hand2")
            lb.pack()
            line = tk.Frame(f, bg=K["panel"], height=2)
            line.pack(fill="x", padx=8)
            lb.bind("<ButtonRelease-1>", lambda e, k=key: self.show(k))
            self.tablabels[key] = (lb, line)
            if key != self.TABS[-1][0]:
                tk.Frame(strip, bg=K["border"], width=1, height=16).pack(side="left", pady=10)
        self.year_lbl = tk.Label(strip, text="", font=F["base"], bg=K["accent"], fg="#FFFFFF", padx=12, pady=3,
                                 cursor="hand2")
        self.year_lbl.pack(side="right", padx=10)
        self.year_lbl.bind("<ButtonRelease-1>", lambda e: self.show("inputs"))
        Tooltip(self.year_lbl, "Año de análisis (Inputs ▸ Año)")
        self.req_lbl = tk.Label(strip, text="* Requerido", font=F["base"], bg=K["panel"], fg=K["required"])
        tk.Frame(inner, bg=K["border"], height=1).pack(fill="x")
        self.host = tk.Frame(inner, bg=K["bg"])
        self.host.pack(fill="both", expand=True)
        self.show("inputs")

    def show(self, key):
        close_popup()
        from .view_config import ObjectivePage, RestrictionsPage
        from .view_inputs import InputsPage
        from .view_results import ResultsPage
        if self.cur and self.cur in self.pages:
            self.pages[self.cur].pack_forget()
        self.cur = key
        if key not in self.pages:
            cls = {"inputs": InputsPage, "obj": ObjectivePage, "restr": RestrictionsPage, "res": ResultsPage}[key]
            self.pages[key] = cls(self.host, self)
            self.stale.discard(key)
        elif key in self.stale:
            self.stale.discard(key)
            self.pages[key].refresh()
        self.pages[key].pack(fill="both", expand=True)
        for k, (lb, line) in self.tablabels.items():
            on = k == key
            lb.configure(font=F["tab_on"] if on else F["tab"])
            line.configure(bg=K["tab_line"] if on else K["panel"])
        if key == "inputs":
            self.req_lbl.pack(side="right", padx=8)
        else:
            self.req_lbl.pack_forget()
        self.update_year()

    def prebuild(self):
        """Prepara en segundo plano (cuando no hay interacción) las pestañas y subpestañas aún no
        construidas, una por vez, para que su primera apertura sea instantánea."""
        from .view_config import ObjectivePage, RestrictionsPage
        from .view_inputs import InputsPage
        from .view_results import ResultsPage
        if getattr(self, "_prebuild_job", None):
            self.after_cancel(self._prebuild_job)
        tasks = []
        for key, cls in (("inputs", InputsPage), ("restr", RestrictionsPage), ("obj", ObjectivePage),
                         ("res", ResultsPage)):
            if key not in self.pages:
                tasks.append(("page", key, cls))
        if self.result is not None:
            for key, _ in ResultsPage.TABS:
                tasks.append(("viewc", key, None))      # crear la vista
                tasks.append(("view", key, None))       # llenarla (en otro paso)

        self.prebuild_log = []

        def step():
            self._prebuild_job = None
            if self.app.busy or not self.winfo_exists():
                return
            t0 = time.perf_counter()
            done = None
            while tasks:
                kind, key, cls = tasks.pop(0)
                if kind == "page":
                    if key in self.pages:
                        continue
                    self.pages[key] = cls(self.host, self)
                    self.stale.discard(key)
                    done = (kind, key)
                    break
                else:
                    page = self.pages.get("res")
                    if page is None or self.result is None:
                        continue
                    v = page.views.get(key)
                    if kind == "viewc":
                        if v is not None:
                            continue
                        page.prepare(key, create_only=True)
                        done = (kind, key)
                        break
                    if v is not None and getattr(v, "_key", None) == (id(self.result), page.circ.get()):
                        continue
                    page.prepare(key)
                done = (kind, key)
                break
            self.update_idletasks()
            self.prebuild_log.append((done, (time.perf_counter() - t0) * 1000))
            if tasks:
                self._prebuild_job = self.after(120, step)
        self._prebuild_job = self.after(300, step)

    def refresh_all(self):
        for k in list(self.pages):
            if k == self.cur:
                self.pages[k].refresh()
            else:
                self.stale.add(k)
        self.left.refresh()
        self.update_year()

    def update_year(self):
        y = self.cfg["general"].get("anio")
        self.year_lbl.configure(text=f"Año {y}" if y else "Año —")

    # ---- archivo de entrada -------------------------------------------------
    def choose_file(self):
        p = filedialog.askopenfilename(parent=self.app.root, title="Input para Análisis", initialdir=desktop(),
                                       filetypes=[("Libro de Excel", "*.xlsx *.xlsm"), ("Todos los archivos", "*.*")])
        if not p:
            return
        if not p.lower().endswith((".xlsx", ".xlsm")):
            dialog(self, "Formato no Admitido", "El input para análisis debe ser un libro de Excel (.xlsx o .xlsm).",
                   "error")
            return
        self.app.prefs.set("last_xlsx_dir", os.path.dirname(p))
        from .plan import list_sheets
        try:
            sheets = list_sheets(p)
        except Exception as ex:
            dialog(self, "No se Pudo Abrir el Archivo", str(ex), "error")
            return
        self.cfg["general"]["archivo"] = p
        self.sheets = sheets
        if not self.cfg["general"]["nombre"].strip():
            self.cfg["general"]["nombre"] = ""
        sheet = self.cfg["general"].get("hoja")
        if sheet not in sheets:
            sheet = self._guess_sheet(p, sheets)
        self.load_sheet(sheet)

    def _guess_sheet(self, path, sheets):
        """Primera hoja que contiene «# Sec» (lectura rápida de las primeras filas)."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                for s in sheets:
                    for row in wb[s].iter_rows(min_row=1, max_row=30, values_only=True):
                        if any(isinstance(v, str) and v.replace(" ", "").lower() == "#sec" for v in row):
                            return s
            finally:
                wb.close()
        except Exception:
            pass
        return sheets[0] if sheets else ""

    def choose_sheet(self, sheet):
        if sheet and sheet != self.cfg["general"].get("hoja"):
            self.load_sheet(sheet)

    def load_sheet(self, sheet, after=None, keep_config=False):
        path = self.cfg["general"]["archivo"]
        from .plan import load_plan

        def work(progress, cancelled):
            return load_plan(path, sheet, progress)

        def done(plan):
            new_file = self.plan is None or self.plan.path != plan.path or self.plan.sheet != plan.sheet
            self.plan = plan
            self.cfg["general"]["hoja"] = sheet
            if new_file and not keep_config:
                old = self.cfg
                self.cfg = C.new_config()
                self.cfg["general"].update({k: old["general"][k] for k in ("archivo", "nombre", "descripcion")})
                self.cfg["general"]["hoja"] = sheet
                self.cfg["experimento"] = old["experimento"]
            C.ensure_plan_defaults(plan, self.cfg, self.app.prefs.get("memory"))
            if not keep_config:
                self.result = None
                self.dirty = True
            self.refresh_all()
            self.app.update_chrome()
            self.app.notify(f"Tabla detectada: {plan.n:,} filas · {len(plan.headers)} columnas")
            self.prebuild()
            if after:
                after()
        self.app.background("Leyendo Input para Análisis", work, done, cancelable=False)

    # ---- ejecución ------------------------------------------------------------
    def run(self):
        close_popup()
        errs = C.validate_config(self.plan, self.cfg)
        if errs:
            dialog(self, "Faltan Datos para Ejecutar", "Revise lo siguiente:", "warn",
                   detail="\n".join("• " + e for e in errs))
            if self.plan is None or not self.cfg["general"]["nombre"].strip():
                self.show("inputs")
            return
        ex = self.cfg["experimento"]
        pd = ex.get("prio_destinos") or {}
        if ex["tipo"] in ("reordenamiento", "integral") and not pd.get("revisado"):
            # primera vez: ofrece activar la priorización de destinos en la permutación
            from .dialogs import DestPriorityDialog

            def apply(state):
                self.cfg["experimento"]["prio_destinos"] = state
            DestPriorityDialog(self.app.root, self.plan, self.cfg, apply, first_time=True)
            self.cfg["experimento"].setdefault("prio_destinos", {})["revisado"] = True
            if "obj" in self.pages:
                self.pages["obj"].pages["exp"].refresh()
        if (self.cfg["experimento"].get("prio_destinos") or {}).get("activo"):
            C.sync_dest_priority(self.plan, self.cfg)
        from . import engine
        cfg = __import__("copy").deepcopy(self.cfg)
        plan = self.plan

        def work(progress, cancelled):
            return engine.run(plan, cfg, progress, cancelled)

        def done(res):
            self.result = res
            self.calc_digest = C.config_digest(cfg)
            self.dirty = True
            self.app.prefs.remember_config(cfg)
            self.stale.add("res")
            self.show("res")
            if "res" in self.pages:
                self.pages["res"].update_view(force=True)
            self.app.update_chrome()
            self.app.notify(f"Experimento ejecutado correctamente ({res.elapsed:,.1f} s)")
            self.prebuild()
        self.app.background("Ejecutando experimento", work, done, cancelable=True)


# ===========================================================================
class FilesPanel(tk.Frame):
    W = 270

    def __init__(self, parent, ws):
        super().__init__(parent, bg=K["border"], width=px(self.W))
        self.ws = ws
        self.pinned = ws.app.prefs.get("panel_pinned", True)
        self.inner = tk.Frame(self, bg=K["panel"])
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.strip = tk.Frame(self, bg=K["panel"], width=26)
        self._build()
        self._apply_pin()

    def _build(self):
        head = tk.Frame(self.inner, bg=K["panel"])
        head.pack(fill="x", padx=12, pady=(10, 4))
        label(head, "Archivos del Modelo", F["bold"]).pack(side="left")
        self.pin = IconButton(head, "pin", self._toggle_pin, "Fijar / Ocultar Automáticamente", size=22,
                              color=K["accent"] if self.pinned else K["muted"])
        self.pin.pack(side="right")
        acts = tk.Frame(self.inner, bg=K["panel"])
        acts.pack(fill="x", padx=8)
        IconButton(acts, "import", self.ws.choose_file, "Importar Input para Análisis (Ctrl+I)").pack(side="left")
        self.b_folder = IconButton(acts, "folder", self._folder, "Mostrar Carpeta del Archivo")
        self.b_folder.pack(side="left")
        self.b_open = IconButton(acts, "file", self._open, "Abrir Archivo")
        self.b_open.pack(side="left")
        tk.Frame(self.inner, bg=K["border"], height=1).pack(fill="x", pady=(6, 0))
        self.list = tk.Frame(self.inner, bg=K["panel"])
        self.list.pack(fill="both", expand=True)
        tk.Frame(self.inner, bg=K["border"], height=1).pack(fill="x", side="bottom")
        self.foot = label(self.inner, "", F["small"], K["muted"], anchor="w")
        self.foot.pack(fill="x", side="bottom", padx=12, pady=8)
        self.refresh()

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        path = self.ws.cfg["general"].get("archivo")
        plan = self.ws.plan
        has = bool(path)
        self.b_folder.set_enabled(has and os.path.exists(path))
        self.b_open.set_enabled(has and os.path.exists(path))
        if not has:
            label(self.list, "Aún no hay archivos. Use el botón «Importar» o «Seleccionar Archivo…» en Inputs para "
                             "agregar el Excel de análisis.", F["small"], K["muted"], justify="left", wraplength=230,
                  anchor="w").pack(fill="x", padx=12, pady=12)
            self.foot.configure(text="0 Archivos")
            return
        exists = os.path.exists(path)
        row = tk.Frame(self.list, bg=K["select"] if exists else K["panel"])
        row.pack(fill="x", padx=6, pady=6)
        cv = tk.Canvas(row, width=26, height=30, bg=row.cget("bg"), highlightthickness=0)
        cv.pack(side="left", padx=6, pady=6)
        draw_icon(cv, "excel", 22, "#1F883D" if exists else K["warn"], 2, 4)
        t = tk.Frame(row, bg=row.cget("bg"))
        t.pack(side="left", fill="x", expand=True)
        label(t, os.path.basename(path), F["bold"], bg=row.cget("bg"), anchor="w", wraplength=180,
              justify="left").pack(fill="x")
        if plan is not None and exists:
            det = f"{plan.file_size / 1024 / 1024:,.1f} MB · {plan.n:,} filas · {plan.sheet}"
        elif exists:
            det = f"{os.path.getsize(path) / 1024 / 1024:,.1f} MB"
        else:
            det = "No encontrado" + (" · resultados guardados disponibles" if self.ws.result else "")
        label(t, det, F["small"], K["muted"] if exists else K["warn"], bg=row.cget("bg"), anchor="w").pack(fill="x")
        label(row, "✓" if exists else "⚠", F["bold"], K["ok_fg"] if exists else K["warn"], bg=row.cget("bg")).pack(
            side="right", padx=8)
        size = os.path.getsize(path) / 1024 / 1024 if exists else 0
        self.foot.configure(text=f"1 Archivo · {'1 Incluido' if exists else 'No encontrado'} · {size:,.1f} MB")

    def _folder(self):
        p = self.ws.cfg["general"].get("archivo")
        if p and os.path.exists(p):
            _open_path(os.path.dirname(p))

    def _open(self):
        p = self.ws.cfg["general"].get("archivo")
        if p and os.path.exists(p):
            _open_path(p)

    def _toggle_pin(self):
        self.pinned = not self.pinned
        self.ws.app.prefs.set("panel_pinned", self.pinned)
        self.pin.color = K["accent"] if self.pinned else K["muted"]
        self.pin._draw()
        self._apply_pin()

    def _apply_pin(self):
        if self.pinned:
            self.strip.pack_forget()
            self.inner.pack(fill="both", expand=True, padx=1, pady=1)
            self.configure(width=px(self.W))
            self.pack_propagate(False)
        else:
            self.inner.pack_forget()
            self.configure(width=px(28))
            self.pack_propagate(False)
            self.strip.pack(fill="both", expand=True, padx=1, pady=1)
            for w in self.strip.winfo_children():
                w.destroy()
            cv = tk.Canvas(self.strip, width=24, bg=K["panel"], highlightthickness=0, cursor="hand2")
            cv.pack(fill="y", expand=True)
            cv.create_text(13, 90, text="Archivos del Modelo", angle=90, fill=K["muted"], font=F["base"])
            cv.bind("<Enter>", lambda e: self._peek(True))
            cv.bind("<ButtonRelease-1>", lambda e: self._toggle_pin())

    def _peek(self, on):
        if self.pinned:
            return
        self._toggle_pin()


def _open_path(p):
    try:
        if sys.platform == "win32":
            os.startfile(p)  # noqa: S606
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", p])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", p])
    except Exception:
        pass


# ===========================================================================
class App:
    def __init__(self, root, files=()):
        self.root = root
        self.prefs = Prefs()
        root.notify = self.notify
        self.dark = bool(self.prefs.get("dark", False))
        theme.apply(root, self.dark)
        install_wheel(root)
        self.workspaces = []
        self.active = None
        self.counter = 0
        self.q = queue.Queue()
        self.busy = False
        self._status_job = None
        self._tabs_key = None
        self._tab_labels = {}
        self._load_icons()
        self._build()
        self._bind_keys()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w0, h0 = min(px(1440), int(sw * 0.94)), min(px(900), int(sh * 0.88))
        default = f"{w0}x{h0}+{max(0, (sw - w0) // 2)}+{max(0, (sh - h0) // 3)}"
        geo = self.prefs.get("geometry")
        try:
            root.geometry(geo or default)
        except tk.TclError:
            root.geometry(default)
        if self.prefs.get("zoomed") and sys.platform == "win32":
            root.state("zoomed")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        opened = False
        for f in files:
            if f.lower().endswith(PROJECT_EXT) and os.path.exists(f):
                self.open_project(f)
                opened = True
        if not opened:
            self.new_scenario()
        root.after(60, self._poll)

    # ---- recursos ---------------------------------------------------------
    def _load_icons(self):
        self.logo_small = self.logo_big = None
        try:
            self.logo_small = tk.PhotoImage(file=resource("logo_24.png"))
            self.logo_big = tk.PhotoImage(file=resource("logo_64.png"))
            self.root.iconphoto(True, tk.PhotoImage(file=resource("logo_64.png")))
            if sys.platform == "win32" and os.path.exists(resource("icono.ico")):
                self.root.iconbitmap(default=resource("icono.ico"))
        except Exception:
            pass

    # ---- construcción -----------------------------------------------------
    def _build(self):
        root = self.root
        for w in root.winfo_children():
            w.destroy()
        top = tk.Frame(root, bg=K["panel"])
        top.pack(fill="x")
        menus = tk.Frame(top, bg=K["panel"])
        menus.pack(side="left", padx=(8, 0))
        self.menu_btns = {}
        for name, builder in (("Archivo", self._menu_file), ("Modelo", self._menu_model),
                              (f"Acerca de {APP_NAME}", self._menu_about)):
            lb = tk.Label(menus, text=name, bg=K["panel"], fg=K["text"], font=F["menu"], padx=10, pady=8, cursor="hand2")
            lb.pack(side="left")
            lb.bind("<Enter>", lambda e, l=lb: l.configure(bg=K["hover"]))
            lb.bind("<Leave>", lambda e, l=lb: l.configure(bg=K["panel"]))
            lb.bind("<ButtonRelease-1>", lambda e, b=builder, l=lb: self._popup_menu(b, l))
            self.menu_btns[name] = (lb, builder)
        tk.Frame(top, bg=K["border"], width=1, height=20).pack(side="left", padx=8)
        tools = tk.Frame(top, bg=K["panel"])
        tools.pack(side="left")
        groups = [
            [("new", self.new_scenario, "Nuevo (Ctrl+N)"), ("open", self.open_dialog, "Abrir… (Ctrl+O)"),
             ("save", self.save, "Guardar (Ctrl+S)")],
            [("import", lambda: self.ws and self.ws.choose_file(), "Importar Input para Análisis (Ctrl+I)"),
             ("run", lambda: self.ws and self.ws.run(), "Ejecutar Experimento (F5)")],
            [("excel", self.export_plan, "Exportar Plan Modificado a Excel (Ctrl+E)"),
             ("report", self.export_report, "Exportar Reporte Excel (Ctrl+Shift+E)")],
            [("moon", self.toggle_dark, "Activar / Desactivar Modo Oscuro (Ctrl+Shift+M)")],
        ]
        for gi, g in enumerate(groups):
            for icon, cmd, tip in g:
                IconButton(tools, icon, cmd, tip, size=28, color=K["primary"] if icon == "run" else None).pack(
                    side="left", padx=1, pady=4)
            if gi < len(groups) - 1:
                tk.Frame(tools, bg=K["border"], width=1, height=18).pack(side="left", padx=6)
        brand = tk.Frame(top, bg=K["panel"])
        brand.pack(side="right", padx=12)
        if self.logo_small is not None:
            tk.Label(brand, image=self.logo_small, bg=K["panel"]).pack(side="left", padx=(0, 6))
        label(brand, APP_NAME, F["brand"]).pack(side="left")
        label(brand, APP_SUBTITLE, F["small"], K["muted"]).pack(side="left", padx=(8, 4), pady=(3, 0))
        label(brand, f"v{VERSION}", F["small"], K["muted"]).pack(side="left", pady=(3, 0))
        tk.Frame(root, bg=K["border"], height=1).pack(fill="x")
        self.tabbar = tk.Frame(root, bg=K["bg"])
        self.tabbar.pack(fill="x", padx=8, pady=(6, 0))
        self.status = tk.Frame(root, bg=K["alt"])
        self.status.pack(fill="x", side="bottom")
        tk.Frame(root, bg=K["border"], height=1).pack(fill="x", side="bottom")
        self.status_l = label(self.status, "Listo", F["small"], K["muted"])
        self.status_l.pack(side="left", padx=10, pady=4)
        self.status_r = label(self.status, "", F["small"], K["muted"])
        self.status_r.pack(side="right", padx=10, pady=4)
        self.area = tk.Frame(root, bg=K["bg"])
        self.area.pack(fill="both", expand=True)

    def _popup_menu(self, builder, anchor):
        close_popup()
        m = tk.Menu(self.root, tearoff=0)
        builder(m)
        m.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def _menu_file(self, m):
        m.add_command(label="Nuevo", accelerator="Ctrl+N", command=self.new_scenario)
        m.add_command(label="Abrir…", accelerator="Ctrl+O", command=self.open_dialog)
        rec = tk.Menu(m, tearoff=0)
        recent = self.prefs.recent()
        for p in recent:
            rec.add_command(label=f"{os.path.basename(p)}  —  {os.path.dirname(p)}", command=lambda p=p: self.open_project(p))
        if recent:
            rec.add_separator()
        rec.add_command(label="Limpiar Lista", command=lambda: self.prefs.set("recent", []))
        m.add_cascade(label="Abrir Existente", menu=rec)
        m.add_separator()
        m.add_command(label="Guardar", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="Guardar Como…", accelerator="Ctrl+Shift+S", command=self.save_as)
        m.add_separator()
        m.add_command(label="Desactivar Modo Oscuro" if self.dark else "Activar Modo Oscuro",
                      accelerator="Ctrl+Shift+M", command=self.toggle_dark)
        m.add_separator()
        m.add_command(label="Cerrar Escenario", accelerator="Ctrl+W", command=lambda: self.close_scenario(self.ws))
        m.add_command(label="Salir", accelerator="Alt+F4", command=self.quit)

    def _menu_model(self, m):
        m.add_command(label="Importar Input para Análisis…", accelerator="Ctrl+I",
                      command=lambda: self.ws and self.ws.choose_file())
        m.add_command(label="Ejecutar Experimento", accelerator="F5", command=lambda: self.ws and self.ws.run())
        m.add_separator()
        m.add_command(label="Exportar Plan Modificado (Excel)…", accelerator="Ctrl+E", command=self.export_plan)
        m.add_command(label="Exportar Reporte (Excel)…", accelerator="Ctrl+Shift+E", command=self.export_report)
        m.add_separator()
        m.add_command(label="Abrir Carpeta de Salida", command=self._open_out_dir)

    def _menu_about(self, m):
        m.add_command(label=f"Acerca de {APP_NAME}", accelerator="F1", command=self.about)

    def _bind_keys(self):
        r = self.root
        r.bind_all("<Control-n>", lambda e: self.new_scenario())
        r.bind_all("<Control-o>", lambda e: self.open_dialog())
        r.bind_all("<Control-s>", lambda e: self.save())
        r.bind_all("<Control-S>", lambda e: self.save_as())
        r.bind_all("<Control-Shift-S>", lambda e: self.save_as())
        r.bind_all("<Control-w>", lambda e: self.close_scenario(self.ws))
        r.bind_all("<Control-i>", lambda e: self.ws and self.ws.choose_file())
        r.bind_all("<F5>", lambda e: self.ws and self.ws.run())
        r.bind_all("<Control-e>", lambda e: self.export_plan())
        r.bind_all("<Control-E>", lambda e: self.export_report())
        r.bind_all("<Control-Shift-E>", lambda e: self.export_report())
        r.bind_all("<Control-M>", lambda e: self.toggle_dark())
        r.bind_all("<Control-Shift-M>", lambda e: self.toggle_dark())
        r.bind_all("<F1>", lambda e: self.about())
        r.bind_all("<Alt-a>", lambda e: self._key_menu("Archivo"))
        r.bind_all("<Alt-m>", lambda e: self._key_menu("Modelo"))

    def _key_menu(self, name):
        lb, b = self.menu_btns[name]
        self._popup_menu(b, lb)

    # ---- escenarios -------------------------------------------------------
    @property
    def ws(self):
        return self.active

    def new_scenario(self):
        self.counter += 1
        ws = Workspace(self.area, self, self.counter)
        self.workspaces.append(ws)
        self.activate(ws)
        return ws

    def activate(self, ws):
        close_popup()
        if self.active is not None and self.active is not ws:
            self.active.pack_forget()
        self.active = ws
        ws.pack(fill="both", expand=True)
        self.update_chrome()

    def close_scenario(self, ws):
        if ws is None:
            return
        if ws.dirty and not self._confirm_save(ws):
            return
        idx = self.workspaces.index(ws)
        self.workspaces.remove(ws)
        ws.destroy()
        if self.active is ws:
            self.active = None
            if self.workspaces:
                self.activate(self.workspaces[min(idx, len(self.workspaces) - 1)])
            else:
                self.new_scenario()
        self.update_chrome()

    def _confirm_save(self, ws):
        if ws is not self.active:
            self.activate(ws)
        r = dialog(self.root, "Cambios sin Guardar", f"¿Desea guardar los cambios de «{ws.title}»?", "question",
                   (("save", "Guardar"), ("no", "No Guardar"), ("cancel", "Cancelar")), default="save")
        if r == "save":
            return self.save()
        return r == "no"

    def update_chrome(self):
        """Título, pestañas de escenarios y barra de estado.

        Solo reconstruye la barra de pestañas cuando cambian los escenarios abiertos o el activo;
        en los demás casos actualiza los textos en su lugar (sin parpadeo al escribir)."""
        ws = self.active
        if ws is None:
            return
        title = f"{APP_NAME}: {ws.title}"
        if self.root.title() != title:
            self.root.title(title)
        key = (tuple(id(s) for s in self.workspaces), id(ws))
        if key != getattr(self, "_tabs_key", None) or not all(
                str(t[0]) and t[0].winfo_exists() for t in getattr(self, "_tab_labels", {}).values()):
            self._build_tabbar(ws)
            self._tabs_key = key
        for s in self.workspaces:
            lb, tip = self._tab_labels[id(s)]
            txt = ("● " if s.dirty else "") + s.title
            if lb.cget("text") != txt:
                lb.configure(text=txt)
            tip.text = s.path or "Sin guardar"
        parts = [f"Escenario: {ws.title}", f"Resultados: {ws.results_state()}"]
        if ws.result is not None:
            parts.append(f"Calculado el {ws.result.when}")
            parts.append(C.EXPERIMENTS.get(ws.result.experiment, ""))
        if ws.path:
            parts.append(os.path.basename(ws.path))
        txt = "   ·   ".join(parts)
        if self.status_r.cget("text") != txt:
            self.status_r.configure(text=txt)
        ws.update_year()

    def _build_tabbar(self, ws):
        for w in self.tabbar.winfo_children():
            w.destroy()
        self._tab_labels = {}
        for s in self.workspaces:
            on = s is ws
            f = tk.Frame(self.tabbar, bg=K["panel"] if on else K["bg"])
            f.pack(side="left", padx=(0, 2))
            tk.Frame(f, bg=K["accent"] if on else K["bg"], height=2).pack(fill="x")
            inner = tk.Frame(f, bg=f.cget("bg"))
            inner.pack()
            lb = tk.Label(inner, text="", font=F["bold"] if on else F["base"], bg=f.cget("bg"), fg=K["text"], padx=10,
                          pady=5, cursor="hand2")
            lb.pack(side="left")
            x = tk.Label(inner, text="✕", font=F["small"], bg=f.cget("bg"), fg=K["muted"], padx=6, cursor="hand2")
            x.pack(side="left")
            lb.bind("<ButtonRelease-1>", lambda e, s=s: self.activate(s))
            lb.bind("<ButtonRelease-2>", lambda e, s=s: self.close_scenario(s))
            x.bind("<ButtonRelease-1>", lambda e, s=s: self.close_scenario(s))
            self._tab_labels[id(s)] = (lb, Tooltip(lb, s.path or "Sin guardar"))
        plus = tk.Label(self.tabbar, text="+", font=F["title"], bg=K["bg"], fg=K["muted"], padx=8, cursor="hand2")
        plus.pack(side="left")
        plus.bind("<ButtonRelease-1>", lambda e: self.new_scenario())
        Tooltip(plus, "Nuevo Escenario (Ctrl+N)")

    def notify(self, msg, ms=5000):
        self.status_l.configure(text=msg)
        if self._status_job:
            self.root.after_cancel(self._status_job)
        self._status_job = self.root.after(ms, lambda: self.status_l.configure(text="Listo"))

    # ---- trabajo en segundo plano ----------------------------------------
    def background(self, title, work, done, cancelable=False):
        if self.busy:
            self.notify("Hay una tarea en curso; espere a que termine.")
            return
        self.busy = True
        flag = threading.Event()
        pw = ProgressWindow(self.root, title, cancel=flag.set if cancelable else None)
        t0 = time.time()

        def progress(msg, frac):
            if flag.is_set():
                from .engine import Cancelled
                raise Cancelled()
            self.q.put(("progress", pw, msg, frac))

        def runner():
            try:
                res = work(progress, flag.is_set)
                self.q.put(("done", pw, done, res, None, t0))
            except BaseException as ex:  # noqa: BLE001
                self.q.put(("done", pw, done, None, ex, t0))
        threading.Thread(target=runner, daemon=True).start()

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "progress":
                    _, pw, msg, frac = item
                    if pw.winfo_exists():
                        pw.update_progress(msg, frac)
                        self.status_l.configure(text=msg)
                else:
                    _, pw, done, res, ex, t0 = item
                    self.busy = False
                    if pw.winfo_exists():
                        pw.close()
                    if ex is not None:
                        from .engine import Cancelled
                        if isinstance(ex, Cancelled):
                            self.notify("Tarea cancelada")
                        else:
                            traceback.print_exception(type(ex), ex, ex.__traceback__)
                            dialog(self.root, "No se Pudo Completar la Tarea", str(ex) or type(ex).__name__, "error")
                            self.notify("Error")
                    else:
                        try:
                            done(res)
                        except Exception as e2:  # noqa: BLE001
                            traceback.print_exc()
                            dialog(self.root, "Error al Mostrar Resultados", str(e2), "error")
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    # ---- archivo de proyecto --------------------------------------------
    def open_dialog(self):
        init = self.prefs.get("last_dir") or os.path.join(app_dir(), "Escenarios")
        if not os.path.isdir(init):
            init = desktop()
        p = filedialog.askopenfilename(parent=self.root, title="Abrir Escenario", initialdir=init,
                                       filetypes=[(f"Escenario {APP_NAME}", "*" + PROJECT_EXT)])
        if p:
            self.open_project(p)

    def open_project(self, path):
        for s in self.workspaces:
            if s.path and os.path.normcase(s.path) == os.path.normcase(path):
                self.activate(s)
                return
        try:
            cfg, stored = C.load_project(path)
        except Exception as ex:
            dialog(self.root, "No se Pudo Abrir el Escenario", str(ex), "error")
            return
        ws = self.active
        if ws is None or ws.dirty or ws.path or ws.plan is not None:
            ws = self.new_scenario()
        ws.path = path
        ws.cfg = cfg
        self.prefs.set("last_dir", os.path.dirname(path))
        self.prefs.add_recent(path)
        src = cfg["general"].get("archivo", "")
        if src and not os.path.exists(src):
            alt = os.path.join(os.path.dirname(path), os.path.basename(src))
            if os.path.exists(alt):
                cfg["general"]["archivo"] = src = alt
        res = None
        if stored is not None:
            from .engine import Result
            try:
                res = Result.from_storage(*stored)
            except Exception:
                traceback.print_exc()
                res = None
        if res is not None:
            ws.result = res
            ws.calc_digest = C.config_digest(res.cfg)
            plan = res.plan
            same = (src and os.path.exists(src) and os.path.normcase(plan.path) == os.path.normcase(src)
                    and abs(os.path.getmtime(src) - plan.file_mtime) < 1 and os.path.getsize(src) == plan.file_size)
            if same or not (src and os.path.exists(src)):
                ws.plan = plan
                if src and os.path.exists(src):
                    from .plan import list_sheets
                    try:
                        ws.sheets = list_sheets(src)
                    except Exception:
                        ws.sheets = [plan.sheet]
                else:
                    ws.sheets = [plan.sheet]
                ws.dirty = False
                ws.refresh_all()
                ws.show("res")
                self.update_chrome()
                self.notify(f"Escenario abierto: {ws.title}")
                return
        if src and os.path.exists(src):
            from .plan import list_sheets
            ws.sheets = list_sheets(src)

            def after():
                ws.dirty = False
                self.update_chrome()
                if res is not None:
                    self.notify("El Excel cambió desde el último cálculo: los resultados quedan desactualizados")
                    ws.calc_digest = None
            ws.load_sheet(cfg["general"].get("hoja"), after=after, keep_config=True)
        else:
            ws.dirty = False
            ws.refresh_all()
            self.update_chrome()
            if src:
                dialog(self.root, "Archivo Base no Encontrado",
                       f"No se encontró el Input para Análisis:\n{src}\n\nSeleccione su nueva ubicación en Inputs.",
                       "warn")
        self.notify(f"Escenario abierto: {ws.title}")

    def save(self):
        ws = self.active
        if ws is None:
            return False
        if not ws.path:
            return self.save_as()
        return self._write(ws, ws.path)

    def save_as(self):
        ws = self.active
        if ws is None:
            return False
        init = self.prefs.get("last_dir") or os.path.join(app_dir(), "Escenarios")
        if not os.path.isdir(init):
            init = desktop()
        name = ws.cfg["general"]["nombre"].strip() or "Escenario"
        p = filedialog.asksaveasfilename(parent=self.root, title="Guardar Como", initialdir=init,
                                         initialfile=_safe(name) + PROJECT_EXT, defaultextension=PROJECT_EXT,
                                         filetypes=[(f"Escenario {APP_NAME}", "*" + PROJECT_EXT)])
        if not p:
            return False
        if not p.lower().endswith(PROJECT_EXT):
            p += PROJECT_EXT
        return self._write(ws, p)

    def _write(self, ws, path):
        res = ws.result
        if res is not None and ws.results_state() == "Desactualizados":
            r = dialog(self.root, "Resultados Desactualizados",
                       "La configuración cambió después del cálculo. Se guardará solo la configuración (inputs). "
                       "Pulse F5 antes de guardar para incluir resultados vigentes.", "warn",
                       (("ok", "Guardar Configuración"), ("cancel", "Cancelar")))
            if r != "ok":
                return False
            res = None
        try:
            C.save_project(path, ws.cfg, res)
        except Exception as ex:
            dialog(self.root, "No se Pudo Guardar", str(ex), "error")
            return False
        ws.path = path
        ws.dirty = False
        self.prefs.set("last_dir", os.path.dirname(path))
        self.prefs.add_recent(path)
        self.update_chrome()
        self.notify(f"Escenario guardado: {os.path.basename(path)}" + (" (inputs + resultados)" if res else " (inputs)"))
        return True

    # ---- exportaciones ----------------------------------------------------
    def _out_dir(self):
        d = os.path.join(app_dir(), "Outputs")
        if os.path.isdir(d):
            return d
        ws = self.active
        if ws and ws.path:
            return os.path.dirname(ws.path)
        return desktop()

    def _open_out_dir(self):
        _open_path(self._out_dir())

    def _need_result(self):
        ws = self.active
        if ws is None or ws.result is None:
            dialog(self.root, "Sin Resultados", "Ejecute un experimento (F5) antes de exportar.", "info")
            return None
        return ws

    def export_plan(self):
        ws = self._need_result()
        if not ws:
            return
        name = _safe(ws.title) + " - Plan Modificado.xlsx"
        p = filedialog.asksaveasfilename(parent=self.root, title="Exportar Plan Modificado", initialdir=self._out_dir(),
                                         initialfile=name, defaultextension=".xlsx", filetypes=[("Libro de Excel", "*.xlsx")])
        if not p:
            return
        from .export import export_plan
        res = ws.result

        def done(n):
            self.notify(f"Plan modificado exportado ({n:,} celdas actualizadas): {os.path.basename(p)}")
            if dialog(self.root, "Exportación Completa", f"Se creó:\n{p}", "ok",
                      (("open", "Abrir"), ("ok", "Aceptar")), default="ok") == "open":
                _open_path(p)
        self.background("Exportando Plan Modificado", lambda pr, c: export_plan(res, p, pr), done)

    def export_report(self):
        ws = self._need_result()
        if not ws:
            return
        name = _safe(ws.title) + " - Reporte.xlsx"
        p = filedialog.asksaveasfilename(parent=self.root, title="Exportar Reporte", initialdir=self._out_dir(),
                                         initialfile=name, defaultextension=".xlsx", filetypes=[("Libro de Excel", "*.xlsx")])
        if not p:
            return
        from .export import export_report
        res = ws.result

        def done(_):
            self.notify(f"Reporte exportado: {os.path.basename(p)}")
            if dialog(self.root, "Exportación Completa", f"Se creó:\n{p}", "ok",
                      (("open", "Abrir"), ("ok", "Aceptar")), default="ok") == "open":
                _open_path(p)
        self.background("Exportando Reporte", lambda pr, c: export_report(res, p, pr), done)

    # ---- varios -----------------------------------------------------------
    def about(self):
        from .dialogs import AboutDialog
        AboutDialog(self.root, self.logo_big)

    def toggle_dark(self):
        close_popup()
        self.dark = not self.dark
        self.prefs.set("dark", self.dark)
        theme.apply(self.root, self.dark)
        # reconstruye la interfaz conservando los escenarios
        states = []
        for s in self.workspaces:
            states.append({"cfg": s.cfg, "plan": s.plan, "sheets": s.sheets, "result": s.result,
                           "digest": s.calc_digest, "path": s.path, "dirty": s.dirty, "cur": s.cur, "number": s.number})
        act = self.workspaces.index(self.active) if self.active in self.workspaces else 0
        self._build()
        self.workspaces = []
        self.active = None
        for st in states:
            ws = Workspace(self.area, self, st["number"])
            ws.cfg, ws.plan, ws.sheets, ws.result = st["cfg"], st["plan"], st["sheets"], st["result"]
            ws.calc_digest, ws.path, ws.dirty = st["digest"], st["path"], st["dirty"]
            ws.refresh_all()
            ws.show(st["cur"] or "inputs")
            self.workspaces.append(ws)
            ws.pack_forget()
        if self.workspaces:
            self.activate(self.workspaces[act])

    def quit(self):
        close_popup()
        for ws in list(self.workspaces):
            if ws.dirty and not self._confirm_save(ws):
                return
        try:
            zoomed = self.root.state() == "zoomed"
            self.prefs.data["zoomed"] = zoomed
            if not zoomed:
                self.prefs.data["geometry"] = self.root.geometry()
            self.prefs.save()
        except Exception:
            pass
        self.root.destroy()


def _safe(name):
    return "".join(ch for ch in name if ch not in '<>:"/\\|?*').strip() or "Escenario"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PlanMaterialShift.App")
        except Exception:
            pass
    root = tk.Tk()
    root.withdraw()
    App(root, argv)
    root.deiconify()
    root.mainloop()
