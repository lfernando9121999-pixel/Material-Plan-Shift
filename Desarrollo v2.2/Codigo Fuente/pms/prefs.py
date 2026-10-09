"""Preferencias del usuario (tema, recientes, carpetas, ventana y memoria de configuración)."""
import json
import os
import sys

from . import APP_NAME


def folder():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    p = os.path.join(base, APP_NAME)
    os.makedirs(p, exist_ok=True)
    return p


def desktop():
    home = os.path.expanduser("~")
    for c in (os.path.join(home, "Desktop"), os.path.join(home, "Escritorio"),
              os.path.join(home, "OneDrive", "Desktop"), os.path.join(home, "OneDrive", "Escritorio")):
        if os.path.isdir(c):
            return c
    return home


class Prefs:
    def __init__(self):
        self.path = os.path.join(folder(), "preferencias.json")
        self.data = {"dark": False, "recent": [], "last_dir": "", "last_xlsx_dir": "", "geometry": "",
                     "zoomed": False, "panel_pinned": True, "memory": {}}
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception:
            pass

    def get(self, k, d=None):
        return self.data.get(k, d)

    def set(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def add_recent(self, path):
        r = [p for p in self.data.get("recent", []) if os.path.normcase(p) != os.path.normcase(path)]
        self.data["recent"] = [path] + r[:9]
        self.save()

    def recent(self):
        return [p for p in self.data.get("recent", []) if os.path.exists(p)]

    def remember_config(self, cfg):
        """Memoria de la última clasificación (destinos/materiales) para casos nuevos."""
        mem = self.data.setdefault("memory", {})
        mem.setdefault("destinos", {}).update({k: v for k, v in cfg["destinos"].items() if v.get("tipo") != "N/A"})
        mem.setdefault("materiales", {}).update({k: v for k, v in cfg["materiales"].items() if v != "N/A"})
        self.save()
