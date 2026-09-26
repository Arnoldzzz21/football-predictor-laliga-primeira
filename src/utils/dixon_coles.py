
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson


def _tau(x, y, lh, la, rho):
    t = np.ones_like(lh)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    t[m00] = 1 - lh[m00] * la[m00] * rho
    t[m01] = 1 + lh[m01] * rho
    t[m10] = 1 + la[m10] * rho
    t[m11] = 1 - rho
    return t


def _neg_loglik(params, hi, ai, x, y, w, n, reg, att0, def0, reg_glob):
    att, dfn = params[:n], params[n:2 * n]
    mu, gamma, rho = params[2 * n:]
    lh = np.exp(mu + gamma + att[hi] - dfn[ai])
    la = np.exp(mu + att[ai] - dfn[hi])
    tau = np.clip(_tau(x, y, lh, la, rho), 1e-10, None)
    ll = w * (np.log(tau) + x * np.log(lh) - lh + y * np.log(la) - la)
    penalty = reg * (np.sum((att - att0) ** 2) + np.sum((dfn - def0) ** 2))
    penalty += reg_glob * ((gamma - 0.25) ** 2 + (rho + 0.05) ** 2)  # weak anchor
    return -ll.sum() + penalty


def fit_dixon_coles(matches, teams, ref_date, half_life_days=365,
                    reg=5.0, prior=None, x0=None, reg_glob=10.0):
    """Fit one league with Dixon-Coles.

    matches: played matches only, already filtered to before ref_date (caller's job).
    teams:   all team_keys to rate. Teams without matches stay at their prior.
    prior:   optional dict {team_key: (attack0, defense0)}. Missing teams use (0, 0).
    """
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}

    hi_s = matches["home_team_key"].map(idx)
    ai_s = matches["away_team_key"].map(idx)
    if hi_s.isna().any() or ai_s.isna().any():
        raise ValueError("matches contain team_keys that are not in `teams`")
    hi, ai = hi_s.to_numpy(dtype=int), ai_s.to_numpy(dtype=int)

    x = matches["home_score"].to_numpy(dtype=float)
    y = matches["away_score"].to_numpy(dtype=float)
    days = (ref_date - matches["match_date"]).dt.total_seconds().to_numpy() / 86400
    w = np.exp(-(np.log(2) / half_life_days) * np.clip(days, 0, None))

    prior = prior or {}
    att0 = np.array([prior.get(t, (0.0, 0.0))[0] for t in teams], dtype=float)
    def0 = np.array([prior.get(t, (0.0, 0.0))[1] for t in teams], dtype=float)

    if x0 is None:
        x0 = np.zeros(2 * n + 3)
        x0[:n], x0[n:2 * n] = att0, def0
        x0[2 * n:] = [0.25, 0.25, -0.05]
    bounds = [(-3, 3)] * (2 * n) + [(-2, 2), (-1, 1), (-0.3, 0.3)]

    res = minimize(_neg_loglik, x0, args=(hi, ai, x, y, w, n, reg, att0, def0, reg_glob),
                   method="L-BFGS-B", bounds=bounds)
    p = res.x

    n_matches = np.bincount(hi, minlength=n) + np.bincount(ai, minlength=n)
    ratings = pd.DataFrame({
        "team_key": teams,
        "attack": p[:n],
        "defense": p[n:2 * n],
        "n_matches": n_matches,
    })
    params = {"mu": float(p[2 * n]), "gamma": float(p[2 * n + 1]), "rho": float(p[2 * n + 2])}
    return ratings, params, res

def score_matrix(lh, la, rho, max_goals=10):
    """P(home scores i, away scores j), with the Dixon-Coles low-score correction."""
    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    m[0, 0] *= 1 - lh * la * rho
    m[0, 1] *= 1 + lh * rho
    m[1, 0] *= 1 + la * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def outcome_probs(lh, la, rho, max_goals=10):
    """Returns (P_home_win, P_draw, P_away_win)."""
    m = score_matrix(lh, la, rho, max_goals)
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())
