"""Controles visuales propios (estilo SimA) sobre tkinter."""
from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import ttk

from . import APP_NAME
from .theme import C, F, titlebar


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------
def fmt(v, dec=0, dash_zero=False):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, str):
        return v
    if dash_zero and abs(v) < 0.5 * 10 ** (-dec):
        return "0"
    return f"{v:,.{dec}f}"


def fmt_signed(v, dec=0):
    s = fmt(abs(v), dec)
    if abs(v) < 0.5 * 10 ** (-dec):
        return "0"
    return ("+" if v > 0 else "−") + s


def center(win, parent=None, w=None, h=None):
    win.update_idletasks()
    w = w or win.winfo_reqwidth()
    h = h or win.winfo_reqheight()
    if parent is not None and parent.winfo_viewable():
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    else:
        px, py, pw, ph = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()
    x = px + max(0, (pw - w) // 2)
    y = py + max(0, (ph - h) // 3)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = min(max(0, x), max(0, sw - w))
    y = min(max(0, y), max(0, sh - h - 40))
    win.geometry(f"{w}x{h}+{x}+{y}")


# rueda del mouse: se enruta al primer ancestro desplazable bajo el puntero
def install_wheel(root):
    def handler(ev, delta=None):
        w = root.winfo_containing(ev.x_root, ev.y_root)
        if delta is None:
            delta = ev.delta if sys.platform == "darwin" else ev.delta / 120
        shift = bool(ev.state & 0x0001)
        while w is not None:
            fn = getattr(w, "_wheel", None)
            if fn is not None:
                if fn(delta, shift):
                    return "break"
            try:
                w = w.master
            except Exception:
                break
        return None
    root.bind_all("<MouseWheel>", handler, add="+")
    root.bind_all("<Shift-MouseWheel>", handler, add="+")
    root.bind_all("<Button-4>", lambda e: handler(e, 1), add="+")
    root.bind_all("<Button-5>", lambda e: handler(e, -1), add="+")


class Tooltip:
    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._hide()
        self.job = self.widget.after(self.delay, self._show)

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.configure(bg=C["border"])
        tk.Label(tw, text=text, bg=C["panel"], fg=C["text"], font=F["small"], justify="left", padx=7, pady=4,
                 wraplength=360).pack(padx=1, pady=1)
        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self, _e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


def autowrap(lbl, pad=4):
    """Ajusta el ancho de línea del texto al ancho disponible del rótulo."""
    lbl.bind("<Configure>", lambda e: lbl.configure(wraplength=max(60, e.width - pad)), add="+")
    return lbl


def label(parent, text="", font=None, fg=None, bg=None, **kw):
    return tk.Label(parent, text=text, font=font or F["base"], fg=fg or C["text"],
                    bg=bg or parent.cget("bg"), **kw)


def sep(parent, orient="h", pad=6, color=None):
    f = tk.Frame(parent, bg=color or C["border"], height=1 if orient == "h" else 1, width=1)
    if orient == "h":
        f.pack(fill="x", pady=pad)
    else:
        f.pack(side="left", fill="y", padx=pad)
    return f


# ---------------------------------------------------------------------------
# iconos vectoriales (independientes de las fuentes instaladas)
# ---------------------------------------------------------------------------
def draw_icon(cv, name, s, color, x0=0, y0=0):
    def L(*pts, w=1.4, fill=None):
        return cv.create_line(*[p + (x0 if i % 2 == 0 else y0) for i, p in enumerate(pts)], fill=fill or color,
                              width=w, capstyle="round", joinstyle="round")

    def R(a, b, c, d, fill="", outline=None, w=1.3):
        return cv.create_rectangle(a + x0, b + y0, c + x0, d + y0, fill=fill, outline=outline or color, width=w)

    k = s / 20.0

    def P(*v):
        return [x * k for x in v]
    if name == "new":
        L(*P(5, 2, 12, 2, 16, 6, 16, 18, 5, 18, 5, 2))
        L(*P(12, 2, 12, 6, 16, 6))
    elif name == "open":
        L(*P(2, 5, 7, 5, 9, 7, 17, 7, 17, 16, 2, 16, 2, 5))
        L(*P(2, 16, 5, 10, 19, 10, 17, 16))
    elif name == "save":
        L(*P(3, 3, 14, 3, 17, 6, 17, 17, 3, 17, 3, 3))
        R(*P(6, 3, 13, 7))
        R(*P(6, 11, 14, 17))
    elif name == "import":
        L(*P(10, 2, 10, 12))
        L(*P(6, 8, 10, 12, 14, 8))
        L(*P(3, 13, 3, 17, 17, 17, 17, 13))
    elif name == "run":
        cv.create_polygon(*[p + (x0 if i % 2 == 0 else y0) for i, p in enumerate(P(6, 3, 17, 10, 6, 17))],
                          fill=color, outline=color)
    elif name == "excel":
        R(*P(3, 3, 17, 17))
        L(*P(3, 8, 17, 8))
        L(*P(3, 12.5, 17, 12.5))
        L(*P(8, 3, 8, 17))
    elif name == "report":
        L(*P(3, 17, 17, 17))
        R(*P(5, 10, 8, 17), fill=color)
        R(*P(9, 6, 12, 17), fill=color)
        R(*P(13, 3, 16, 17), fill=color)
    elif name == "moon":
        a = P(3, 3, 17, 17)
        b = P(7, 1, 20, 14)
        cv.create_oval(a[0] + x0, a[1] + y0, a[2] + x0, a[3] + y0, fill=color, outline=color)
        cv.create_oval(b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0, fill=cv.cget("bg"), outline=cv.cget("bg"))
    elif name == "folder":
        L(*P(2, 5, 7, 5, 9, 7, 17, 7, 17, 16, 2, 16, 2, 5))
    elif name == "file":
        L(*P(5, 2, 12, 2, 16, 6, 16, 18, 5, 18, 5, 2))
        R(*P(7, 9, 14, 15))
    elif name == "pin":
        L(*P(10, 12, 10, 18))
        R(*P(6, 2, 14, 7))
        L(*P(4, 12, 16, 12))
        L(*P(7, 7, 6, 12))
        L(*P(13, 7, 14, 12))
    elif name == "filter":
        L(*P(3, 4, 17, 4, 11, 11, 11, 16, 9, 17, 9, 11, 3, 4))
    elif name == "close":
        L(*P(5, 5, 15, 15))
        L(*P(15, 5, 5, 15))
    elif name == "plus":
        L(*P(10, 4, 10, 16))
        L(*P(4, 10, 16, 10))
    elif name == "grid":
        R(*P(3, 3, 9, 9))
        R(*P(11, 3, 17, 9))
        R(*P(3, 11, 9, 17))
        R(*P(11, 11, 17, 17))
    elif name == "help":
        cv.create_oval(*P(3, 3, 17, 17), outline=color, width=1.3)
        cv.create_text(10 * k + x0, 10 * k + y0, text="?", fill=color, font=(F["bold"][0], max(6, int(7 * k)), "bold"))


class IconButton(tk.Canvas):
    def __init__(self, parent, icon, command=None, tip="", size=26, color=None, bg=None):
        bgc = bg or parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=bgc, highlightthickness=0, cursor="hand2")
        self._bg = bgc
        self.icon, self.command, self.color = icon, command, color
        self.enabled = True
        self._draw()
        self.bind("<Enter>", lambda e: self.enabled and self.configure(bg=C["hover"]))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))
        self.bind("<ButtonRelease-1>", self._click)
        if tip:
            Tooltip(self, tip)

    def _draw(self):
        self.delete("all")
        s = int(self["width"])
        col = (self.color or C["muted"]) if self.enabled else C["disabled"]
        draw_icon(self, self.icon, s - 8, col, 4, 4)

    def set_enabled(self, on):
        self.enabled = on
        self._draw()

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()


# ---------------------------------------------------------------------------
# botones
# ---------------------------------------------------------------------------
class Btn(tk.Label):
    """Botón plano: kind = default | primary | accent | link | subtle."""

    def __init__(self, parent, text, command=None, kind="default", width=None, tip="", padx=12, pady=4, font=None):
        self.kind = kind
        self.command = command
        self.enabled = True
        super().__init__(parent, text=text, font=font or F["base"], padx=padx, pady=pady, cursor="hand2",
                         highlightthickness=1)
        if width:
            self.configure(width=width)
        self._colors()
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", lambda e: self._colors())
        self.bind("<ButtonRelease-1>", self._click)
        if tip:
            Tooltip(self, tip)

    def _palette(self):
        k = self.kind
        if not self.enabled:
            return C["alt"], C["disabled"], C["border"]
        if k == "primary":
            return C["primary"], "#FFFFFF", C["primary"]
        if k == "accent":
            return C["accent"], "#FFFFFF", C["accent"]
        if k == "link":
            return self.master.cget("bg"), C["accent"], self.master.cget("bg")
        if k == "subtle":
            return self.master.cget("bg"), C["muted"], self.master.cget("bg")
        return C["panel"], C["text"], C["border"]

    def _colors(self):
        bg, fg, bd = self._palette()
        self.configure(bg=bg, fg=fg, highlightbackground=bd, highlightcolor=bd)

    def _enter(self, _e):
        if not self.enabled:
            return
        if self.kind == "primary":
            self.configure(bg=C["primary_hover"])
        elif self.kind in ("default",):
            self.configure(bg=C["hover"])
        elif self.kind in ("link", "subtle"):
            self.configure(fg=C["accent"])

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self._colors()


class Segmented(tk.Frame):
    """Botones segmentados de selección única."""

    def __init__(self, parent, options, value=None, command=None, font=None, padx=12, pady=4, colors=None):
        super().__init__(parent, bg=C["border"])
        self.colors = colors or {}
        self.options = list(options)
        self.command = command
        self.value = value if value is not None else self.options[0][0]
        self.enabled = True
        self.labels = {}
        inner = tk.Frame(self, bg=C["border"])
        inner.pack(padx=1, pady=1)
        for i, (key, text) in enumerate(self.options):
            lb = tk.Label(inner, text=text, font=font or F["base"], padx=padx, pady=pady, cursor="hand2")
            lb.pack(side="left", padx=(0 if i == 0 else 1, 0))
            lb.bind("<ButtonRelease-1>", lambda e, k=key: self._pick(k))
            lb.bind("<Enter>", lambda e, k=key: self._hover(k, True))
            lb.bind("<Leave>", lambda e, k=key: self._hover(k, False))
            self.labels[key] = lb
        self._paint()

    def _paint(self):
        for k, lb in self.labels.items():
            if not self.enabled:
                on = k == self.value
                lb.configure(bg=C["border"] if on else C["alt"], fg=C["panel"] if on else C["disabled"], cursor="arrow")
            elif k == self.value:
                lb.configure(bg=self.colors.get(k, C["accent"]), fg="#FFFFFF", cursor="hand2")
            else:
                lb.configure(bg=C["panel"], fg=C["text"], cursor="hand2")

    def _hover(self, k, on):
        if self.enabled and k != self.value:
            self.labels[k].configure(bg=C["hover"] if on else C["panel"])

    def _pick(self, k):
        if not self.enabled or k == self.value:
            return
        self.value = k
        self._paint()
        if self.command:
            self.command(k)

    def set(self, k, notify=False):
        self.value = k
        self._paint()
        if notify and self.command:
            self.command(k)

    def get(self):
        return self.value

    def set_enabled(self, on):
        self.enabled = on
        self._paint()


class Check(tk.Frame):
    """Casilla dibujada (se ve igual en Windows y en modo oscuro)."""

    def __init__(self, parent, text="", value=False, command=None, font=None, bg=None, size=14):
        bgc = bg or parent.cget("bg")
        super().__init__(parent, bg=bgc)
        self.value = bool(value)
        self.command = command
        self.enabled = True
        self.size = size
        self.cv = tk.Canvas(self, width=size + 2, height=size + 2, bg=bgc, highlightthickness=0, cursor="hand2")
        self.cv.pack(side="left")
        self.lb = None
        if text:
            self.lb = tk.Label(self, text=text, bg=bgc, fg=C["text"], font=font or F["base"], cursor="hand2")
            self.lb.pack(side="left", padx=(5, 0))
            self.lb.bind("<ButtonRelease-1>", self._toggle)
        self.cv.bind("<ButtonRelease-1>", self._toggle)
        self._draw()

    def _draw(self):
        cv, s = self.cv, self.size
        cv.delete("all")
        if self.enabled:
            fill = C["accent"] if self.value else C["input"]
            out = C["accent"] if self.value else C["muted"]
        else:
            fill = C["disabled"] if self.value else C["alt"]
            out = C["disabled"]
        cv.create_rectangle(1, 1, s, s, fill=fill, outline=out, width=1.2)
        if self.value:
            cv.create_line(3.5, s * 0.52, s * 0.42, s - 3.5, s - 3, 3.8, fill="#FFFFFF", width=2, capstyle="round")
        if self.lb:
            self.lb.configure(fg=C["text"] if self.enabled else C["disabled"])

    def _toggle(self, _e=None):
        if not self.enabled:
            return
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, v):
        self.value = bool(v)
        self._draw()

    def get(self):
        return self.value

    def set_enabled(self, on):
        self.enabled = on
        self.cv.configure(cursor="hand2" if on else "arrow")
        self._draw()

    def set_bg(self, bg):
        self.configure(bg=bg)
        self.cv.configure(bg=bg)
        if self.lb:
            self.lb.configure(bg=bg)


class Toggle(tk.Canvas):
    """Interruptor sutil (activar/desactivar bloque)."""

    def __init__(self, parent, value=True, command=None, bg=None, tip=""):
        bgc = bg or parent.cget("bg")
        super().__init__(parent, width=34, height=18, bg=bgc, highlightthickness=0, cursor="hand2")
        self.value = bool(value)
        self.command = command
        self.enabled = True
        self.bind("<ButtonRelease-1>", self._toggle)
        self._draw()
        if tip:
            Tooltip(self, tip)

    def _draw(self):
        self.delete("all")
        on = self.value
        track = (C["primary"] if on else C["border"]) if self.enabled else C["alt"]
        self.create_oval(1, 1, 17, 17, fill=track, outline=track)
        self.create_oval(17, 1, 33, 17, fill=track, outline=track)
        self.create_rectangle(9, 1, 25, 17, fill=track, outline=track)
        x = 25 if on else 9
        self.create_oval(x - 6, 3, x + 6, 15, fill="#FFFFFF", outline="#FFFFFF")

    def _toggle(self, _e=None):
        if not self.enabled:
            return
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, v):
        self.value = bool(v)
        self._draw()

    def set_enabled(self, on):
        self.enabled = on
        self._draw()


# ---------------------------------------------------------------------------
# contenedores
# ---------------------------------------------------------------------------
class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=None, horizontal=False):
        bgc = bg or C["bg"]
        super().__init__(parent, bg=bgc)
        self.canvas = tk.Canvas(self, bg=bgc, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=bgc)
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas._wheel = self._wheel
        self.body._wheel = self._wheel
        self._wheel_ok = True

    def _on_body(self, _e=None):
        self.canvas.configure(scrollregion=(0, 0, self.body.winfo_reqwidth(), self.body.winfo_reqheight()))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=max(e.width, 200))

    def _wheel(self, delta, shift):
        if shift:
            return False
        if self.body.winfo_reqheight() <= self.canvas.winfo_height():
            return False
        self.canvas.yview_scroll(int(-delta * 3), "units")
        return True

    def top(self):
        self.canvas.yview_moveto(0)


class Card(tk.Frame):
    """Recuadro con borde tenue y título opcional."""

    def __init__(self, parent, title=None, pad=12, bg=None, right=None):
        super().__init__(parent, bg=C["border"])
        self.inner = tk.Frame(self, bg=bg or C["panel"])
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.head = None
        if title is not None:
            self.head = tk.Frame(self.inner, bg=self.inner.cget("bg"))
            self.head.pack(fill="x", padx=pad, pady=(pad - 2, 4))
            self.title = tk.Label(self.head, text=title, font=F["section"], bg=self.inner.cget("bg"), fg=C["text"])
            self.title.pack(side="left")
        self.body = tk.Frame(self.inner, bg=self.inner.cget("bg"))
        self.body.pack(fill="both", expand=True, padx=pad, pady=(0 if title is not None else pad, pad))


def set_tree_state(widget, enabled, inactive_bg=None):
    """Atenúa recursivamente un bloque (modo inactivo/desconectado)."""
    for w in [widget] + _descendants(widget):
        fn = getattr(w, "set_enabled", None)
        if fn is not None and w is not widget:
            try:
                fn(enabled)
            except Exception:
                pass
        elif isinstance(w, tk.Label) and not isinstance(w, Btn):
            if not hasattr(w, "_fg0"):
                w._fg0 = w.cget("fg")
            w.configure(fg=w._fg0 if enabled else C["disabled"])
        elif isinstance(w, (ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            if isinstance(w, ttk.Combobox):
                w.configure(state="readonly" if enabled else "disabled")
            else:
                w.configure(state="normal" if enabled else "disabled")


def _descendants(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        if not hasattr(c, "set_enabled") or isinstance(c, (tk.Frame,)) and not isinstance(c, (Check, Segmented)):
            out.extend(_descendants(c))
    return out


# ---------------------------------------------------------------------------
# diálogos
# ---------------------------------------------------------------------------
def dialog(parent, title, text, kind="info", buttons=(("ok", "Aceptar"),), default=None, detail=None):
    """Aviso compacto: devuelve la clave del botón pulsado (o None con Esc)."""
    top = tk.Toplevel(parent)
    top.withdraw()
    top.title(APP_NAME)
    top.configure(bg=C["panel"])
    top.transient(parent.winfo_toplevel())
    top.resizable(False, False)
    res = {"v": None}
    colors = {"info": C["accent"], "error": C["bad_fg"], "warn": C["warn"], "ok": C["ok_fg"], "question": C["accent"]}
    glyph = {"info": "i", "error": "!", "warn": "!", "ok": "✓", "question": "?"}
    body = tk.Frame(top, bg=C["panel"])
    body.pack(fill="both", expand=True, padx=18, pady=(16, 8))
    cv = tk.Canvas(body, width=30, height=30, bg=C["panel"], highlightthickness=0)
    cv.pack(side="left", anchor="n", padx=(0, 12))
    cv.create_oval(2, 2, 28, 28, fill=colors.get(kind, C["accent"]), outline="")
    cv.create_text(15, 15, text=glyph.get(kind, "i"), fill="#FFFFFF", font=(F["bold"][0], 11, "bold"))
    txt = tk.Frame(body, bg=C["panel"])
    txt.pack(side="left", fill="both", expand=True)
    tk.Label(txt, text=title, font=F["title"], bg=C["panel"], fg=C["text"], anchor="w", justify="left").pack(fill="x")
    tk.Label(txt, text=text, font=F["base"], bg=C["panel"], fg=C["text"], anchor="w", justify="left",
             wraplength=430).pack(fill="x", pady=(4, 0))
    if detail:
        tk.Label(txt, text=detail, font=F["small"], bg=C["panel"], fg=C["muted"], anchor="w", justify="left",
                 wraplength=430).pack(fill="x", pady=(6, 0))
    foot = tk.Frame(top, bg=C["alt"])
    foot.pack(fill="x")
    bar = tk.Frame(foot, bg=C["alt"])
    bar.pack(side="right", padx=12, pady=10)
    default = default or buttons[0][0]

    def close(k):
        res["v"] = k
        top.grab_release()
        top.destroy()
    for k, t in buttons:
        Btn(bar, t, lambda k=k: close(k), kind="primary" if k == default else "default").pack(side="left", padx=4)
    top.bind("<Return>", lambda e: close(default))
    top.bind("<Escape>", lambda e: close(None))
    top.protocol("WM_DELETE_WINDOW", lambda: close(None))
    center(top, parent.winfo_toplevel())
    top.deiconify()
    titlebar(top)
    top.grab_set()
    top.focus_set()
    top.wait_window()
    return res["v"]


class ToolWindow(tk.Toplevel):
    """Ventana de herramienta centrada sobre la principal."""

    def __init__(self, parent, title, w=640, h=480, modal=True):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=C["panel"])
        self.transient(parent.winfo_toplevel())
        self.minsize(360, 240)
        self.body = tk.Frame(self, bg=C["panel"])
        self.body.pack(fill="both", expand=True)
        self.foot = tk.Frame(self, bg=C["alt"])
        self.foot.pack(fill="x", side="bottom")
        self.bar = tk.Frame(self.foot, bg=C["alt"])
        self.bar.pack(side="right", padx=12, pady=10)
        self.left = tk.Frame(self.foot, bg=C["alt"])
        self.left.pack(side="left", padx=12, pady=10)
        self._modal = modal
        self._size = (w, h)
        self.bind("<Escape>", lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def show(self):
        center(self, self.master.winfo_toplevel(), *self._size)
        self.deiconify()
        titlebar(self)
        if self._modal:
            self.grab_set()
        self.focus_set()
        if self._modal:
            self.wait_window()

    def cancel(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class ProgressWindow(tk.Toplevel):
    def __init__(self, parent, title, cancel=None):
        super().__init__(parent)
        self.withdraw()
        self.title(APP_NAME)
        self.configure(bg=C["panel"])
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        tk.Label(self, text=title, font=F["title"], bg=C["panel"], fg=C["text"], anchor="w").pack(
            fill="x", padx=18, pady=(16, 2))
        self.msg = tk.Label(self, text="", font=F["base"], bg=C["panel"], fg=C["muted"], anchor="w")
        self.msg.pack(fill="x", padx=18)
        self.pb = ttk.Progressbar(self, length=380, maximum=1.0, mode="determinate")
        self.pb.pack(padx=18, pady=(10, 12))
        self.cancelled = False
        foot = tk.Frame(self, bg=C["alt"])
        foot.pack(fill="x")
        if cancel:
            Btn(foot, "Cancelar", self._cancel).pack(side="right", padx=12, pady=8)

            def _c():
                self._cancel()
            self.protocol("WM_DELETE_WINDOW", _c)
        else:
            self.protocol("WM_DELETE_WINDOW", lambda: None)
            tk.Frame(foot, bg=C["alt"], height=8).pack()
        self._cancel_cb = cancel
        center(self, parent.winfo_toplevel(), 420, 150)
        self.deiconify()
        titlebar(self)
        self.grab_set()

    def _cancel(self):
        self.cancelled = True
        self.msg.configure(text="Cancelando…")
        if self._cancel_cb:
            self._cancel_cb()

    def update_progress(self, msg, frac):
        self.msg.configure(text=msg)
        self.pb.configure(value=max(0.0, min(1.0, frac)))

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# ---------------------------------------------------------------------------
# filtro emergente (estilo Excel)
# ---------------------------------------------------------------------------
_ACTIVE_POPUP = [None]


def close_popup():
    p = _ACTIVE_POPUP[0]
    if p is not None:
        try:
            p.apply()
        except tk.TclError:
            pass
    _ACTIVE_POPUP[0] = None


class FilterPopup(tk.Toplevel):
    """Lista con casillas, búsqueda (>8 valores), Seleccionar Todo, Limpiar, Aceptar/Cancelar."""

    def __init__(self, anchor, title, values, selected, on_apply, multi=True):
        close_popup()
        super().__init__(getattr(anchor, "cv", anchor))
        _ACTIVE_POPUP[0] = self
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=C["border"])
        self.values = list(values)
        self.sel = set(selected) if selected is not None else set(self.values)
        self.orig = set(self.sel)
        self.on_apply = on_apply
        self.done = False
        box = tk.Frame(self, bg=C["panel"])
        box.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(box, bg=C["alt"])
        head.pack(fill="x")
        tk.Label(head, text=title, font=F["bold"], bg=C["alt"], fg=C["text"]).pack(side="left", padx=8, pady=4)
        x = tk.Label(head, text="✕", bg=C["alt"], fg=C["muted"], cursor="hand2")
        x.pack(side="right", padx=8)
        x.bind("<ButtonRelease-1>", lambda e: self.apply())
        self._drag(head)
        Btn(box, "Limpiar Filtro", self._clear, kind="link", padx=8, pady=2).pack(anchor="w", padx=4, pady=(4, 0))
        self.search = None
        if len(self.values) > 8:
            self.search = ttk.Entry(box)
            self.search.pack(fill="x", padx=8, pady=4)
            self.search.insert(0, "")
            self.search.bind("<KeyRelease>", lambda e: self._fill())
        self.all = Check(box, "(Seleccionar Todo)", True, self._toggle_all)
        self.all.pack(anchor="w", padx=8, pady=(4, 2))
        sf = ScrollFrame(box, bg=C["panel"])
        sf.pack(fill="both", expand=True, padx=4)
        self.listf = sf.body
        self.sf = sf
        bar = tk.Frame(box, bg=C["panel"])
        bar.pack(fill="x", pady=6)
        Btn(bar, "Cancelar", self.cancel).pack(side="right", padx=(4, 8))
        Btn(bar, "Aceptar", self.apply, kind="primary").pack(side="right")
        self.checks = {}
        self._fill()
        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.apply())
        h = min(420, 150 + 24 * min(len(self.values), 12) + (34 if self.search else 0))
        w = 250
        x0 = anchor.winfo_rootx()
        y0 = anchor.winfo_rooty() + anchor.winfo_height() + 2
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x0 = min(x0, sw - w - 4)
        if y0 + h > sh - 40:
            y0 = max(0, anchor.winfo_rooty() - h - 2)
        self.geometry(f"{w}x{h}+{x0}+{y0}")
        self.deiconify()
        self.lift()
        self.focus_force()
        if self.search:
            self.search.focus_set()
        self.bind("<FocusOut>", self._focus_out)

    def _drag(self, w):
        def start(e):
            self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

        def move(e):
            self.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")
        w.bind("<ButtonPress-1>", start)
        w.bind("<B1-Motion>", move)

    def _focus_out(self, _e):
        self.after(150, self._check_focus)

    def _check_focus(self):
        if self.done:
            return
        try:
            f = self.focus_get()
        except (KeyError, tk.TclError):
            f = None
        if f is None or not str(f).startswith(str(self)):
            self.apply()

    def _visible(self):
        q = self.search.get().strip().lower() if self.search else ""
        return [v for v in self.values if q in str(v).lower()]

    def _fill(self):
        for w in self.listf.winfo_children():
            w.destroy()
        self.checks = {}
        for v in self._visible():
            ch = Check(self.listf, str(v) if str(v) != "" else "(Vacías)", v in self.sel,
                       lambda on, v=v: self._set(v, on), bg=C["panel"])
            ch.pack(anchor="w", padx=4, pady=1)
            self.checks[v] = ch
        self._sync_all()

    def _set(self, v, on):
        (self.sel.add if on else self.sel.discard)(v)
        self._sync_all()

    def _sync_all(self):
        vis = self._visible()
        self.all.set(bool(vis) and all(v in self.sel for v in vis))

    def _toggle_all(self, on):
        for v in self._visible():
            (self.sel.add if on else self.sel.discard)(v)
            if v in self.checks:
                self.checks[v].set(on)

    def _clear(self):
        self.sel = set(self.values)
        self.apply()

    def apply(self):
        if self.done:
            return
        self.done = True
        _ACTIVE_POPUP[0] = None
        sel = self.sel if self.sel else self.orig     # cero valores: conserva el filtro anterior
        try:
            self.destroy()
        except tk.TclError:
            pass
        if sel != self.orig:
            self.on_apply(sel)

    def cancel(self):
        self.done = True
        _ACTIVE_POPUP[0] = None
        self.destroy()


class FilterButton(tk.Frame):
    """Botón de filtro de gráfico: «Fase  Todas ▾»."""

    def __init__(self, parent, title, values, on_change, all_text="Todas"):
        super().__init__(parent, bg=parent.cget("bg"))
        self.title, self.values, self.on_change, self.all_text = title, list(values), on_change, all_text
        self.sel = set(self.values)
        tk.Label(self, text=title, bg=self.cget("bg"), fg=C["muted"], font=F["base"]).pack(side="left", padx=(0, 4))
        self.btn = tk.Label(self, text="", bg=C["panel"], fg=C["text"], font=F["base"], padx=8, pady=3,
                            cursor="hand2", highlightthickness=1, highlightbackground=C["border"])
        self.btn.pack(side="left")
        self.btn.bind("<ButtonRelease-1>", self._open)
        self._label()

    def _label(self):
        if len(self.sel) == len(self.values):
            t = self.all_text
        elif len(self.sel) == 1:
            t = str(next(iter(self.sel)))
        else:
            t = f"{len(self.sel)} Selecc."
        self.btn.configure(text=f"{t}  ▾", fg=C["text"] if len(self.sel) == len(self.values) else C["accent"])

    def _open(self, _e=None):
        FilterPopup(self.btn, self.title, self.values, self.sel, self._apply)

    def _apply(self, sel):
        self.sel = set(sel)
        self._label()
        self.on_change()

    def reset(self, values=None):
        if values is not None:
            self.values = list(values)
        self.sel = set(self.values)
        self._label()

    def selected(self):
        return self.sel


# ---------------------------------------------------------------------------
# lista de prioridad (arrastrar para ordenar)
# ---------------------------------------------------------------------------
class PriorityList(tk.Frame):
    def __init__(self, parent, title, on_change=None, toggle=True):
        super().__init__(parent, bg=C["border"])
        self.on_change = on_change
        self.items = []
        self.active = True
        self.enabled = True
        inner = tk.Frame(self, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(inner, bg=C["alt"])
        head.pack(fill="x")
        self.title = tk.Label(head, text=title, font=F["bold"], bg=C["alt"], fg=C["text"])
        self.title.pack(side="left", padx=8, pady=6)
        self.toggle = None
        if toggle:
            self.toggle = Toggle(head, True, self._toggle, bg=C["alt"], tip="Activar / desactivar este criterio")
            self.toggle.pack(side="right", padx=8)
        self.listf = tk.Frame(inner, bg=C["panel"])
        self.listf.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.count = tk.Label(inner, text="", font=F["small"], bg=C["panel"], fg=C["muted"], anchor="e")
        self.count.pack(fill="x", padx=8, pady=(0, 4))
        self.rows = []
        self._drag_from = None

    def set_items(self, items, active=True):
        self.items = [list(x) for x in items]
        self.active = active
        if self.toggle:
            self.toggle.set(active)
        self._render()

    def _render(self):
        for w in self.listf.winfo_children():
            w.destroy()
        self.rows = []
        en = self.enabled and self.active
        for i, (name, on) in enumerate(self.items):
            row = tk.Frame(self.listf, bg=C["border"])
            row.pack(fill="x", pady=2)
            r = tk.Frame(row, bg=C["panel"])
            r.pack(fill="x", padx=1, pady=1)
            num = tk.Label(r, text=f"{i + 1}.", width=3, anchor="e", bg=C["panel"],
                           fg=C["muted"] if en else C["disabled"], font=F["base"])
            num.pack(side="left", padx=(4, 2))
            ch = Check(r, "", on, lambda v, i=i: self._check(i, v), bg=C["panel"])
            ch.pack(side="left", padx=4, pady=4)
            ch.set_enabled(en)
            nm = tk.Label(r, text=name, bg=C["panel"], fg=C["text"] if en else C["disabled"], font=F["base"], anchor="w")
            nm.pack(side="left", fill="x", expand=True)
            h = tk.Label(r, text="≡", bg=C["panel"], fg=C["muted"] if en else C["disabled"], font=(F["base"][0], 12),
                         cursor="fleur" if en else "arrow")
            h.pack(side="right", padx=8)
            for w in (h, nm, num):
                w.bind("<ButtonPress-1>", lambda e, i=i: self._start(i))
                w.bind("<B1-Motion>", self._motion)
                w.bind("<ButtonRelease-1>", self._drop)
            for w in (r, nm, num, h):
                w.bind("<Alt-Up>", lambda e, i=i: self._move(i, -1))
                w.bind("<Alt-Down>", lambda e, i=i: self._move(i, 1))
            nm.bind("<Button-1>", lambda e, w=nm: w.focus_set(), add="+")
            nm.configure(takefocus=1)
            self.rows.append((row, r, nm))
        n_on = sum(1 for _, on in self.items if on)
        self.count.configure(text=f"{n_on} de {len(self.items)} habilitados")
        self.title.configure(fg=C["text"] if self.enabled else C["disabled"])

    def _check(self, i, v):
        self.items[i][1] = v
        self.count.configure(text=f"{sum(1 for _, on in self.items if on)} de {len(self.items)} habilitados")
        self._changed()

    def _toggle(self, v):
        self.active = v
        self._render()
        self._changed()

    def _start(self, i):
        if self.enabled and self.active:
            self._drag_from = i
            self._drag_to = i

    def _motion(self, e):
        if self._drag_from is None:
            return
        y = e.y_root
        tgt = self._drag_from
        for j, (row, r, nm) in enumerate(self.rows):
            if row.winfo_rooty() <= y <= row.winfo_rooty() + row.winfo_height():
                tgt = j
                break
        for j, (row, r, nm) in enumerate(self.rows):
            row.configure(bg=C["accent"] if j == tgt and tgt != self._drag_from else C["border"])
        self._drag_to = tgt

    def _drop(self, _e):
        if self._drag_from is None:
            return
        a, b = self._drag_from, getattr(self, "_drag_to", self._drag_from)
        self._drag_from = None
        if a != b:
            it = self.items.pop(a)
            self.items.insert(b, it)
            self._render()
            self._changed()
        else:
            for row, r, nm in self.rows:
                row.configure(bg=C["border"])

    def _move(self, i, d):
        j = i + d
        if not (self.enabled and self.active) or not (0 <= j < len(self.items)):
            return "break"
        self.items[i], self.items[j] = self.items[j], self.items[i]
        self._render()
        self.rows[j][2].focus_set()
        self._changed()
        return "break"

    def _changed(self):
        if self.on_change:
            self.on_change(self.items, self.active)

    def set_enabled(self, on):
        self.enabled = on
        if self.toggle:
            self.toggle.set_enabled(on)
        self._render()
