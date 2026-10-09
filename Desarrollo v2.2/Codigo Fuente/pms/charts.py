"""Gráficos interactivos dibujados sobre Canvas (sin dependencias externas).

Todos los gráficos muestran información al pasar el mouse y ofrecen, con clic
derecho, «Copiar Datos de Gráfico» (texto tabulado para Excel).
"""
from __future__ import annotations

import math
import tkinter as tk

from .theme import C, F, measure, px, shared_font
from .widgets import fmt


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    raw = span / max(1, n)
    mag = 10 ** math.floor(math.log10(raw))
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    t0 = math.floor(lo / step) * step
    t1 = math.ceil(hi / step) * step
    ticks = []
    v = t0
    while v <= t1 + step * 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def compact(v, unit="t"):
    a = abs(v)
    if unit == "Mt":
        return f"{v:,.1f}" if a < 100 else f"{v:,.0f}"
    if a >= 1e6:
        return f"{v / 1e6:,.1f} Mt"
    if a >= 1e3:
        return f"{v / 1e3:,.0f} kt"
    if a == 0:
        return "0"
    return f"{v:,.0f} t"


class Chart(tk.Canvas):
    ML, MR, MT, MB = 70, 18, 14, 46

    def __init__(self, parent, height=320, yfmt=None, unit="t", xlabel="", ylabel="", legend=True):
        super().__init__(parent, height=px(height), bg=C["panel"], highlightthickness=0)
        self.ML, self.MR, self.MT, self.MB = px(self.ML), px(self.MR), px(self.MT), px(self.MB)
        self.yfmt = yfmt or (lambda v: compact(v, unit))
        self.unit = unit
        self.xlabel, self.ylabel = xlabel, ylabel
        self.legend = legend
        self.cats = []
        self._job = None
        self.font = shared_font(F["small"], self)
        self._drawn = None          # tamaño con el que se dibujó por última vez
        self._dirty = True
        self.bind("<Configure>", self._on_configure)
        self.bind("<Map>", lambda e: self._dirty and self._schedule(10))
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self.delete("hover"))
        self.bind("<Button-3>", self._menu)
        self.hidden = set()
        self.legend_items = []

    def _on_configure(self, e):
        # mover la ventana o volver a mostrar la vista no cambia el tamaño: no se redibuja
        if (e.width, e.height) != self._drawn:
            self._schedule(90)

    def _schedule(self, delay=15):
        """Programa un redibujo. Cambios de datos: casi inmediato; cambios de tamaño: agrupados."""
        if delay == 15:
            self._dirty = True
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(delay, self._redraw)

    def _redraw(self):
        self._job = None
        if not self.winfo_ismapped():
            self._dirty = True          # se dibuja al mostrarse
            return
        size = (self.winfo_width(), self.winfo_height())
        if not self._dirty and size == self._drawn:
            return
        self._dirty = False
        self._drawn = size
        self.delete("all")
        try:
            self.draw()
        except tk.TclError:
            pass

    def refresh(self):
        self._schedule()

    def plot_box(self):
        w, h = self.winfo_width(), self.winfo_height()
        mb = self.MB + (18 if self.xlabel else 0) - (0 if self.legend else 20)
        ml = self.ML + (16 if self.ylabel else 0)
        return ml, self.MT, max(ml + 10, w - self.MR), max(self.MT + 10, h - mb)

    def axes_y(self, lo, hi, box, ticks=None):
        x0, y0, x1, y1 = box
        ticks = ticks or nice_ticks(lo, hi)
        lo, hi = ticks[0], ticks[-1]
        for t in ticks:
            y = y1 - (t - lo) / (hi - lo or 1) * (y1 - y0)
            self.create_line(x0, y, x1, y, fill=C["grid"])
            self.create_text(x0 - 6, y, text=self.yfmt(t), anchor="e", fill=C["muted"], font=F["small"])
        if self.ylabel:
            self.create_text(12, (y0 + y1) / 2, text=self.ylabel, angle=90, fill=C["muted"], font=F["small"])
        return lo, hi

    def x_labels(self, box, n, label_of, xpos):
        x0, y0, x1, y1 = box
        if n == 0:
            return
        maxw = max(measure(self.font, str(label_of(i))) for i in range(n)) + 8
        step = max(1, math.ceil(maxw / max(1.0, (x1 - x0) / n)))
        for i in range(0, n, step):
            self.create_text(xpos(i), y1 + 10, text=str(label_of(i)), fill=C["muted"], font=F["small"])
        if self.xlabel:
            self.create_text((x0 + x1) / 2, y1 + 26, text=self.xlabel, fill=C["muted"], font=F["small"])

    def draw_legend(self, items):
        """items: [(nombre, color, tipo)] tipo = line | box."""
        self.legend_items = []
        if not self.legend or not items:
            return
        w, h = self.winfo_width(), self.winfo_height()
        widths = [measure(self.font, n) + 30 for n, _, _ in items]
        rows, cur, cw = [], [], 0
        for it, iw in zip(items, widths):
            if cur and cw + iw > w - 20:
                rows.append((cur, cw))
                cur, cw = [], 0
            cur.append((it, iw))
            cw += iw
        if cur:
            rows.append((cur, cw))
        y = h - 12 - 16 * (len(rows) - 1)
        for row, rw in rows:
            x = (w - rw) / 2
            for (name, color, kind), iw in row:
                off = name in self.hidden
                col = C["disabled"] if off else color
                if kind == "line":
                    self.create_line(x, y, x + 16, y, fill=col, width=2.5)
                elif kind == "dash":
                    self.create_line(x, y, x + 16, y, fill=col, width=1.2, dash=(4, 3))
                else:
                    self.create_rectangle(x + 3, y - 5, x + 13, y + 5, fill=col, outline="")
                self.create_text(x + 20, y, text=name, anchor="w", fill=C["disabled"] if off else C["muted"],
                                 font=F["small"])
                self.legend_items.append((x, y - 8, x + iw, y + 8, name))
                x += iw
            y += 16

    def tooltip(self, x, y, title, lines):
        """lines: [(color|None, texto, valor)]"""
        self.delete("hover")
        fb = (F["small"][0], F["small"][1], "bold")
        wt = max([measure(self.font, title)] + [measure(self.font, t) + measure(self.font, v) + 40 for _, t, v in lines])
        hgt = 22 + 16 * len(lines)
        W, H = self.winfo_width(), self.winfo_height()
        bx = x + 14 if x + 14 + wt + 16 < W else x - wt - 30
        by = min(max(4, y - hgt / 2), H - hgt - 4)
        self.create_rectangle(bx + 2, by + 2, bx + wt + 18, by + hgt + 2, fill=C["border"], outline="", tags="hover")
        self.create_rectangle(bx, by, bx + wt + 16, by + hgt, fill=C["panel"], outline=C["border"], tags="hover")
        self.create_text(bx + 8, by + 11, text=title, anchor="w", font=fb, fill=C["text"], tags="hover")
        yy = by + 27
        for col, t, v in lines:
            if col:
                self.create_rectangle(bx + 8, yy - 4, bx + 16, yy + 4, fill=col, outline="", tags="hover")
            self.create_text(bx + (20 if col else 8), yy, text=t, anchor="w", font=F["small"], fill=C["text"],
                             tags="hover")
            self.create_text(bx + wt + 8, yy, text=v, anchor="e", font=fb, fill=C["text"], tags="hover")
            yy += 16

    def _legend_hit(self, e):
        for x0, y0, x1, y1, name in self.legend_items:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                return name
        return None

    def _motion(self, e):
        pass

    def data_rows(self):
        return []

    def _menu(self, e):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Copiar Datos de Gráfico", command=self.copy_data)
        m.tk_popup(e.x_root, e.y_root)

    def copy_data(self):
        rows = self.data_rows()
        txt = "\n".join("\t".join("" if v is None else (repr(round(v, 6)) if isinstance(v, float) else str(v))
                                  for v in r) for r in rows)
        self.clipboard_clear()
        self.clipboard_append(txt)
        fn = getattr(self.winfo_toplevel(), "notify", None)
        if fn:
            fn("Datos del gráfico copiados al portapapeles")


# ---------------------------------------------------------------------------
class LineChart(Chart):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.series = []
        self.hlines = []
        self.bind("<ButtonRelease-1>", self._click)

    def set_data(self, cats, series, hlines=()):
        """series: [{"name","values","color","width","dash"}]; hlines: [{"value","color","dash","label"}]"""
        self.cats, self.series, self.hlines = list(cats), list(series), list(hlines)
        self._schedule()

    def _visible(self):
        return [s for s in self.series if s["name"] not in self.hidden]

    def draw(self):
        box = self.plot_box()
        x0, y0, x1, y1 = box
        vals = [v for s in self._visible() for v in s["values"] if v is not None]
        vals += [h["value"] for h in self.hlines]
        if not vals or not self.cats:
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="Sin datos", fill=C["muted"])
            return
        lo, hi = min(0, min(vals)), max(vals)
        fixed = getattr(self, "fixed", None)
        if fixed:
            lo, hi = self.axes_y(fixed[0], fixed[1], box, nice_ticks(fixed[0], fixed[1]))
        else:
            lo, hi = self.axes_y(lo, hi * 1.05 if hi > 0 else 1, box)
        n = len(self.cats)
        self._xpos = lambda i: x0 + (i / (n - 1) if n > 1 else 0.5) * (x1 - x0)
        self._ypos = lambda v: y1 - (v - lo) / (hi - lo or 1) * (y1 - y0)
        self.create_line(x0, y1, x1, y1, fill=C["border"])
        for h in self.hlines:
            y = self._ypos(h["value"])
            self.create_line(x0, y, x1, y, fill=h.get("color", C["muted"]), dash=h.get("dash", (4, 3)), width=1)
        for s in self._visible():
            pts = []
            for i, v in enumerate(s["values"]):
                if v is None:
                    continue
                pts += [self._xpos(i), self._ypos(v)]
            if len(pts) >= 4:
                self.create_line(*pts, fill=s["color"], width=s.get("width", 2), dash=s.get("dash"),
                                 smooth=s.get("smooth", False))
            elif len(pts) == 2:
                self.create_oval(pts[0] - 2, pts[1] - 2, pts[0] + 2, pts[1] + 2, fill=s["color"], outline="")
        self.x_labels(box, n, lambda i: self.cats[i], self._xpos)
        self.draw_legend([(s["name"], s["color"], "line") for s in self.series] +
                         [(h["label"], h.get("color", C["muted"]), "dash") for h in self.hlines if h.get("label")])

    def _motion(self, e):
        if not self.cats or not hasattr(self, "_xpos"):
            return
        x0, y0, x1, y1 = self.plot_box()
        self.delete("hover")
        if not (x0 - 5 <= e.x <= x1 + 5 and y0 <= e.y <= y1):
            return
        n = len(self.cats)
        i = int(round((e.x - x0) / (x1 - x0 or 1) * (n - 1))) if n > 1 else 0
        i = max(0, min(n - 1, i))
        x = self._xpos(i)
        self.create_line(x, y0, x, y1, fill=C["muted"], dash=(2, 2), tags="hover")
        lines = []
        for s in self._visible():
            v = s["values"][i] if i < len(s["values"]) else None
            if v is None:
                continue
            y = self._ypos(v)
            self.create_oval(x - 3.5, y - 3.5, x + 3.5, y + 3.5, fill=s["color"], outline=C["panel"], tags="hover")
            lines.append((s["color"], s["name"], fmt(v)))
        self.tooltip(e.x, e.y, str(self.cats[i]), lines)

    def _click(self, e):
        name = self._legend_hit(e)
        if name:
            self.hidden ^= {name}
            self._schedule()

    def data_rows(self):
        rows = [[""] + [s["name"] for s in self.series]]
        for i, c in enumerate(self.cats):
            rows.append([c] + [s["values"][i] for s in self.series])
        return rows


# ---------------------------------------------------------------------------
class BarChart(Chart):
    def __init__(self, parent, horizontal=False, stacked=False, **kw):
        super().__init__(parent, **kw)
        self.horizontal, self.stacked = horizontal, stacked
        self.series = []
        self.bind("<ButtonRelease-1>", self._click)
        if horizontal:
            self.ML = px(96)

    def set_data(self, cats, series, hlines=()):
        self.cats, self.series, self.hlines = list(cats), list(series), list(hlines)
        if self.horizontal and self.cats:
            self.ML = min(220, max(60, max(measure(self.font, str(c)) for c in self.cats) + 16))
        self._schedule()

    def _visible(self):
        return [s for s in self.series if s["name"] not in self.hidden]

    def draw(self):
        box = self.plot_box()
        x0, y0, x1, y1 = box
        ser = self._visible()
        n = len(self.cats)
        if not n or not ser:
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="Sin datos", fill=C["muted"])
            self.draw_legend([(s["name"], s["color"], "box") for s in self.series])
            return
        if self.stacked:
            tops = [sum(max(0, s["values"][i] or 0) for s in ser) for i in range(n)]
            vmax = max(tops + [h["value"] for h in getattr(self, "hlines", [])] + [0])
        else:
            vmax = max([v or 0 for s in ser for v in s["values"]] + [0])
        ticks = nice_ticks(0, vmax * 1.04 if vmax > 0 else 1)
        lo, hi = ticks[0], ticks[-1]
        self._geom = []
        if self.horizontal:
            for t in ticks:
                x = x0 + (t - lo) / (hi - lo) * (x1 - x0)
                self.create_line(x, y0, x, y1, fill=C["grid"])
                self.create_text(x, y1 + 10, text=self.yfmt(t), fill=C["muted"], font=F["small"])
            band = (y1 - y0) / n
            for i, c in enumerate(self.cats):
                yc = y0 + band * (i + 0.5)
                self.create_text(x0 - 6, yc, text=str(c), anchor="e", fill=C["text"], font=F["small"])
                inner = band * 0.72
                bh = inner / (1 if self.stacked else len(ser))
                acc = 0.0
                for k, s in enumerate(ser):
                    v = s["values"][i] or 0
                    if self.stacked:
                        xa = x0 + (acc - lo) / (hi - lo) * (x1 - x0)
                        acc += max(0, v)
                        xb = x0 + (acc - lo) / (hi - lo) * (x1 - x0)
                        ya = yc - inner / 2
                    else:
                        xa = x0
                        xb = x0 + (max(0, v) - lo) / (hi - lo) * (x1 - x0)
                        ya = yc - inner / 2 + k * bh
                    self.create_rectangle(xa, ya, xb, ya + bh - (0 if self.stacked else 1.5), fill=s["color"], outline="")
                self._geom.append((x0, yc - band / 2, x1, yc + band / 2, i))
        else:
            lo, hi = self.axes_y(0, vmax * 1.04 if vmax > 0 else 1, box, ticks)
            band = (x1 - x0) / n
            for i in range(n):
                xc = x0 + band * (i + 0.5)
                inner = band * (0.72 if n > 1 else 0.4)
                bw = inner / (1 if self.stacked else len(ser))
                acc = 0.0
                for k, s in enumerate(ser):
                    v = s["values"][i] or 0
                    if self.stacked:
                        ya = y1 - (acc - lo) / (hi - lo) * (y1 - y0)
                        acc += max(0, v)
                        yb = y1 - (acc - lo) / (hi - lo) * (y1 - y0)
                        xa = xc - inner / 2
                    else:
                        ya = y1
                        yb = y1 - (max(0, v) - lo) / (hi - lo) * (y1 - y0)
                        xa = xc - inner / 2 + k * bw
                    if abs(ya - yb) >= 0.3:
                        self.create_rectangle(xa, yb, xa + bw - (0 if self.stacked else 1.5), ya, fill=s["color"],
                                              outline="")
                self._geom.append((xc - band / 2, y0, xc + band / 2, y1, i))
            for h in getattr(self, "hlines", []):
                y = y1 - (h["value"] - lo) / (hi - lo) * (y1 - y0)
                self.create_line(x0, y, x1, y, fill=h.get("color", C["muted"]), dash=h.get("dash", (4, 3)))
            self.create_line(x0, y1, x1, y1, fill=C["border"])
            self.x_labels(box, n, lambda i: self.cats[i], lambda i: x0 + band * (i + 0.5))
        self.draw_legend([(s["name"], s["color"], "box") for s in self.series])

    def _motion(self, e):
        self.delete("hover")
        for a, b, c, d, i in getattr(self, "_geom", []):
            if a <= e.x <= c and b <= e.y <= d:
                self.create_rectangle(a, b, c, d, fill="", outline=C["accent"], dash=(2, 2), tags="hover")
                lines = [(s["color"], s["name"], fmt(s["values"][i] or 0)) for s in self._visible()]
                if self.stacked and len(lines) > 1:
                    lines = lines[::-1]
                    lines.append((None, "Total", fmt(sum(s["values"][i] or 0 for s in self._visible()))))
                self.tooltip(e.x, e.y, str(self.cats[i]), lines)
                return

    def _click(self, e):
        name = self._legend_hit(e)
        if name:
            self.hidden ^= {name}
            self._schedule()

    def data_rows(self):
        rows = [[""] + [s["name"] for s in self.series]]
        for i, c in enumerate(self.cats):
            rows.append([c] + [s["values"][i] for s in self.series])
        return rows


# ---------------------------------------------------------------------------
class SegmentChart(Chart):
    """Barras apiladas por segmentos (cada registro de cada polígono)."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.bars = []
        self.legend_def = []

    def set_data(self, cats, bars, legend_def, top_first=True):
        """bars[i] = [(valor, color, info_dict)] en el orden del plan (primer registro primero)."""
        self.cats, self.bars, self.legend_def, self.top_first = list(cats), bars, legend_def, top_first
        self._schedule()

    def draw(self):
        box = self.plot_box()
        x0, y0, x1, y1 = box
        n = len(self.cats)
        if not n:
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="Sin datos", fill=C["muted"])
            return
        tops = [sum(v for v, _, _ in b) for b in self.bars]
        lo, hi = self.axes_y(0, max(tops + [0]) * 1.04 or 1, box)
        band = (x1 - x0) / n
        bw = band * (0.55 if n > 8 else 0.4)
        self._geom = []
        sep = C["panel"]
        for i, segs in enumerate(self.bars):
            xc = x0 + band * (i + 0.5)
            order = list(reversed(segs)) if self.top_first else list(segs)
            acc = 0.0
            geo = []
            run = None                      # tramos contiguos del mismo color = un solo rectángulo
            for v, col, info in order:
                if v <= 0:
                    continue
                ya = y1 - (acc - lo) / (hi - lo) * (y1 - y0)
                acc += v
                yb = y1 - (acc - lo) / (hi - lo) * (y1 - y0)
                geo.append((yb, ya, info, col))
                if run and run[2] == col:
                    run[0] = yb
                else:
                    if run:
                        self.create_rectangle(xc - bw / 2, run[0], xc + bw / 2, run[1], fill=run[2], outline="")
                    run = [yb, ya, col]
            if run:
                self.create_rectangle(xc - bw / 2, run[0], xc + bw / 2, run[1], fill=run[2], outline="")
            # separador sutil entre polígonos (solo si hay espacio visible)
            last = None
            for yb, ya, info, col in geo:
                if info.get("poly_start"):
                    yline = yb if self.top_first else ya
                    if last is None or abs(yline - last) >= 2.5:
                        self.create_line(xc - bw / 2, yline, xc + bw / 2, yline, fill=sep, width=0.6)
                        last = yline
            self._geom.append((xc - band / 2, xc + band / 2, geo, i, tops[i]))
        self.create_line(x0, y1, x1, y1, fill=C["border"])
        self.x_labels(box, n, lambda i: self.cats[i], lambda i: x0 + band * (i + 0.5))
        self.draw_legend(self.legend_def)

    def _motion(self, e):
        self.delete("hover")
        for a, b, geo, i, top in getattr(self, "_geom", []):
            if a <= e.x <= b:
                for yb, ya, info, col in geo:
                    if yb - 1 <= e.y <= ya + 1:
                        bw = (b - a) * 0.55
                        xc = (a + b) / 2
                        self.create_rectangle(xc - bw / 2, yb, xc + bw / 2, ya, outline=C["text"], width=1.5,
                                              tags="hover")
                        lines = [(col, "Material", info.get("material", "")),
                                 (None, "Polígono", info.get("poly", "")),
                                 (None, "# Sec", info.get("sec", "")),
                                 (None, "Orden en polígono", info.get("pos", "")),
                                 (None, "Destino principal", info.get("dest", "")),
                                 (None, "Tonelaje (t)", fmt(info.get("t", 0)))]
                        self.tooltip(e.x, e.y, f"{self.cats[i]} · total {fmt(top / 1e6 if self.unit == 'Mt' else top, 2 if self.unit == 'Mt' else 0)} {self.unit}", lines)
                        return
                return

    def data_rows(self):
        rows = [["Semana", "Orden", "Polígono", "# Sec", "Material", "Tipo", "Destino principal", "Tonelaje (t)"]]
        for c, segs in zip(self.cats, self.bars):
            for v, col, info in segs:
                rows.append([c, info.get("pos"), info.get("poly"), info.get("sec"), info.get("material"),
                             info.get("tipo"), info.get("dest", ""), info.get("t")])
        return rows


# ---------------------------------------------------------------------------
class Sparkline(tk.Canvas):
    def __init__(self, parent, width=150, height=34, color=None, bg=None):
        super().__init__(parent, width=px(width), height=px(height), bg=bg or C["panel"], highlightthickness=0)
        self.color = color or C["muted"]
        self.values = []
        self.mark = None
        self.avg = False
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, values, mark=None, avg=False):
        self.values, self.mark, self.avg = list(values), mark, avg
        self.draw()

    def draw(self):
        self.delete("all")
        v = self.values
        if not v:
            return
        w, h = self.winfo_width(), self.winfo_height()
        hi = max(v) or 1
        n = len(v)
        bw = w / n
        for i, x in enumerate(v):
            bh = (h - 2) * (x / hi)
            col = self.color if i == self.mark else C["disabled"]
            self.create_rectangle(i * bw + 0.5, h - bh, (i + 1) * bw - 0.5, h, fill=col, outline="")
        if self.avg:
            y = h - (h - 2) * (sum(v) / n / hi)
            self.create_line(0, y, w, y, fill=self.color, dash=(3, 2))
