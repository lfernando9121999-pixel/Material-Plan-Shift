"""Configuración de prueba común para las pruebas internas (no forma parte del programa)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Codigo Fuente")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from pms import config as C  # noqa: E402



def _find_input():
    """Excel de trabajo: variable PMS_INPUT o el primer .xlsx de la carpeta de fundamentos (excepto Graphs)."""
    env = os.environ.get("PMS_INPUT")
    if env:
        return env
    import glob
    folder = os.path.join(os.path.dirname(os.path.dirname(HERE)), "Fund. Plan Material Shift GIT")
    files = [f for f in sorted(glob.glob(os.path.join(folder, "*.xlsx"))) if "graphs" not in os.path.basename(f).lower()]
    return files[0] if files else os.path.join(folder, "no_encontrado.xlsx")


INPUT = _find_input()


def base_config(plan, experimento="convencional", modo="fijo", gran="semanal", **ex):
    cfg = C.new_config()
    cfg["general"].update({"archivo": INPUT, "hoja": plan.sheet, "nombre": "Prueba", "descripcion": "Prueba interna"})
    for m in plan.mat_names:
        cfg["materiales"][m] = "Mineral" if m.startswith("M") else ("Desmonte" if m.startswith("W") else "N/A")
    roles = {"Ore1": ("Mineral", "Receptor"), "Stk3_Ore1": ("Mineral", "Donante"), "yan_bl_v": ("Mineral", "Donante"),
             "Chw2a_1": ("Desmonte", "Receptor"), "Chw2a_2": ("Desmonte", "Receptor")}
    for d in ("DiqueN_2", "E10_5", "E10_6", "Inpit_F12", "Inpit_F13", "N3_7"):
        roles[d] = ("Desmonte", "Donante")
    C.ensure_plan_defaults(plan, cfg)
    for d in list(cfg["destinos"]):
        t, r = roles.get(d, ("N/A", "Donante"))
        cfg["destinos"][d] = {"tipo": t, "rol": r}
    cfg["circuitos"]["Desmonte"]["semanal"] = {"min": 1.25, "prom": 1.30, "max": 1.35}
    cfg["circuitos"]["Desmonte"]["diario"] = {"min": 0.16, "prom": 0.19, "max": 0.22}
    cfg["circuitos"]["Mineral"]["semanal"] = {"min": 0.95, "prom": 1.00, "max": 1.05}
    cfg["circuitos"]["Mineral"]["diario"] = {"min": 0.12, "prom": 0.143, "max": 0.17}
    C.refresh_circuits(plan, cfg)
    for c in C.CIRCUITS:
        cfg["circuitos"][c]["modo"] = modo
        cfg["circuitos"][c]["granularidad"] = gran
    cfg["experimento"]["tipo"] = experimento
    cfg["experimento"].update(ex)
    return cfg
