"""Minimal meta-analysis toolkit (numpy/scipy only).

Effect sizes are standardized mean differences (Cohen's d) for an
independent-groups comparison, signed as patients minus controls.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def d_from_t(t: float, n1: int, n2: int) -> float:
    return t * np.sqrt(1.0 / n1 + 1.0 / n2)


def t_from_d(d: float, n1: int, n2: int) -> float:
    return d / np.sqrt(1.0 / n1 + 1.0 / n2)


def var_d(d: float, n1: int, n2: int) -> float:
    """Large-sample sampling variance of Cohen's d (Hedges & Olkin)."""
    return (n1 + n2) / (n1 * n2) + d ** 2 / (2.0 * (n1 + n2))


def random_effects(d: np.ndarray, v: np.ndarray) -> dict:
    """DerSimonian-Laird random-effects pooled estimate."""
    d = np.asarray(d, float); v = np.asarray(v, float)
    w = 1.0 / v
    fe = np.sum(w * d) / np.sum(w)
    q = np.sum(w * (d - fe) ** 2)
    k = len(d)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (q - (k - 1)) / c) if k > 1 else 0.0
    ws = 1.0 / (v + tau2)
    est = np.sum(ws * d) / np.sum(ws)
    se = np.sqrt(1.0 / np.sum(ws))
    z = est / se
    return {
        "k": int(k), "estimate": float(est), "se": float(se),
        "ci95": [float(est - 1.96 * se), float(est + 1.96 * se)],
        "p": float(2 * stats.norm.sf(abs(z))), "tau2": float(tau2), "Q": float(q),
        "Q_p": float(stats.chi2.sf(q, k - 1)) if k > 1 else None,
        "I2": float(max(0.0, (q - (k - 1)) / q)) if q > 0 else 0.0,
    }


def subgroup_test(d, v, groups) -> dict:
    """Mixed-effects subgroup analysis: separate RE estimates per level,
    then a Q-between test on the subgroup estimates."""
    d = np.asarray(d, float); v = np.asarray(v, float); groups = np.asarray(groups)
    levels = [g for g in sorted(set(groups.tolist()))]
    sub = {}
    for g in levels:
        m = groups == g
        sub[str(g)] = random_effects(d[m], v[m]) if m.sum() >= 2 else None
    ests = np.array([sub[str(g)]["estimate"] for g in levels if sub[str(g)]])
    ses = np.array([sub[str(g)]["se"] for g in levels if sub[str(g)]])
    if len(ests) < 2:
        return {"levels": sub, "Q_between": None, "df": 0, "p": None}
    w = 1.0 / ses ** 2
    grand = np.sum(w * ests) / np.sum(w)
    qb = float(np.sum(w * (ests - grand) ** 2))
    df = len(ests) - 1
    return {"levels": sub, "Q_between": qb, "df": df, "p": float(stats.chi2.sf(qb, df))}


def meta_regression(d, v, x) -> dict:
    """Single continuous moderator; method-of-moments residual tau^2."""
    d = np.asarray(d, float); v = np.asarray(v, float); x = np.asarray(x, float)
    X = np.column_stack([np.ones_like(x), x])
    W = np.diag(1.0 / v)
    beta_fe = np.linalg.solve(X.T @ W @ X, X.T @ W @ d)
    resid = d - X @ beta_fe
    q = float(resid @ W @ resid)
    k, p = X.shape
    P = W - W @ X @ np.linalg.solve(X.T @ W @ X, X.T @ W)
    tau2 = max(0.0, (q - (k - p)) / np.trace(P))
    Ws = np.diag(1.0 / (v + tau2))
    cov = np.linalg.inv(X.T @ Ws @ X)
    beta = cov @ X.T @ Ws @ d
    se = np.sqrt(np.diag(cov))
    z = beta[1] / se[1]
    return {"slope": float(beta[1]), "se": float(se[1]), "p": float(2 * stats.norm.sf(abs(z))), "tau2_resid": float(tau2)}
