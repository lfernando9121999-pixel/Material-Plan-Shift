"""Configuración del escenario y archivo de proyecto .pmsx.

Un .pmsx es un ZIP con:
  escenario.json   inputs (configuración completa)
  resultados.json  resumen de la última corrida (opcional)
  resultados.npz   arreglos de la plan base y del resultado (opcional)
"""
from __future__ import annotations

import copy
import io
import json
import math
import zipfile

import numpy as np

from . import APP_NAME, VERSION

CIRCUITS = ("Mineral", "Desmonte")
TIPOS = ("Mineral", "Desmonte", "N/A")
ROLES = ("Receptor", "Donante")
EXPERIMENTS = {
    "convencional": "1. Convencional",
    "reordenamiento": "2. Reordenamiento de Filas",
    "aleatoria": "3. Asignación Balanceada Aleatoria",
    "integral": "4. Optimización Integral",
}
APERTURAS = {"estricto": "Estricto", "moderado": "Moderado", "flexible": "Flexible"}
PRIO_BLOCKS = (("fases", "1. Fases"), ("donantes", "2. Donantes"), ("materiales", "3. Materiales"))


def circuit_default():
    return {
        "activo": True,
        "matriz": {},                      # destino -> {material: bool}; ausente = permitido
        "modo": "fijo",                    # fijo | balanceado
        "granularidad": "semanal",         # semanal | diario
        "semanal": {"min": None, "prom": None, "max": None},   # Mt/semana por receptor
        "diario": {"min": None, "prom": None, "max": None},    # Mt/día por receptor
        "prioridad": {},                   # receptor -> {bloque: {"activo": bool, "items": [[nombre, bool]]}}
    }


def new_config():
    return {
        "tipo": APP_NAME + " - Escenario",
        "version": 1,
        "general": {"archivo": "", "hoja": "", "nombre": "", "descripcion": "", "anio": None},
        "fases": {},
        "destinos": {},
        "materiales": {},
        "circuitos": {c: circuit_default() for c in CIRCUITS},
        "experimento": {"tipo": "convencional", "pct_mineral": 50.0, "base_pct": "elegibles",
                        "apertura": "moderado", "semilla": 1},
    }


def merge_defaults(cfg):
    base = new_config()

    def merge(dst, src):
        for k, v in src.items():
            if k in dst and isinstance(dst[k], dict) and isinstance(v, dict) and k not in (
                    "fases", "destinos", "materiales", "matriz", "prioridad"):
                merge(dst[k], v)
            else:
                dst[k] = v
    merge(base, cfg or {})
    for c in CIRCUITS:
        base["circuitos"].setdefault(c, circuit_default())
    return base


# ---------------------------------------------------------------------------
# Contexto por circuito
# ---------------------------------------------------------------------------
class CircuitInfo:
    def __init__(self, name, receptors, donors, materials, phases):
        self.name = name
        self.receptors = receptors
        self.donors = donors
        self.materials = materials
        self.phases = phases

    @property
    def dests(self):
        return self.receptors + self.donors

    @property
    def usable(self):
        return bool(self.receptors) and (bool(self.donors) or len(self.receptors) > 1) and bool(self.materials)


def detected_destinations(plan):
    sums = plan.dest_sums()
    return [d for d in plan.dest_names if sums.get(d, 0) > 0]


def detected_materials(plan):
    sums = plan.mat_sums()
    return [m for m in plan.mat_names if sums.get(m, 0) > 0]


def circuit_info(plan, cfg, circuit):
    dests = detected_destinations(plan)
    mats = detected_materials(plan)
    dcfg = cfg["destinos"]
    rec = [d for d in dests if dcfg.get(d, {}).get("tipo") == circuit and dcfg.get(d, {}).get("rol") == "Receptor"]
    don = [d for d in dests if dcfg.get(d, {}).get("tipo") == circuit and dcfg.get(d, {}).get("rol") != "Receptor"]
    mm = [m for m in mats if cfg["materiales"].get(m) == circuit]
    ph = [p for p in plan.detected_phases() if cfg["fases"].get(p, True)]
    return CircuitInfo(circuit, rec, don, mm, ph)


def ensure_plan_defaults(plan, cfg, memory=None):
    """Completa fases/destinos/materiales/objetivos/prioridades para un plan nuevo."""
    memory = memory or {}
    for p in plan.detected_phases():
        cfg["fases"].setdefault(p, True)
    for d in detected_destinations(plan):
        if d not in cfg["destinos"]:
            mem = memory.get("destinos", {}).get(d)
            cfg["destinos"][d] = dict(mem) if mem else {"tipo": "N/A", "rol": "Donante"}
    for m in detected_materials(plan):
        if m not in cfg["materiales"]:
            cfg["materiales"][m] = memory.get("materiales", {}).get(m, "N/A")
    if not cfg["general"].get("anio"):
        cfg["general"]["anio"] = plan.detect_year()
    refresh_circuits(plan, cfg)


def suggest_destination_types(plan, cfg):
    """Tipo de destino según el material que recibe mayoritariamente."""
    D = plan.dest_matrix()
    rm = plan.row_material()
    mats = plan.mat_names
    out = {}
    for j, d in enumerate(plan.dest_names):
        col = D[:, j]
        if col.sum() <= 0:
            continue
        acc = {"Mineral": 0.0, "Desmonte": 0.0}
        for k, m in enumerate(mats):
            t = cfg["materiales"].get(m)
            if t in acc:
                acc[t] += col[rm == k].sum()
        if acc["Mineral"] + acc["Desmonte"] > 0:
            out[d] = max(acc, key=acc.get)
    return out


def _round_mt(x):
    if x <= 0:
        return 0.0
    digits = max(2, 2 - int(math.floor(math.log10(x))))
    return float(round(float(x), digits))


def default_objectives(plan, cfg, circuit):
    info = circuit_info(plan, cfg, circuit)
    if not info.receptors:
        return None
    sums = plan.dest_sums()
    ym = plan.year_mask(cfg["general"].get("anio"))
    D = plan.dest_matrix()
    names = plan.dest_names
    tot = sum(D[ym, names.index(r)].sum() for r in info.receptors)
    if tot <= 0:
        tot = sum(sums.get(r, 0) for r in info.receptors)
    weeks = 52
    prom = tot / 1e6 / weeks / len(info.receptors)
    days = len(set(plan.date_ord[ym].tolist())) or weeks * 7
    pd_ = tot / 1e6 / days / len(info.receptors)
    return ({"min": _round_mt(prom * 0.95), "prom": _round_mt(prom), "max": _round_mt(prom * 1.05)},
            {"min": _round_mt(pd_ * 0.85), "prom": _round_mt(pd_), "max": _round_mt(pd_ * 1.15)})


def refresh_circuits(plan, cfg):
    """Sincroniza listas de prioridad y objetivos con la configuración actual."""
    for c in CIRCUITS:
        cc = cfg["circuitos"][c]
        info = circuit_info(plan, cfg, c)
        if cc["semanal"].get("prom") in (None, "") and info.receptors:
            obj = default_objectives(plan, cfg, c)
            if obj:
                cc["semanal"], cc["diario"] = obj
        prio = cc["prioridad"]
        for r in list(prio):
            if r not in info.receptors:
                del prio[r]
        for r in info.receptors:
            p = prio.setdefault(r, {})
            for key, src in (("fases", plan.detected_phases()), ("donantes", info.donors + [x for x in info.receptors if x != r]),
                             ("materiales", info.materials)):
                if key == "donantes":
                    src = info.donors
                blk = p.setdefault(key, {"activo": True, "items": []})
                names = [it[0] for it in blk["items"]]
                items = [it for it in blk["items"] if it[0] in src]
                items += [[s, True] for s in src if s not in names]
                blk["items"] = items


def priority_ranks(cfg, circuit, receptor, block):
    """Devuelve (activo, {nombre: rango}, {nombres excluidos})."""
    p = cfg["circuitos"][circuit]["prioridad"].get(receptor, {}).get(block)
    if not p:
        return False, {}, set()
    ranks, excl = {}, set()
    k = 0
    for name, on in p["items"]:
        if on:
            ranks[name] = k
            k += 1
        else:
            excl.add(name)
    return bool(p.get("activo", True)), ranks, excl


def allowed(cfg, circuit, dest, mat):
    return cfg["circuitos"][circuit]["matriz"].get(dest, {}).get(mat, True)


def objective_values(cfg, circuit, kind):
    o = cfg["circuitos"][circuit][kind]
    vals = [o.get("min"), o.get("prom"), o.get("max")]
    try:
        vals = [float(v) for v in vals]
    except (TypeError, ValueError):
        return None
    lo, de, hi = vals
    if not (lo <= de <= hi) or lo < 0:
        return None
    return lo * 1e6, de * 1e6, hi * 1e6


def validate_config(plan, cfg):
    """Lista de problemas que impiden ejecutar (vacía = ok)."""
    errs = []
    if plan is None:
        return ["Seleccione el Input para Análisis y la Hoja para Análisis."]
    if not cfg["general"].get("nombre", "").strip():
        errs.append("Ingrese el Nombre del Escenario.")
    if not cfg["general"].get("anio"):
        errs.append("Ingrese el Año.")
    if not any(cfg["fases"].get(p, True) for p in plan.detected_phases()):
        errs.append("Habilite al menos una fase.")
    any_active = False
    for c in CIRCUITS:
        cc = cfg["circuitos"][c]
        info = circuit_info(plan, cfg, c)
        if not cc["activo"] or not info.receptors:
            continue
        any_active = True
        if not info.usable:
            errs.append(f"{c}: se necesita al menos un receptor, un donante (o dos receptores) y un material.")
        if objective_values(cfg, c, "semanal") is None:
            errs.append(f"{c}: revise la meta semanal (Mínimo ≤ Promedio ≤ Máximo).")
        if cc["granularidad"] == "diario" and objective_values(cfg, c, "diario") is None:
            errs.append(f"{c}: revise la meta diaria (Mínimo ≤ Promedio ≤ Máximo).")
    if not any_active:
        errs.append("Active el balanceo de Mineral o Desmonte y asigne al menos un receptor (Inputs ▸ Configuración de Destinos).")
    ex = cfg["experimento"]
    if ex["tipo"] in ("reordenamiento", "integral"):
        try:
            v = float(ex["pct_mineral"])
            if not 0 <= v <= 100:
                raise ValueError
        except (TypeError, ValueError):
            errs.append("El porcentaje de polígonos que inician con mineral debe estar entre 0 y 100.")
    return errs


# ---------------------------------------------------------------------------
# Archivo .pmsx
# ---------------------------------------------------------------------------
def save_project(path, cfg, result=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {"aplicacion": APP_NAME, "version": VERSION, "con_resultados": result is not None}
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
        zf.writestr("escenario.json", json.dumps(cfg, ensure_ascii=False, indent=1))
        if result is not None:
            js, arrays = result.to_storage()
            zf.writestr("resultados.json", json.dumps(js, ensure_ascii=False))
            ab = io.BytesIO()
            np.savez_compressed(ab, **arrays)
            zf.writestr("resultados.npz", ab.getvalue())
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
    import os
    os.replace(tmp, path)


def load_project(path):
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "escenario.json" not in names:
            raise ValueError("El archivo no es un proyecto de " + APP_NAME + ".")
        cfg = merge_defaults(json.loads(zf.read("escenario.json").decode("utf-8")))
        stored = None
        if "resultados.json" in names and "resultados.npz" in names:
            js = json.loads(zf.read("resultados.json").decode("utf-8"))
            with np.load(io.BytesIO(zf.read("resultados.npz")), allow_pickle=False) as z:
                arrays = {k: z[k] for k in z.files}
            stored = (js, arrays)
    return cfg, stored


def config_digest(cfg):
    """Huella de los inputs que afectan al cálculo (para marcar resultados desactualizados)."""
    c = copy.deepcopy(cfg)
    c["general"].pop("descripcion", None)
    c["general"].pop("nombre", None)
    return json.dumps(c, sort_keys=True, ensure_ascii=False)
