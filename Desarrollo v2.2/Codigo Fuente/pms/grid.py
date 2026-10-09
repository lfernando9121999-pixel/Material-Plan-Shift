"""Tabla virtualizada sobre Canvas: encabezados fijos, orden, filtro por columna,
color por celda, fila de total y copiado al portapapeles."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .theme import C, F, measure, px, shared_font
from .widgets import FilterPopup, draw_icon, fmt


class DataGrid(tk.Frame):
    RH = 22

    def __init__(self, parent, columns, cell_style=None, group_header=None, stretch=True, height=None,
                 on_select=None, frozen=0, min_col=56, status=None):
        super().__init__(parent, bg=C["border"])
        self.RH = px(22)
        self.columns = columns            # [{"title", "align", "fmt", "width", "filter", "key"}]
        self.cell_style = cell_style
        self.group_header = group_header  # [(texto, col_ini, col_fin)]
        self.stretch = stretch
        self.on_select = on_select
        self.min_col = min_col
        self.status = status
        self.rows = []
        self.total = None
        self.view = []
        self.sort_col, self.sort_dir = None, 0
        self.filters = {}
        self.sel = None
        self.widths = []
        self.font = shared_font(F["base"], self)
        self.bfont = shared_font(F["bold"], self)
        inner = tk.Frame(self, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        hh = self.RH + 6 + (self.RH if group_header else 0)
        self.hcv = tk.Canvas(inner, height=hh, bg=C["header"], highlightthickness=0)
        self.hcv.grid(row=0, column=0, sticky="ew")
        self.cv = tk.Canvas(inner, bg=C["panel"], highlightthickness=0, height=height or 200)
        self.cv.grid(row=1, column=0, sticky="nsew")
        self.vbar = ttk.Scrollbar(inner, orient="vertical", command=self._yview)
        self.vbar.grid(row=0, column=1, rowspan=2, sticky="ns")
        self.hbar = ttk.Scrollbar(inner, orient="horizontal", command=self._xview)
        self.hbar.grid(row=2, column=0, sticky="ew")
        self.foot = None
        inner.grid_rowconfigure(1, weight=1)
        inner.grid_columnconfigure(0, weight=1)
        self.cv.configure(yscrollcommand=self._yset, xscrollcommand=self._xset)
        self.cv.bind("<Configure>", self._on_configure)
        self._size = (0, 0)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Button-3>", self._menu)
        self.hcv.bind("<Button-1>", self._hclick)
        self.hcv.bind("<Button-3>", self._hmenu)
        self.cv._wheel = self._wheel
        self.hcv._wheel = self._wheel
        self._job = None

    # ---- datos ------------------------------------------------------------
    def set_rows(self, rows, total=None, keep_state=True):
        self.rows = rows
        self.total = total
        if not keep_state:
            self.sort_col, self.sort_dir, self.filters = None, 0, {}
        self._apply()
        self._measure()
        self._layout()

    def set_columns(self, columns, group_header=None):
        self.columns = columns
        self.group_header = group_header
        self.hcv.configure(height=self.RH + 6 + (self.RH if group_header else 0))
        self.sort_col, self.sort_dir, self.filters = None, 0, {}
        self.base_widths = None

    def _text(self, ci, v):
        f = self.columns[ci].get("fmt")
        if f:
            try:
                return f(v)
            except Exception:
                return str(v)
        if isinstance(v, float):
            return fmt(v, 0)
        if isinstance(v, int):
            return f"{v:,}"
        return "" if v is None else str(v)

    def _apply(self):
        idx = list(range(len(self.rows)))
        for ci, allowed in self.filters.items():
            idx = [i for i in idx if self._text(ci, self.rows[i][ci]) in allowed]
        if self.sort_col is not None and self.sort_dir:
            ci = self.sort_col

            def key(i):
                v = self.rows[i][ci]
                if isinstance(v, (int, float)):
                    return (0, v, "")
                return (1, 0, str(v).lower())
            idx.sort(key=key, reverse=self.sort_dir < 0)
        self.view = idx
        if self.status:
            self.status(len(self.view), len(self.rows))

    def _measure(self):
        """Anchos de columna. Mide solo los textos candidatos (los más largos) y usa caché:
        cada medición de fuente es una llamada a Tk, que es lo más costoso de una tabla."""
        ws = []
        sample = self.rows[:400]
        for ci, col in enumerate(self.columns):
            w = _measure(self.bfont, col["title"]) + 30
            texts = {self._text(ci, r[ci]) for r in sample}
            if self.total:
                texts.add(self._text(ci, self.total[ci]))
            numeric = [t for t in texts if _NUMERIC.issuperset(t)]
            other = [t for t in texts if not _NUMERIC.issuperset(t)]
            if numeric:   # cifras de ancho fijo: basta la cantidad de caracteres (una medición en caché)
                w = max(w, _measure(self.bfont, "0" * len(max(numeric, key=len))) + 18)
            for t in sorted(other, key=len)[-4:]:
                w = max(w, _measure(self.font, t) + 18)
            w = max(px(self.min_col), min(w, px(col.get("max", 360))))
            if col.get("width"):
                w = px(col["width"])
            ws.append(w)
        self.base_widths = ws

    def _layout(self):
        if not self.columns:
            return
        if not getattr(self, "base_widths", None):
            self._measure()
        avail = max(self.cv.winfo_width(), 50)
        ws = list(self.base_widths)
        tot = sum(ws)
        if self.stretch and tot < avail:
            extra = avail - tot
            ws = [w + extra * w / tot for w in ws]
        self.widths = ws
        self.xs = [0]
        for w in ws:
            self.xs.append(self.xs[-1] + w)
        n = len(self.view) + (1 if self.total else 0)
        H = max(n * self.RH, 1)
        self.cv.configure(scrollregion=(0, 0, self.xs[-1], H))
        self.hcv.configure(scrollregion=(0, 0, self.xs[-1], int(self.hcv["height"])))
        self._draw_header()
        self._draw()

    # ---- dibujo -----------------------------------------------------------
    def _draw_header(self):
        cv = self.hcv
        cv.delete("all")
        gh = self.RH if self.group_header else 0
        h = int(cv["height"])
        cv.create_rectangle(0, 0, self.xs[-1] + 2000, h, fill=C["header"], outline="")
        if self.group_header:
            for text, a, b in self.group_header:
                x0, x1 = self.xs[a], self.xs[b + 1]
                cv.create_text((x0 + x1) / 2, gh / 2 + 2, text=text, font=F["bold"], fill=C["text"])
                cv.create_line(x0 + 8, gh, x1 - 8, gh, fill=C["border"])
        for ci, col in enumerate(self.columns):
            x0, x1 = self.xs[ci], self.xs[ci + 1]
            al = col.get("align", "w")
            filt = col.get("filter")
            right = x1 - (22 if filt else 8)
            if al == "e":
                cv.create_text(right, gh + (h - gh) / 2, text=col["title"], anchor="e", font=F["bold"], fill=C["text"])
            elif al == "center":
                cv.create_text((x0 + right) / 2, gh + (h - gh) / 2, text=col["title"], font=F["bold"], fill=C["text"])
            else:
                cv.create_text(x0 + 8, gh + (h - gh) / 2, text=col["title"], anchor="w", font=F["bold"], fill=C["text"])
            if self.sort_col == ci and self.sort_dir:
                cv.create_text(right + (4 if not filt else 2), gh + 7, text="▲" if self.sort_dir > 0 else "▼",
                               font=(F["small"][0], 6), fill=C["accent"], anchor="w")
            if filt:
                active = ci in self.filters
                draw_icon(cv, "filter", 12, C["accent"] if active else C["muted"], x1 - 18, gh + (h - gh) / 2 - 6)
            cv.create_line(x1, gh + 5, x1, h - 5, fill=C["border"])
        cv.create_line(0, h - 1, self.xs[-1] + 2000, h - 1, fill=C["border"])

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        if not self.widths:
            return
        top = cv.canvasy(0)
        hgt = cv.winfo_height()
        r0 = max(0, int(top // self.RH))
        r1 = min(len(self.view) + (1 if self.total else 0), int((top + hgt) // self.RH) + 2)
        left = cv.canvasx(0)
        width = cv.winfo_width()
        c0 = 0
        while c0 < len(self.columns) - 1 and self.xs[c0 + 1] < left:
            c0 += 1
        c1 = c0
        while c1 < len(self.columns) and self.xs[c1] < left + width:
            c1 += 1
        W = self.xs[-1]
        for k in range(r0, r1):
            y0 = k * self.RH
            is_total = k >= len(self.view)
            row = self.total if is_total else self.rows[self.view[k]]
            bg = C["total_bg"] if is_total else (C["select"] if self.sel == k else (C["alt"] if k % 2 else C["panel"]))
            cv.create_rectangle(0, y0, max(W, width + left), y0 + self.RH, fill=bg, outline="")
            for ci in range(c0, c1):
                x0, x1 = self.xs[ci], self.xs[ci + 1]
                v = row[ci]
                cbg = cfg = None
                if self.cell_style and not is_total:
                    st = self.cell_style(row, ci)
                    if st:
                        cbg, cfg = st
                if cbg:
                    cv.create_rectangle(x0, y0, x1, y0 + self.RH, fill=cbg, outline="")
                t = self._text(ci, v)
                al = self.columns[ci].get("align", "w")
                font = F["bold"] if is_total else F["base"]
                col = cfg or C["text"]
                if al == "e":
                    cv.create_text(x1 - 10, y0 + self.RH / 2, text=t, anchor="e", font=font, fill=col)
                elif al == "center":
                    cv.create_text((x0 + x1) / 2, y0 + self.RH / 2, text=t, font=font, fill=col)
                else:
                    cv.create_text(x0 + 8, y0 + self.RH / 2, text=t, anchor="w", font=font, fill=col)
        if not self.view and not self.total:
            cv.create_text(width / 2 + left, 30, text="Sin datos", fill=C["muted"], font=F["base"])

    def _on_configure(self, e):
        size = (e.width, e.height)
        if size == self._size:
            return
        width_changed = size[0] != self._size[0]
        self._size = size
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(15, self._layout if width_changed else self._redraw)

    def _schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(10, self._redraw)

    def _redraw(self):
        self._job = None
        self._draw()

    # ---- desplazamiento ---------------------------------------------------
    def _yview(self, *a):
        self.cv.yview(*a)
        self._draw()

    def _xview(self, *a):
        self.cv.xview(*a)
        self.hcv.xview(*a)
        self._draw()

    def _yset(self, a, b):
        self.vbar.set(a, b)

    def _xset(self, a, b):
        self.hbar.set(a, b)
        self.hcv.xview_moveto(a)

    def _wheel(self, delta, shift):
        if shift:
            self.cv.xview_scroll(int(-delta * 3), "units")
            self.hcv.xview_moveto(self.cv.xview()[0])
        else:
            if (len(self.view) + 1) * self.RH <= self.cv.winfo_height():
                return False
            self.cv.yview_scroll(int(-delta * 3), "units")
        self._draw()
        return True

    # ---- eventos ----------------------------------------------------------
    def _col_at(self, x):
        for ci in range(len(self.columns)):
            if self.xs[ci] <= x < self.xs[ci + 1]:
                return ci
        return None

    def _hclick(self, e):
        x = self.hcv.canvasx(e.x)
        ci = self._col_at(x)
        if ci is None:
            return
        if self.group_header and e.y < self.RH:
            return
        if self.columns[ci].get("filter") and x > self.xs[ci + 1] - 22:
            self._open_filter(ci, e)
            return
        if self.sort_col != ci:
            self.sort_col, self.sort_dir = ci, 1
        else:
            self.sort_dir = {1: -1, -1: 0, 0: 1}[self.sort_dir]
        self._apply()
        self._layout()

    def _open_filter(self, ci, e=None):
        vals = sorted({self._text(ci, r[ci]) for r in self.rows}, key=lambda s: _natkey(s))
        cur = self.filters.get(ci)
        anchor = _Anchor(self.hcv, self.xs[ci + 1] - 22 - self.hcv.canvasx(0), int(self.hcv["height"]))

        def apply(sel):
            if len(sel) == len(vals):
                self.filters.pop(ci, None)
            else:
                self.filters[ci] = set(sel)
            self._apply()
            self._layout()
        FilterPopup(anchor, self.columns[ci]["title"], vals, cur if cur is not None else set(vals), apply)

    def _hmenu(self, e):
        ci = self._col_at(self.hcv.canvasx(e.x))
        if ci is None:
            return
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Orden Ascendente", command=lambda: self._sort(ci, 1))
        m.add_command(label="Orden Descendente", command=lambda: self._sort(ci, -1))
        m.add_command(label="Orden Original", command=lambda: self._sort(None, 0))
        if self.columns[ci].get("filter"):
            m.add_separator()
            m.add_command(label="Filtrar…", command=lambda: self._open_filter(ci))
        if self.filters:
            m.add_command(label="Limpiar Filtros", command=self.clear_filters)
        m.tk_popup(e.x_root, e.y_root)

    def _sort(self, ci, d):
        self.sort_col, self.sort_dir = ci, d
        self._apply()
        self._layout()

    def clear_filters(self):
        self.filters = {}
        self._apply()
        self._layout()

    def _click(self, e):
        k = int(self.cv.canvasy(e.y) // self.RH)
        if 0 <= k < len(self.view):
            self.sel = k
            self._draw()
            if self.on_select:
                self.on_select(self.rows[self.view[k]])

    def _menu(self, e):
        self._click(e)
        m = tk.Menu(self, tearoff=0)
        if self.sel is not None:
            m.add_command(label="Copiar Selección", command=self.copy_selection)
        m.add_command(label="Copiar Tabla", command=self.copy_table)
        m.tk_popup(e.x_root, e.y_root)

    def to_tsv(self):
        lines = []
        if self.group_header:
            g = [""] * len(self.columns)
            for t, a, b in self.group_header:
                g[a] = t
            lines.append("\t".join(g))
        lines.append("\t".join(c["title"] for c in self.columns))
        for i in self.view:
            lines.append("\t".join(_raw(v) for v in self.rows[i]))
        if self.total:
            lines.append("\t".join(_raw(v) for v in self.total))
        return "\n".join(lines)

    def copy_table(self):
        self.clipboard_clear()
        self.clipboard_append(self.to_tsv())
        _notify(self, "Tabla copiada al portapapeles")

    def copy_selection(self):
        if self.sel is None or self.sel >= len(self.view):
            return
        r = self.rows[self.view[self.sel]]
        self.clipboard_clear()
        self.clipboard_append("\t".join(c["title"] for c in self.columns) + "\n" + "\t".join(_raw(v) for v in r))
        _notify(self, "Selección copiada al portapapeles")


_NUMERIC = set("0123456789,.-+−% ")


def _measure(font, text):
    return measure(font, text)


class _Anchor:
    """Ancla mínima para ubicar el filtro emergente bajo un punto del encabezado."""

    def __init__(self, cv, x, h):
        self.cv, self.x, self.h = cv, x, h

    def winfo_rootx(self):
        return self.cv.winfo_rootx() + int(self.x)

    def winfo_rooty(self):
        return self.cv.winfo_rooty()

    def winfo_height(self):
        return self.h

    def __getattr__(self, k):
        return getattr(self.cv, k)


def _raw(v):
    if isinstance(v, float):
        return repr(round(v, 6))
    return "" if v is None else str(v)


def _natkey(s):
    import re
    try:
        return (0, float(s.replace(",", "")), "")
    except ValueError:
        return (1, 0, [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)])


def _notify(w, msg):
    top = w.winfo_toplevel()
    fn = getattr(top, "notify", None)
    if fn:
        fn(msg)
