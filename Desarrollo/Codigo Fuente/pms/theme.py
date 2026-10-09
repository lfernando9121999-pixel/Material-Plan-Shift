"""Tema visual (paleta Primer, como SimA) en modo claro y oscuro."""
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

LIGHT = {
    "bg": "#ECEFF3", "panel": "#FFFFFF", "alt": "#F5F7F9", "border": "#D6DCE2", "text": "#1F2328",
    "muted": "#5F6873", "accent": "#0969DA", "accent_soft": "#DDF4FF", "tab_line": "#FD8C73",
    "primary": "#1F883D", "primary_hover": "#1A7F37", "required": "#A4161A", "hover": "#EEF1F4",
    "select": "#DDEBFB", "disabled": "#A8B0B9", "inactive_bg": "#F1F3F5", "ok_bg": "#DAFBE1", "ok_fg": "#1A7F37",
    "bad_bg": "#FFEBE9", "bad_fg": "#CF222E", "warn": "#9A6700", "grid": "#E7EBEF", "header": "#F5F7F9",
    "brand_bg": "#0B2545", "input": "#FFFFFF", "total_bg": "#EEF1F4", "green_cell": "#E6F6EA", "red_cell": "#FDECEC",
}
DARK = {
    "bg": "#010409", "panel": "#0D1117", "alt": "#161B22", "border": "#30363D", "text": "#E6EDF3",
    "muted": "#7D8590", "accent": "#2F81F7", "accent_soft": "#132F52", "tab_line": "#F78166",
    "primary": "#238636", "primary_hover": "#2EA043", "required": "#F85149", "hover": "#1C232C",
    "select": "#1B3150", "disabled": "#4A525B", "inactive_bg": "#11161C", "ok_bg": "#12301C", "ok_fg": "#3FB950",
    "bad_bg": "#3A1518", "bad_fg": "#F85149", "warn": "#D29922", "grid": "#21262D", "header": "#161B22",
    "brand_bg": "#0B2545", "input": "#0D1117", "total_bg": "#1C232C", "green_cell": "#12301C", "red_cell": "#3A1518",
}

SERIES = ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F",
          "#BCBD22", "#17BECF", "#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#B07AA1", "#76B7B2"]
PLAN_COLOR = "#8C8C8C"
SCEN_COLOR = "#2CA02C"
MINERAL_COLOR = "#4472C4"
DESMONTE_COLOR = "#ED7D31"
TYPE_COLORS = {"Mineral": MINERAL_COLOR, "Desmonte": DESMONTE_COLOR}

C = dict(LIGHT)
DARK_MODE = False
F = {}


def family():
    fams = set(tkfont.families())
    for f in ("Segoe UI", "Segoe UI Variable Text", "Helvetica Neue", "DejaVu Sans", "Arial"):
        if f in fams:
            return f
    return "TkDefaultFont"


def apply(root, dark=False):
    global DARK_MODE
    DARK_MODE = dark
    C.clear()
    C.update(DARK if dark else LIGHT)
    fam = family()
    F.update({
        "base": (fam, 9), "bold": (fam, 9, "bold"), "small": (fam, 8), "title": (fam, 10, "bold"),
        "h1": (fam, 11, "bold"), "kpi": (fam, 13, "bold"), "brand": (fam, 11, "bold"), "menu": (fam, 9),
        "tab": (fam, 10), "tab_on": (fam, 10, "bold"), "section": (fam, 10, "bold"),
    })
    root.configure(bg=C["bg"])
    root.option_add("*Font", F["base"])
    root.option_add("*Menu.background", C["panel"])
    root.option_add("*Menu.foreground", C["text"])
    root.option_add("*Menu.activeBackground", C["select"])
    root.option_add("*Menu.activeForeground", C["text"])
    root.option_add("*Menu.relief", "flat")
    root.option_add("*Listbox.background", C["panel"])
    root.option_add("*Listbox.foreground", C["text"])
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=C["panel"], foreground=C["text"], fieldbackground=C["input"],
                 bordercolor=C["border"], lightcolor=C["border"], darkcolor=C["border"], font=F["base"],
                 troughcolor=C["alt"], arrowcolor=C["muted"], focuscolor=C["accent"])
    st.configure("TCombobox", fieldbackground=C["input"], background=C["panel"], foreground=C["text"],
                 arrowcolor=C["muted"], padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", C["input"]), ("disabled", C["alt"])],
           foreground=[("disabled", C["disabled"])], selectbackground=[("readonly", C["input"])],
           selectforeground=[("readonly", C["text"])])
    root.option_add("*TCombobox*Listbox.background", C["panel"])
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", C["text"])
    st.configure("TEntry", fieldbackground=C["input"], foreground=C["text"], padding=3, insertcolor=C["text"])
    st.map("TEntry", fieldbackground=[("disabled", C["alt"])], foreground=[("disabled", C["disabled"])])
    st.configure("TSpinbox", fieldbackground=C["input"], foreground=C["text"], padding=3, arrowcolor=C["muted"],
                 insertcolor=C["text"])
    st.map("TSpinbox", fieldbackground=[("disabled", C["alt"])], foreground=[("disabled", C["disabled"])])
    st.configure("Vertical.TScrollbar", background=C["alt"], troughcolor=C["panel"], bordercolor=C["panel"],
                 arrowcolor=C["muted"], gripcount=0, relief="flat")
    st.configure("Horizontal.TScrollbar", background=C["alt"], troughcolor=C["panel"], bordercolor=C["panel"],
                 arrowcolor=C["muted"], gripcount=0, relief="flat")
    st.map("Vertical.TScrollbar", background=[("active", C["border"])])
    st.map("Horizontal.TScrollbar", background=[("active", C["border"])])
    st.configure("TProgressbar", background=C["accent"], troughcolor=C["alt"], bordercolor=C["border"],
                 lightcolor=C["accent"], darkcolor=C["accent"])
    if sys.platform == "win32":
        _dark_titlebar(root, dark)


def _dark_titlebar(win, dark):
    """Barra de título oscura en Windows 10/11 (si está disponible)."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:
        pass


def titlebar(win):
    if sys.platform == "win32":
        _dark_titlebar(win, DARK_MODE)


def blend(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
