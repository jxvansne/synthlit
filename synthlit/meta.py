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


def meta_regression_multi(d, v, X, test_cols) -> dict | None:
    """Mixed-effects meta-regression on design matrix X (intercept included),
    method-of-moments residual tau^2 as in `meta_regression`, with a Wald
    chi-square test that the coefficients in `test_cols` are all zero.
    Returns None when the model has no residual degrees of freedom."""
    d = np.asarray(d, float); v = np.asarray(v, float); X = np.asarray(X, float)
    k, p = X.shape
    if k <= p or not test_cols:
        return None
    W = np.diag(1.0 / v)
    XtWX_inv = np.linalg.inv(X.T @ W @ X)
    resid = d - X @ (XtWX_inv @ X.T @ W @ d)
    q = float(resid @ W @ resid)
    P = W - W @ X @ XtWX_inv @ X.T @ W
    tau2 = max(0.0, (q - (k - p)) / np.trace(P))
    Ws = np.diag(1.0 / (v + tau2))
    cov = np.linalg.inv(X.T @ Ws @ X)
    beta = cov @ X.T @ Ws @ d
    s = list(test_cols)
    b = beta[s]
    qm = float(b @ np.linalg.solve(cov[np.ix_(s, s)], b))
    return {"Q_M": qm, "df": len(s), "p": float(stats.chi2.sf(qm, len(s))), "tau2_resid": float(tau2),
            "beta": [float(x) for x in beta]}


def _add_columns(X: list, cols: list) -> list[int]:
    """Append each column to X if it is not collinear with what is there; return the kept indices."""
    kept = []
    for c in cols:
        trial = np.column_stack(X + [c])
        if np.linalg.matrix_rank(trial) > len(X):
            X.append(c); kept.append(len(X) - 1)
    return kept


def _dummies(groups) -> list:
    groups = np.asarray(groups)
    levels = sorted(set(groups.tolist()), key=lambda g: (-int((groups == g).sum()), str(g)))
    return [(groups == g).astype(float) for g in levels[1:]]  # most common level is the reference


def categorical_test(d, v, groups, covariates=()) -> float | None:
    """p for a categorical moderator (dummy-coded) in a mixed-effects meta-regression,
    optionally adjusting for other covariate columns. None if the moderator can't be tested."""
    d = np.asarray(d, float)
    X = [np.ones_like(d)]
    _add_columns(X, [np.asarray(c, float) for c in covariates])
    test = _add_columns(X, _dummies(groups))
    r = meta_regression_multi(d, v, np.column_stack(X), test)
    return None if r is None else r["p"]


def continuous_test(d, v, x, covariates=()) -> float | None:
    """p for a continuous moderator in a mixed-effects meta-regression, optionally adjusted."""
    d = np.asarray(d, float)
    X = [np.ones_like(d)]
    _add_columns(X, [np.asarray(c, float) for c in covariates])
    test = _add_columns(X, [np.asarray(x, float)])
    r = meta_regression_multi(d, v, np.column_stack(X), test)
    return None if r is None else r["p"]


def egger_test(d, v) -> dict:
    """Classic Egger regression test for funnel asymmetry: OLS of d/se on 1/se; tests the intercept."""
    d = np.asarray(d, float); se = np.sqrt(np.asarray(v, float))
    y = d / se; X = np.column_stack([np.ones_like(se), 1.0 / se])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    k = len(d); dof = k - 2
    s2 = float(np.sum((y - X @ beta) ** 2) / dof)
    se_b0 = float(np.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0]))
    t = float(beta[0] / se_b0)
    return {"intercept": float(beta[0]), "se": se_b0, "t": t, "df": dof, "p": float(2 * stats.t.sf(abs(t), dof))}


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
