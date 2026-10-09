"""Motor de cálculo de Plan Material Shift.

Etapas (según el experimento):
  1. Convencional: programa lineal conjunto de las 52 semanas por circuito
     (Mineral / Desmonte) + materialización en filas (+ refinamiento diario).
  2. Asignación Balanceada Aleatoria: reparte de nuevo, al azar, el tonelaje de
     cada fila entre los destinos del circuito conservando exactamente los
     totales del Convencional por semana (o día), material, fase y destino.
  3. Reordenamiento de Filas: permuta el contenido completo de las filas dentro
     de cada polígono para controlar si inicia con mineral o con desmonte.

Reglas rígidas que se respetan siempre:
  * Cada movimiento resta y suma el mismo tonelaje dentro de la misma fila
    (total de fila constante; columnas de material intactas).
  * Oferta: un donante cede como máximo su tonelaje de cada material en la
    semana; un receptor devuelve como máximo su tonelaje base.
  * Intercambio receptor→receptor solo con el excedente del receptor sobre su
    objetivo semanal.
  * Conservación anual exacta de cada donante y cada receptor.
  * Matriz de materiales: una celda desmarcada nunca se modifica.
"""
from __future__ import annotations

import datetime as _dt
import math
import time
from collections import defaultdict

import numpy as np

from . import config as C

EPS = 1e-9
KT = 1000.0          # el LP trabaja en kilotoneladas (mejor escala numérica)
STAGE_NAMES = {"semanal": "Convencional · Semanal", "diario": "Convencional · Diario", "aleatoria": "Asignación Aleatoria"}


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------------------
# Programa lineal genérico de balanceo
# ---------------------------------------------------------------------------
class _Rows:
    def __init__(self):
        self.r, self.c, self.v, self.b = [], [], [], []

    def add(self, cols, vals, rhs):
        k = len(self.b)
        self.r.extend([k] * len(cols))
        self.c.extend(cols)
        self.v.extend(vals)
        self.b.append(rhs)

    def matrix(self, n):
        from scipy.sparse import csr_matrix
        if not self.b:
            return None, None
        return csr_matrix((self.v, (self.r, self.c)), shape=(len(self.b), n)), np.array(self.b)


class BalanceProblem:
    """LP de transferencias donante↔receptor para un conjunto de períodos.

    periods: número de períodos K.  group[k]: grupo de conservación del período k
    (todo el año para el semanal; la semana para el diario).
    D[k, m, p, d] / B[k, m, p, c]: tonelaje base de donantes / receptores.
    """

    def __init__(self, ctx, info, K, group, D, B, lo, de, hi, allow_rr):
        self.ctx, self.info = ctx, info
        self.K, self.group = K, group
        self.D, self.B = D, B
        self.lo, self.de, self.hi = lo, de, hi
        self.allow_rr = allow_rr

    def solve(self):
        from scipy.optimize import linprog

        ctx, info = self.ctx, self.info
        cfg, circ = ctx.cfg, info.name
        R, Dn, M, P = info.receptors, info.donors, info.materials, info.phases
        nc, nd, nm, npz = len(R), len(Dn), len(M), len(P)
        mode = cfg["circuitos"][circ]["modo"]
        D = self.D / KT
        B = self.B / KT
        lo, de, hi = self.lo / KT, self.de / KT, self.hi / KT
        base = B.sum(axis=(1, 2))                                   # K x nc
        allowed = {(x, m): C.allowed(cfg, circ, x, m) for x in R + Dn for m in M}

        pr = {}
        for c in R:
            pr[c] = {b: C.priority_ranks(cfg, circ, c, b) for b, _ in C.PRIO_BLOCKS}

        def excluded(c, block, name):
            act, ranks, excl = pr[c][block]
            return act and name in excl

        def rank(c, block, name):
            act, ranks, excl = pr[c][block]
            return ranks.get(name, len(ranks)) if act else 0

        span_d, span_m = nd + 1, nm + 1
        max_cost = 1.0 + (npz + 1) * span_d * span_m

        cost, ub, meta = [], [], []

        def var(cst, cap, info_):
            cost.append(cst)
            ub.append(cap)
            meta.append(info_)
            return len(cost) - 1

        supply = defaultdict(list)       # (k,m,p,d) -> vars
        giveback = defaultdict(list)     # (k,m,p,c) -> vars
        rr_out = defaultdict(list)       # (k,a) -> vars
        qcoef = defaultdict(list)        # (k,c) -> [(var, coef)]
        cons_d = defaultdict(list)       # (g,d) -> [(var, coef)]
        cons_c = defaultdict(list)       # (g,c) -> [(var, coef)]

        nzk, nzm, nzp = np.nonzero((D.sum(axis=3) > EPS) | (B.sum(axis=3) > EPS))
        for k, mi, pi in zip(nzk.tolist(), nzm.tolist(), nzp.tolist()):
            m, p = M[mi], P[pi]
            g = int(self.group[k])
            for ci, c in enumerate(R):
                if not allowed[(c, m)] or excluded(c, "fases", p) or excluded(c, "materiales", m):
                    continue
                rp, rm = rank(c, "fases", p), rank(c, "materiales", m)
                for di, d in enumerate(Dn):
                    if not allowed[(d, m)] or excluded(c, "donantes", d):
                        continue
                    rd = rank(c, "donantes", d)
                    cap = D[k, mi, pi, di]
                    if cap > EPS:
                        j = var(1.0 + rp * span_d * span_m + rd * span_m + rm, cap, (0, k, mi, pi, di, ci))
                        supply[(k, mi, pi, di)].append(j)
                        qcoef[(k, ci)].append((j, 1.0))
                        cons_d[(g, di)].append((j, 1.0))
                        cons_c[(g, ci)].append((j, 1.0))
                    capb = B[k, mi, pi, ci]
                    if capb > EPS:
                        # devolver primero lo de menor prioridad de fase
                        j = var(0.1 + 0.05 * (npz - rp) / (npz + 1), capb, (1, k, mi, pi, ci, di))
                        giveback[(k, mi, pi, ci)].append(j)
                        qcoef[(k, ci)].append((j, -1.0))
                        cons_d[(g, di)].append((j, -1.0))
                        cons_c[(g, ci)].append((j, -1.0))
                if self.allow_rr and nc > 1:
                    for ai, a in enumerate(R):
                        if a == c or not allowed[(a, m)]:
                            continue
                        capb = B[k, mi, pi, ai]
                        if capb <= EPS:
                            continue
                        j = var(0.5 + rp * 0.01, capb, (2, k, mi, pi, ai, ci))
                        giveback[(k, mi, pi, ai)].append(j)
                        rr_out[(k, ai)].append(j)
                        qcoef[(k, ci)].append((j, 1.0))
                        qcoef[(k, ai)].append((j, -1.0))
                        cons_c[(g, ci)].append((j, 1.0))
                        cons_c[(g, ai)].append((j, -1.0))

        nflow = len(cost)
        unit = max_cost + 1.0
        lam = unit
        w_des = 10.0 * unit
        w_rec = 100.0 * unit
        big = 1000.0 * unit

        A_ub, A_eq = _Rows(), _Rows()
        for (k, mi, pi, di), js in supply.items():
            if len(js) > 1:
                A_ub.add(js, [1.0] * len(js), D[k, mi, pi, di])
        for (k, mi, pi, ci), js in giveback.items():
            if len(js) > 1:
                A_ub.add(js, [1.0] * len(js), B[k, mi, pi, ci])
        for (k, ai), js in rr_out.items():
            surplus = max(0.0, base[k, ai] - de[k])
            A_ub.add(js, [1.0] * len(js), surplus)

        def band(cols, vals, b0, lo_, hi_, w):
            s1 = var(w, np.inf, None)
            s2 = var(w, np.inf, None)
            A_ub.add(cols + [s1], [-v for v in vals] + [-1.0], b0 - lo_)
            A_ub.add(cols + [s2], vals + [-1.0], hi_ - b0)

        def desired(cols, vals, b0, target, w):
            e1 = var(w, np.inf, None)
            e2 = var(w, np.inf, None)
            A_eq.add(cols + [e1, e2], vals + [-1.0, 1.0], target - b0)

        for k in range(self.K):
            if mode == "balanceado":
                tc, tv = [], []
                for ci in range(nc):
                    cols = [j for j, _ in qcoef[(k, ci)]]
                    vals = [v for _, v in qcoef[(k, ci)]]
                    tc += cols
                    tv += vals
                    band(cols, vals, base[k, ci], lo[k], hi[k], w_rec)
                tb = base[k].sum()
                band(tc, tv, tb, nc * lo[k], nc * hi[k], big)
                desired(tc, tv, tb, nc * de[k], w_des)
                if nc > 1:
                    for ci in range(nc):
                        dlt = var(lam, np.inf, None)
                        cols = [j for j, _ in qcoef[(k, ci)]]
                        vals = [v for _, v in qcoef[(k, ci)]]
                        # Q_c - T/n <= dlt  y  T/n - Q_c <= dlt
                        cc = cols + tc + [dlt]
                        v1 = vals + [-v / nc for v in tv] + [-1.0]
                        r1 = tb / nc - base[k, ci]
                        A_ub.add(cc, v1, r1)
                        A_ub.add(cc, [-v for v in v1[:-1]] + [-1.0], -r1)
            else:
                for ci in range(nc):
                    cols = [j for j, _ in qcoef[(k, ci)]]
                    vals = [v for _, v in qcoef[(k, ci)]]
                    band(cols, vals, base[k, ci], lo[k], hi[k], big)
                    desired(cols, vals, base[k, ci], de[k], w_des)

        for lst in list(cons_d.values()) + list(cons_c.values()):
            if lst:
                A_eq.add([j for j, _ in lst], [v for _, v in lst], 0.0)

        n = len(cost)
        Aub, bub = A_ub.matrix(n)
        Aeq, beq = A_eq.matrix(n)
        bounds = np.zeros((n, 2))
        bounds[:, 1] = np.array(ub, dtype=float)
        bounds[np.isinf(bounds[:, 1]), 1] = np.nan
        bnd = [(0.0, None if math.isnan(u) else float(u)) for u in bounds[:, 1]]
        res = linprog(np.array(cost), A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bnd, method="highs")
        ok = bool(res.status == 0)
        x = res.x if ok and res.x is not None else np.zeros(n)
        flows = []
        for j in range(nflow):
            val = x[j]
            if val * KT > 1e-4:
                flows.append((meta[j], min(val, ub[j]) * KT))
        return ok, str(res.message), flows, n


# ---------------------------------------------------------------------------
class RunContext:
    def __init__(self, plan, cfg, progress=None, cancel=None):
        self.plan, self.cfg = plan, cfg
        self.progress = progress or (lambda *a: None)
        self.cancel = cancel or (lambda: False)
        self.V = plan.V.copy()
        self.vcol = {plan.headers[i]: plan.vcol(i) for i in plan.dest_idx}
        self.moves = []          # (fila, etapa, desde, hacia, toneladas)
        self.year_mask = plan.year_mask(cfg["general"].get("anio"))
        self.row_mat = plan.row_material()
        self.mat_names = plan.mat_names
        self.lp_info = {}
        self.rr_tons = defaultdict(float)

    def check(self):
        if self.cancel():
            raise Cancelled()

    def eligible_rows(self, info):
        mats = {self.mat_names.index(m): i for i, m in enumerate(info.materials)}
        phases = {p: i for i, p in enumerate(info.phases)}
        idx, mi, pi = [], [], []
        ph = self.plan.phase
        for r in np.nonzero(self.year_mask)[0].tolist():
            m = mats.get(int(self.row_mat[r]))
            p = phases.get(ph[r])
            if m is None or p is None:
                continue
            idx.append(r)
            mi.append(m)
            pi.append(p)
        return np.array(idx, dtype=int), np.array(mi, dtype=int), np.array(pi, dtype=int)

    # -- aplicación de transferencias en filas ---------------------------------
    def transfer(self, rows, src, dst, amount, stage, descending=False):
        col_s, col_d = self.vcol[src], self.vcol[dst]
        order = rows[::-1] if descending else rows
        remaining = amount
        V = self.V
        for r in order:
            if remaining <= 1e-7:
                break
            av = V[r, col_s]
            if av <= 1e-9:
                continue
            t = av if av < remaining else remaining
            V[r, col_s] = av - t
            V[r, col_d] += t
            self.moves.append((int(r), stage, src, dst, float(t)))
            remaining -= t
        return remaining


def _tensor(ctx, info, rows, mi, pi, period, K):
    R, Dn = info.receptors, info.donors
    nm, npz = len(info.materials), len(info.phases)
    Dt = np.zeros((K, nm, npz, len(Dn)))
    Bt = np.zeros((K, nm, npz, len(R)))
    V = ctx.V
    if len(rows):
        for di, d in enumerate(Dn):
            np.add.at(Dt[..., di], (period, mi, pi), V[rows, ctx.vcol[d]])
        for ci, c in enumerate(R):
            np.add.at(Bt[..., ci], (period, mi, pi), V[rows, ctx.vcol[c]])
    return Dt, Bt


def _materialize(ctx, info, rows, mi, pi, period, flows, stage):
    groups = defaultdict(list)
    for r, m, p, k in zip(rows.tolist(), mi.tolist(), pi.tolist(), period.tolist()):
        groups[(k, m, p)].append(r)
    for key in groups:
        groups[key] = np.array(sorted(groups[key], key=lambda r: (ctx.plan.sec[r], r)), dtype=int)
    R, Dn = info.receptors, info.donors
    pending = 0.0
    # primero salidas desde receptores (devoluciones e intercambios), luego entradas
    for (typ, k, m, p, a, b), t in sorted(flows, key=lambda f: 0 if f[0][0] in (1, 2) else 1):
        rows_g = groups.get((k, m, p))
        if rows_g is None:
            pending += t
            continue
        if typ == 0:
            pending += ctx.transfer(rows_g, Dn[a], R[b], t, stage)
        elif typ == 1:
            pending += ctx.transfer(rows_g, R[a], Dn[b], t, stage, descending=True)
        else:
            pending += ctx.transfer(rows_g, R[a], R[b], t, stage, descending=True)
            ctx.rr_tons[(info.name, k)] += t
    return pending


def run_weekly(ctx, info):
    cfg = ctx.cfg
    rows, mi, pi = ctx.eligible_rows(info)
    weeks = ctx.plan.week[rows] - 1 if len(rows) else np.zeros(0, int)
    K = 52
    Dt, Bt = _tensor(ctx, info, rows, mi, pi, weeks, K)
    lo, de, hi = C.objective_values(cfg, info.name, "semanal")
    prob = BalanceProblem(ctx, info, K, np.zeros(K, int), Dt, Bt,
                          np.full(K, lo), np.full(K, de), np.full(K, hi), allow_rr=True)
    ok, msg, flows, nvar = prob.solve()
    ctx.lp_info[(info.name, "semanal")] = {"ok": ok, "mensaje": msg, "variables": nvar, "flujos": len(flows)}
    pend = _materialize(ctx, info, rows, mi, pi, weeks, flows, "semanal")
    ctx.lp_info[(info.name, "semanal")]["pendiente_t"] = pend
    return rows, mi, pi


def run_daily(ctx, info, rows, mi, pi):
    cfg = ctx.cfg
    if not len(rows):
        return
    plan = ctx.plan
    keys = sorted(set(zip(plan.week[rows].tolist(), plan.date_ord[rows].tolist())))
    kid = {k: i for i, k in enumerate(keys)}
    period = np.array([kid[(plan.week[r], plan.date_ord[r])] for r in rows.tolist()], dtype=int)
    group = np.array([k[0] for k in keys], dtype=int)
    K = len(keys)
    Dt, Bt = _tensor(ctx, info, rows, mi, pi, period, K)
    lo, de, hi = C.objective_values(cfg, info.name, "diario")
    prob = BalanceProblem(ctx, info, K, group, Dt, Bt, np.full(K, lo), np.full(K, de), np.full(K, hi),
                          allow_rr=False)
    snapshot = ctx.V[rows].copy()
    nmoves = len(ctx.moves)
    ok, msg, flows, nvar = prob.solve()
    _materialize(ctx, info, rows, mi, pi, period, flows, "diario")
    # red de seguridad: si una semana no cierra exactamente, se revierte su suavizado
    cols = [ctx.vcol[d] for d in info.dests]
    before = defaultdict(lambda: np.zeros(len(cols)))
    after = defaultdict(lambda: np.zeros(len(cols)))
    wk = plan.week[rows]
    for i, r in enumerate(rows.tolist()):
        before[wk[i]] += snapshot[i, cols]
        after[wk[i]] += ctx.V[r, cols]
    bad = {w for w in before if np.abs(before[w] - after[w]).max() > 1e-4}
    if bad:
        sel = np.isin(wk, list(bad))
        ctx.V[rows[sel]] = snapshot[sel]
        keep = ctx.moves[:nmoves]
        keep += [mv for mv in ctx.moves[nmoves:] if plan.week[mv[0]] not in bad]
        ctx.moves = keep
    ctx.lp_info[(info.name, "diario")] = {"ok": ok, "mensaje": msg, "variables": nvar, "flujos": len(flows),
                                         "semanas_revertidas": sorted(int(w) for w in bad)}


def _greedy_split(rowt, colt, apertura, k, rng):
    """Reparto voraz aleatorio con márgenes exactos (base factible)."""
    cap = colt.copy()
    new = np.zeros((len(rowt), len(colt)))
    order = [ri for ri in rng.permutation(len(rowt)).tolist() if rowt[ri] > 1e-9]
    for t, ri in enumerate(order):
        a = rowt[ri]
        if t == len(order) - 1:
            new[ri] = np.maximum(cap, 0.0)       # la última fila cierra los márgenes
            break
        avail = np.nonzero(cap > 1e-9)[0]
        if len(avail) == 0:
            break
        if apertura == "estricto":
            fit = avail[cap[avail] >= a - 1e-9]
            chosen = [int(rng.choice(fit)) if len(fit) else int(avail[np.argmax(cap[avail])])]
        else:
            chosen = [int(j) for j in rng.choice(avail, size=min(k, len(avail)), replace=False)]
        w = rng.dirichlet(np.ones(len(chosen)))
        alloc = np.zeros(len(colt))
        rem = a
        for j, ww in zip(chosen, w):
            t_ = min(cap[j], a * ww, rem)
            alloc[j] += t_
            rem -= t_
        for j in chosen:
            if rem <= 1e-9:
                break
            t_ = min(cap[j] - alloc[j], rem)
            if t_ > 0:
                alloc[j] += t_
                rem -= t_
        if rem > 1e-9:
            for j in np.argsort(-(cap - alloc)).tolist():
                t_ = min(cap[j] - alloc[j], rem)
                if t_ > 0:
                    alloc[j] += t_
                    rem -= t_
                if rem <= 1e-9:
                    break
        new[ri] = alloc
        cap = cap - alloc
    return new


def _repair_columns(new, colt, tol=1e-7):
    """Corrige residuos numéricos de columnas moviendo tonelaje dentro de filas."""
    for _ in range(4 * new.shape[1] + 4):
        e = colt - new.sum(axis=0)
        if np.abs(e).max() <= tol:
            return True
        jm = int(np.argmin(e))       # columna con exceso
        jp = int(np.argmax(e))       # columna con falta
        t = min(-e[jm], e[jp])
        rows = np.nonzero(new[:, jm] >= t)[0]
        if len(rows) == 0:
            return False
        r = rows[np.argmax(new[rows, jm])]
        new[r, jm] -= t
        new[r, jp] += t
    return np.abs(colt - new.sum(axis=0)).max() <= tol


def _ipf_split(rowt, colt, mask, rng):
    """Matriz aleatoria sobre el soporte `mask` con márgenes dados (ajuste proporcional iterativo)."""
    W = np.where(mask, rng.gamma(1.0, size=mask.shape) + 1e-3, 0.0)
    for _ in range(500):
        rs = W.sum(axis=1)
        W *= np.divide(rowt, rs, out=np.zeros_like(rowt), where=rs > 0)[:, None]
        cs = W.sum(axis=0)
        W *= np.divide(colt, cs, out=np.zeros_like(colt), where=cs > 0)[None, :]
        if np.abs(W.sum(axis=1) - rowt).max() <= 1e-9 * max(1.0, rowt.max()):
            break
    rs = W.sum(axis=1)
    W *= np.divide(rowt, rs, out=np.zeros_like(rowt), where=rs > 0)[:, None]
    if np.abs(W.sum(axis=1) - rowt).max() > 1e-6 or not _repair_columns(W, colt):
        return None
    return W


def run_random(ctx, info, rows, mi, pi, apertura, rng, by_day):
    """Asignación balanceada aleatoria conservando los márgenes de cada grupo.

    Grupo = semana (o día), material y fase. Dentro del grupo se reparte de nuevo
    el tonelaje de cada fila entre los destinos del circuito, al azar, con el
    grado de apertura pedido; los totales por destino del grupo (y por lo tanto
    los objetivos semanales, la oferta y la conservación anual) quedan iguales
    a los del Convencional.
    """
    if not len(rows):
        return 0
    plan, cfg = ctx.plan, ctx.cfg
    groups = defaultdict(list)
    for r, m, p in zip(rows.tolist(), mi.tolist(), pi.tolist()):
        key = (plan.week[r], plan.date_ord[r] if by_day else 0, m, p)
        groups[key].append(r)
    V = ctx.V
    changed = 0
    for key in sorted(groups):
        g = np.array(groups[key], dtype=int)
        m = info.materials[key[2]]
        dests = [d for d in info.dests if C.allowed(cfg, info.name, d, m)]
        if len(dests) < 2:
            continue
        cols = [ctx.vcol[d] for d in dests]
        X = V[np.ix_(g, cols)]
        colt = X.sum(axis=0)
        rowt = X.sum(axis=1)
        act = np.nonzero(colt > 1e-6)[0]
        if len(act) < 2 or (rowt > 1e-9).sum() == 0:
            continue
        na = len(act)
        k = 1 if apertura == "estricto" else (na if apertura == "flexible" else max(1, math.ceil(na / 2)))
        new = _greedy_split(rowt, colt, apertura, k, rng)
        if apertura != "estricto":
            mask = new > 1e-9
            for ri in np.nonzero(rowt > 1e-9)[0]:
                mask[ri, rng.choice(act, size=min(k, na), replace=False)] = True
            alt = _ipf_split(rowt, colt, mask, rng)
            if alt is not None:
                new = alt
        new = np.maximum(new, 0.0)
        if np.abs(colt - new.sum(axis=0)).max() > 1e-6 or np.abs(rowt - new.sum(axis=1)).max() > 1e-6:
            continue
        V[np.ix_(g, cols)] = new
        delta = new - X
        for i_, r in enumerate(g.tolist()):
            dl = delta[i_]
            if np.abs(dl).max() <= 1e-6:
                continue
            changed += 1
            src = [[j, -dl[j]] for j in range(len(dests)) if dl[j] < -1e-6]
            dst = [[j, dl[j]] for j in range(len(dests)) if dl[j] > 1e-6]
            si = di = 0
            while si < len(src) and di < len(dst):
                t = min(src[si][1], dst[di][1])
                ctx.moves.append((r, "aleatoria", dests[src[si][0]], dests[dst[di][0]], float(t)))
                src[si][1] -= t
                dst[di][1] -= t
                if src[si][1] <= 1e-6:
                    si += 1
                if dst[di][1] <= 1e-6:
                    di += 1
    return changed


# ---------------------------------------------------------------------------
# Reordenamiento de filas
# ---------------------------------------------------------------------------
def row_types(plan, cfg, V=None):
    """'M' mineral, 'D' desmonte o '' por fila (según el material y su tonelaje)."""
    rm = plan.row_material()
    mats = plan.mat_names
    t = np.array([""] * plan.n, dtype=object)
    Vv = plan.V if V is None else V
    tot = Vv[:, 0]
    for k, m in enumerate(mats):
        tipo = cfg["materiales"].get(m)
        if tipo in ("Mineral", "Desmonte"):
            t[(rm == k) & (tot > 1e-9)] = "M" if tipo == "Mineral" else "D"
    return t


def _spread_pick(cands, k):
    """Elige k elementos repartidos uniformemente a lo largo de la secuencia."""
    if k <= 0:
        return []
    if k >= len(cands):
        return list(cands)
    step = len(cands) / k
    return [cands[int(i * step + step / 2)] for i in range(k)]


def reorder_rows(plan, cfg, pct, base_mode, types):
    """Devuelve (perm, tabla_semanal, swaps).  perm[i] = fila origen del contenido de i."""
    perm = np.arange(plan.n)
    year = plan.year_mask(cfg["general"].get("anio"))
    enabled = {p for p in plan.detected_phases() if cfg["fases"].get(p, True)}
    by_week = defaultdict(list)
    for (a, b) in plan.polygon_blocks():
        if not year[a] or plan.phase[a] not in enabled:
            continue
        rows = list(range(a, b))
        cls = [r for r in rows if types[r] in ("M", "D")]
        if not cls:
            continue
        kinds = {types[r] for r in cls}
        by_week[int(plan.week[a])].append({"rows": rows, "cls": cls, "kinds": kinds, "first": types[cls[0]]})
    table = []
    cum_dev = 0.0
    swaps_total = 0
    frac = pct / 100.0
    for w in range(1, 53):
        polys = by_week.get(w, [])
        fm = sum(1 for p in polys if p["kinds"] == {"M"})
        fd = sum(1 for p in polys if p["kinds"] == {"D"})
        both = [p for p in polys if len(p["kinds"]) == 2]
        nb = len(both)
        cur_m = sum(1 for p in both if p["first"] == "M")
        if base_mode == "todos":
            n_base, offset = fm + fd + nb, fm
        else:
            n_base, offset = nb, 0
        ideal = frac * n_base
        lo_k, hi_k = offset, offset + nb
        cands = sorted({min(max(math.floor(ideal), lo_k), hi_k), min(max(math.ceil(ideal), lo_k), hi_k)})

        def score(kk):
            return (round(abs(kk - ideal), 9), round(abs(cum_dev + kk - ideal), 9), abs((kk - offset) - cur_m))
        k_m = min(cands, key=score) if n_base else offset
        need_both_m = k_m - offset
        dev = (k_m - ideal) if n_base else 0.0
        cum_dev += dev
        cur_m_list = [p for p in both if p["first"] == "M"]
        cur_d_list = [p for p in both if p["first"] == "D"]
        swaps = 0
        if need_both_m > len(cur_m_list):
            flip = _spread_pick(cur_d_list, need_both_m - len(cur_m_list))
            target = "M"
        else:
            flip = _spread_pick(cur_m_list, len(cur_m_list) - need_both_m)
            target = "D"
        for p in flip:
            i0 = p["cls"][0]
            j = next(r for r in p["cls"] if types[r] == target)
            perm[i0], perm[j] = perm[j], perm[i0]
            swaps += 1
        swaps_total += swaps
        n_all = fm + fd + nb
        m_after = fm + need_both_m
        table.append({
            "semana": w, "poligonos": n_all, "solo_mineral": fm, "solo_desmonte": fd, "ambos": nb,
            "base": n_base, "objetivo": ideal,
            "mineral_antes": fm + cur_m, "mineral_despues": m_after,
            "desmonte_antes": n_all - fm - cur_m, "desmonte_despues": n_all - m_after,
            "pct_mineral": (100.0 * (k_m) / n_base) if n_base else 0.0,
            "diferencia": dev, "intercambios": swaps,
        })
    return perm, table, swaps_total


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
def run(plan, cfg, progress=None, cancel=None, seed=None):
    t0 = time.time()
    ctx = RunContext(plan, cfg, progress, cancel)
    ex = cfg["experimento"]
    tipo = ex["tipo"]
    do_random = tipo in ("aleatoria", "integral")
    do_reorder = tipo in ("reordenamiento", "integral")
    rng = np.random.default_rng(int(ex.get("semilla") or 0) if seed is None else seed)
    infos = {}
    active = [c for c in C.CIRCUITS if cfg["circuitos"][c]["activo"]]
    steps = max(1, len(active) * (2 + do_random)) + do_reorder + 1
    step = 0

    def tick(msg):
        nonlocal step
        ctx.check()
        ctx.progress(msg, min(0.97, step / steps))
        step += 1

    random_rows = {}
    for c in active:
        info = C.circuit_info(plan, cfg, c)
        infos[c] = info
        if not info.usable or C.objective_values(cfg, c, "semanal") is None:
            continue
        tick(f"{c}: optimización semanal (LP)…")
        rows, mi, pi = run_weekly(ctx, info)
        if cfg["circuitos"][c]["granularidad"] == "diario" and C.objective_values(cfg, c, "diario"):
            tick(f"{c}: refinamiento diario (LP)…")
            run_daily(ctx, info, rows, mi, pi)
        if do_random:
            tick(f"{c}: asignación balanceada aleatoria…")
            random_rows[c] = run_random(ctx, info, rows, mi, pi, ex.get("apertura", "moderado"), rng,
                                        cfg["circuitos"][c]["granularidad"] == "diario")
    V_bal = ctx.V.copy()
    perm = np.arange(plan.n)
    reorder_table, swaps = [], 0
    if do_reorder:
        tick("Reordenamiento de filas…")
        types = row_types(plan, cfg, V_bal)
        perm, reorder_table, swaps = reorder_rows(plan, cfg, float(ex.get("pct_mineral", 50)),
                                                  ex.get("base_pct", "elegibles"), types)
    V_final = V_bal[perm]
    tick("Validaciones…")
    res = Result(plan, cfg, V_final, V_bal, perm, ctx.moves, ctx.lp_info, reorder_table, swaps,
                 dict(ctx.rr_tons), random_rows, time.time() - t0)
    res.compute_status()
    res.compute_validations()
    ctx.progress("Listo", 1.0)
    return res


class Result:
    def __init__(self, plan, cfg, V_final, V_bal, perm, moves, lp_info, reorder_table, swaps, rr_tons,
                 random_rows, elapsed, when=None):
        import copy
        self.plan = plan
        self.cfg = copy.deepcopy(cfg)
        self.V = V_final
        self.V_bal = V_bal
        self.perm = perm
        self.moves = moves
        self.lp_info = lp_info
        self.reorder_table = reorder_table
        self.swaps = swaps
        self.rr_tons = rr_tons
        self.random_rows = random_rows
        self.elapsed = elapsed
        self.when = when or _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        self.status = {}
        self.daily_status = {}
        self.validations = []
        self._agg = {}

    # ---- agregados ---------------------------------------------------------
    @property
    def experiment(self):
        return self.cfg["experimento"]["tipo"]

    def dests(self):
        return C.detected_destinations(self.plan)

    def week_dest(self, which="final"):
        key = ("wd", which)
        if key not in self._agg:
            plan = self.plan
            V = self.V if which == "final" else plan.V
            ym = plan.year_mask(self.cfg["general"].get("anio"))
            dn = self.dests()
            cols = [plan.vcol(plan.dest_idx[plan.dest_names.index(d)]) for d in dn]
            out = np.zeros((52, len(dn)))
            w = plan.week[ym] - 1
            np.add.at(out, w, V[np.ix_(np.nonzero(ym)[0], cols)])
            self._agg[key] = out
        return self._agg[key]

    def days(self):
        if "days" not in self._agg:
            plan = self.plan
            ym = plan.year_mask(self.cfg["general"].get("anio"))
            self._agg["days"] = sorted(set(plan.date_ord[ym].tolist()))
        return self._agg["days"]

    def day_dest(self, which="final"):
        key = ("dd", which)
        if key not in self._agg:
            plan = self.plan
            V = self.V if which == "final" else plan.V
            ym = plan.year_mask(self.cfg["general"].get("anio"))
            days = self.days()
            pos = {d: i for i, d in enumerate(days)}
            dn = self.dests()
            cols = [plan.vcol(plan.dest_idx[plan.dest_names.index(d)]) for d in dn]
            out = np.zeros((len(days), len(dn)))
            idx = np.nonzero(ym)[0]
            np.add.at(out, np.array([pos[o] for o in plan.date_ord[idx].tolist()], dtype=int), V[np.ix_(idx, cols)])
            self._agg[key] = out
        return self._agg[key]

    def circuit_info(self, c):
        return C.circuit_info(self.plan, self.cfg, c)

    def circuit_ran(self, c):
        return (c, "semanal") in self.lp_info

    # ---- estados -----------------------------------------------------------
    def compute_status(self):
        dn = self.dests()
        wb, wf = self.week_dest("base"), self.week_dest("final")
        for c in C.CIRCUITS:
            if not self.circuit_ran(c):
                continue
            info = self.circuit_info(c)
            lo, de, hi = C.objective_values(self.cfg, c, "semanal")
            rows = []
            mode = self.cfg["circuitos"][c]["modo"]
            for w in range(52):
                tb = tf = 0.0
                for r in info.receptors:
                    j = dn.index(r)
                    b, f = wb[w, j], wf[w, j]
                    tb += b
                    tf += f
                    rows.append({"periodo": w + 1, "receptor": r, "plan": b, "resultado": f, "min": lo, "prom": de,
                                 "max": hi, "estado": "Ok" if lo - 1e-3 <= f <= hi + 1e-3 else "Brecha"})
                if mode == "balanceado" and len(info.receptors) > 1:
                    n = len(info.receptors)
                    rows.append({"periodo": w + 1, "receptor": "Total Receptores", "plan": tb, "resultado": tf,
                                 "min": n * lo, "prom": n * de, "max": n * hi,
                                 "estado": "Ok" if n * lo - 1e-3 <= tf <= n * hi + 1e-3 else "Brecha"})
            self.status[c] = rows
            if self.cfg["circuitos"][c]["granularidad"] == "diario" and (c, "diario") in self.lp_info:
                lo, de, hi = C.objective_values(self.cfg, c, "diario")
                db, df = self.day_dest("base"), self.day_dest("final")
                drows = []
                for i, o in enumerate(self.days()):
                    for r in info.receptors:
                        j = dn.index(r)
                        f = df[i, j]
                        drows.append({"periodo": _dt.date.fromordinal(o).strftime("%d/%m/%Y"), "receptor": r,
                                      "plan": db[i, j], "resultado": f, "min": lo, "prom": de, "max": hi,
                                      "estado": "Ok" if lo - 1e-3 <= f <= hi + 1e-3 else "Brecha"})
                self.daily_status[c] = drows

    def gaps(self, c, daily=False):
        rows = (self.daily_status if daily else self.status).get(c, [])
        mode = self.cfg["circuitos"][c]["modo"]
        if mode == "balanceado" and not daily and any(r["receptor"] == "Total Receptores" for r in rows):
            return sum(1 for r in rows if r["receptor"] == "Total Receptores" and r["estado"] != "Ok")
        return sum(1 for r in rows if r["estado"] != "Ok")

    def moves_count(self, c=None):
        if c is None:
            return len(self.moves)
        info = self.circuit_info(c)
        ds = set(info.dests)
        return sum(1 for mv in self.moves if mv[2] in ds)

    # ---- validaciones ------------------------------------------------------
    def compute_validations(self):
        plan, cfg = self.plan, self.cfg
        V0, Vb, Vf, perm = plan.V, self.V_bal, self.V, self.perm
        dn = plan.dest_names
        dcols = [plan.vcol(i) for i in plan.dest_idx]
        mcols = [plan.vcol(i) for i in plan.mat_idx]
        val = []

        def add(ind, circ, ok, det):
            val.append({"indicador": ind, "circuito": circ, "estado": "Ok" if ok else "Revisar", "detalle": det})

        d0 = V0[:, dcols].sum(axis=0)
        d1 = Vf[:, dcols].sum(axis=0)
        bad = [dn[j] for j in range(len(dn)) if abs(d1[j] - d0[j]) > 1e-4 + 1e-12 * abs(d0[j])]
        add("Conservación Anual por Destino (Columnas)", "General", not bad,
            "Todas las columnas de destino conservan su total" if not bad else "Difieren: " + ", ".join(bad[:8]))
        m0 = V0[:, mcols].sum(axis=0)
        m1 = Vf[:, mcols].sum(axis=0)
        add("Conservación por Material (Columnas)", "General", np.abs(m1 - m0).max(initial=0) <= 1e-4,
            f"Diferencia máxima {np.abs(m1 - m0).max(initial=0):,.6f} t")
        r0 = V0[:, dcols].sum(axis=1)
        rb = Vb[:, dcols].sum(axis=1)
        nbad = int((np.abs(rb - r0) > 1e-4).sum())
        add("Conservación por Fila (Balanceo)", "General", nbad == 0,
            "Todas las filas conservan su total" if nbad == 0 else f"{nbad} filas con diferencia")
        nbadp = int((np.abs(Vf[:, dcols].sum(axis=1) - r0[perm]) > 1e-4).sum())
        add("Conservación por Registro (Reordenamiento)", "General", nbadp == 0,
            "Cada registro conserva su total y su contenido" if nbadp == 0 else f"{nbadp} registros con diferencia")
        ym = plan.year_mask(cfg["general"].get("anio"))
        wk_b = np.zeros((53, len(dcols)))
        wk_f = np.zeros((53, len(dcols)))
        np.add.at(wk_b, plan.week.clip(0, 52), Vb[:, dcols])
        np.add.at(wk_f, plan.week.clip(0, 52), Vf[:, dcols])
        add("Semana × Destino sin Cambio por Reordenamiento", "General", np.abs(wk_b - wk_f).max() <= 1e-4,
            "El reordenamiento no altera los totales semanales")
        neg = int((Vf[:, dcols] < -1e-7).sum())
        add("Oferta y Devolución (sin Tonelaje Negativo)", "General", neg == 0,
            "Ninguna celda queda negativa" if neg == 0 else f"{neg} celdas negativas")
        dsum = Vf[:, dcols].sum(axis=1)
        msum = Vf[:, mcols].sum(axis=1)
        dev = np.abs(dsum - msum) / np.maximum(np.maximum(dsum, msum), 1e-9)
        nb = int(((dev > 0.0005) & (np.maximum(dsum, msum) > 1e-6)).sum())
        add("Balance Destino / Material por Fila", "General", nb == 0,
            "Σ destinos = Σ materiales en cada fila" if nb == 0 else f"{nb} filas con desviación > 0.05 %")
        # fuera del año activo no se modifica nada
        outside = ~ym
        nout = int((np.abs(Vb[outside][:, dcols] - V0[outside][:, dcols]) > 1e-9).sum())
        add("Filas Fuera del Año o Semanas Activas sin Cambios", "General", nout == 0,
            "Sin cambios" if nout == 0 else f"{nout} celdas modificadas")
        rm = plan.row_material()
        mats = plan.mat_names
        for c in C.CIRCUITS:
            if not self.circuit_ran(c):
                continue
            info = self.circuit_info(c)
            nbad = 0
            for d in info.dests:
                j = plan.vcol(plan.dest_idx[dn.index(d)])
                for m in info.materials:
                    if not C.allowed(cfg, c, d, m):
                        sel = rm == mats.index(m)
                        nbad += int((np.abs(Vb[sel, j] - V0[sel, j]) > 1e-6).sum())
            add("Matriz de Materiales por Destino", c, nbad == 0,
                "Las celdas bloqueadas no cambian" if nbad == 0 else f"{nbad} celdas bloqueadas modificadas")
            lp = self.lp_info.get((c, "semanal"), {})
            add("Solución del Programa Lineal (Semanal)", c, lp.get("ok", False),
                f"{lp.get('variables', 0):,} variables · {lp.get('flujos', 0):,} flujos")
            if (c, "diario") in self.lp_info:
                lpd = self.lp_info[(c, "diario")]
                rev = lpd.get("semanas_revertidas", [])
                add("Solución del Programa Lineal (Diario)", c, lpd.get("ok", False),
                    f"{lpd.get('variables', 0):,} variables" + (f" · semanas revertidas: {rev}" if rev else ""))
            rr = sum(v for (cc, k), v in self.rr_tons.items() if cc == c)
            add("Intercambio entre Receptores (Solo Excedente)", c, True, f"{rr:,.0f} t intercambiadas")
            g = self.gaps(c)
            add("Brechas Semanales", c, g == 0, f"{g} semana(s) fuera de banda")
            if c in self.daily_status:
                gd = self.gaps(c, daily=True)
                add("Brechas Diarias", c, gd == 0, f"{gd} día(s)·receptor fuera de banda")
        self.validations = val

    def checks_ok(self, circuit=None):
        return all(v["estado"] == "Ok" for v in self.validations
                   if not v["indicador"].startswith("Brechas") and v["circuito"] in ("General", circuit or v["circuito"]))

    # ---- persistencia ------------------------------------------------------
    def to_storage(self):
        plan = self.plan
        js = {
            "cfg": self.cfg, "when": self.when, "elapsed": self.elapsed,
            "moves": self.moves, "lp_info": [[k[0], k[1], v] for k, v in self.lp_info.items()],
            "reorder_table": self.reorder_table, "swaps": self.swaps,
            "rr_tons": [[k[0], k[1], v] for k, v in self.rr_tons.items()], "random_rows": self.random_rows,
            "plan": {"path": plan.path, "sheet": plan.sheet, "header_row": plan.header_row, "first_col": plan.first_col,
                     "headers": plan.headers, "roles": plan.roles, "dest_idx": plan.dest_idx, "mat_idx": plan.mat_idx,
                     "content_start": plan.content_start, "content_end": plan.content_end, "phase": plan.phase,
                     "poly": plan.poly, "malla": plan.malla, "proceso": plan.proceso,
                     "detection_note": plan.detection_note, "file_size": plan.file_size, "file_mtime": plan.file_mtime},
        }
        arrays = {"V_base": plan.V, "V_final": self.V, "V_bal": self.V_bal, "perm": self.perm,
                  "excel_rows": plan.excel_rows, "sec": plan.sec, "week": plan.week, "date_ord": plan.date_ord}
        return js, arrays

    @classmethod
    def from_storage(cls, js, arrays):
        from .plan import Plan
        p = js["plan"]
        plan = Plan(path=p["path"], sheet=p["sheet"], header_row=p["header_row"], first_col=p["first_col"],
                    headers=p["headers"], roles=p["roles"], dest_idx=p["dest_idx"], mat_idx=p["mat_idx"],
                    content_start=p["content_start"], content_end=p["content_end"], excel_rows=arrays["excel_rows"],
                    V=arrays["V_base"], sec=arrays["sec"], week=arrays["week"], date_ord=arrays["date_ord"],
                    phase=p["phase"], poly=p["poly"], malla=p["malla"], proceso=p["proceso"],
                    detection_note=p.get("detection_note", ""), file_size=p.get("file_size", 0),
                    file_mtime=p.get("file_mtime", 0.0))
        res = cls(plan, js["cfg"], arrays["V_final"], arrays["V_bal"], arrays["perm"],
                  [tuple(m) for m in js["moves"]], {(a, b): v for a, b, v in js["lp_info"]}, js["reorder_table"],
                  js["swaps"], {(a, b): v for a, b, v in js["rr_tons"]}, js.get("random_rows", {}), js["elapsed"],
                  js["when"])
        res.compute_status()
        res.compute_validations()
        return res
