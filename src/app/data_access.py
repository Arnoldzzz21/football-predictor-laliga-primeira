"""
data_access.py
---------------
Read layer for the app: wraps src/utils/parquet_io.py with Streamlit
caching and adds the match projection logic (lambda_home/away, scoreline
matrix, top-3 most likely scorelines) reusing src/utils/dixon_coles.py.

Note on the actual state of the pipeline (2026-09-26): Team_Ratings_Builder
runs up to the matchday that has already been played (including the
just-closed matchday), but Match_Predictions_Builder can lag one step
behind (it hasn't generated the next matchday's row yet). That is why
match_projection() computes the projection live with the latest
team_ratings snapshot when it doesn't find the already-saved row in
match_predictions -- the app must never be left without a projection for
the next matchday.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.utils.parquet_io import read_partition
from src.utils.dixon_coles import score_matrix, outcome_probs

LAKE_ROOT = Path("data")
ACTIVE_SEASON = "2026-2027"

# For now the app only exposes the active season in the Season slicer --
# the Data Lake already has Silver/Gold for 3 earlier seasons (used as
# history to train the model), but season_simulations (Monte Carlo) only
# exists for the active season, so navigating past seasons from the UI
# would leave the projected table broken. When 2027-2028 starts this list
# will have 2 elements and the slicer will be ready for that with no
# further changes.
AVAILABLE_SEASONS = [ACTIVE_SEASON]

LEAGUE_LABELS = {"laliga": "LaLiga EA Sports", "primeira_liga": "Primeira Liga"}
LEAGUE_FLAG = {"laliga": "ES", "primeira_liga": "PT"}


@st.cache_data(ttl=3600, show_spinner=False)
def load_teams_master() -> pd.DataFrame:
    return read_partition(LAKE_ROOT / "reference" / "teams_master.parquet").to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_matches(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "silver" / league / f"season={season}" / "matches.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_team_ratings(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / league / f"season={season}" / "team_ratings.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_match_predictions(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / league / f"season={season}" / "match_predictions.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_season_simulations(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / "season_simulations" / league / f"season={season}" / "season_simulations.parquet"
    return read_partition(path).to_pandas()


def team_name_map(teams: pd.DataFrame, league: str) -> dict[str, str]:
    sub = teams[teams.league == league]
    return dict(zip(sub.team_key, sub.official_name))


def active_season_teams(matches: pd.DataFrame) -> list[str]:
    return sorted(pd.unique(matches[["home_team_key", "away_team_key"]].values.ravel()).tolist())


def latest_ratings_snapshot(ratings: pd.DataFrame) -> pd.DataFrame:
    """One row per team_key, at the most recent matchday available."""
    last_md = ratings["matchday"].max()
    return ratings[ratings["matchday"] == last_md].set_index("team_key")


def global_params(ratings_snapshot: pd.DataFrame) -> tuple[float, float, float]:
    row = ratings_snapshot.iloc[0]
    return float(row["mu"]), float(row["gamma"]), float(row["rho"])


def _predict_lambdas(home_key: str, away_key: str, snap: pd.DataFrame,
                      mu: float, gamma: float) -> tuple[float, float]:
    """Same functional form that fit_dixon_coles trains (dixon_coles.py)."""
    att_h, def_h = snap.loc[home_key, ["attack", "defense"]]
    att_a, def_a = snap.loc[away_key, ["attack", "defense"]]
    lh = float(np.exp(mu + gamma + att_h - def_a))
    la = float(np.exp(mu + att_a - def_h))
    return lh, la


# "Clear favorite" threshold for showing a bigger scoreline in UPCOMING
# matches. Set with a backtest on the full history (2,158 matches, both
# leagues, 4 seasons): with P(favorite wins) >= 0.65 it applies to ~15% of
# matches, and in those the favorite won 82% of the time and by 2+ goals 57%.
BLOWOUT_MIN_FAV_PROB = 0.65


def blowout_scoreline(lh: float, la: float, p_home: float,
                       p_away: float) -> tuple[int, int] | None:
    """Blowout scoreline for a clear favorite, or None if the match is
    close (in that case the usual most likely scoreline is kept).

    Rule: favorite goals = floor(lambda_fav + 0.75) (its expected goals
    rounded with an upward bias) and opponent goals = floor(lambda_opp).
    This is not the single most likely scoreline (that is usually 2-0), but
    in the backtest on clear-favorite matches it scores equal or better
    than the most likely scoreline: average accuracy badge 64.2 vs 63.0,
    exact score 14.4% vs 12.5%, and lower total-goal error (1.41 vs 1.64).
    It overestimates the real average margin (2.6 vs 1.9 goals), in
    exchange for better reflecting how much the favorite scores.

    Returns the scoreline as (home, away)."""
    fav_is_home = p_home >= p_away
    if max(p_home, p_away) < BLOWOUT_MIN_FAV_PROB:
        return None
    lam_fav, lam_dog = (lh, la) if fav_is_home else (la, lh)
    fav_goals = int(np.floor(lam_fav + 0.75))
    dog_goals = int(np.floor(lam_dog))
    if fav_goals - dog_goals < 1:  # safeguard: never show a draw/loss for the favorite
        return None
    return (fav_goals, dog_goals) if fav_is_home else (dog_goals, fav_goals)


def match_projection(home_key: str, away_key: str, matchday: int,
                      predictions: pd.DataFrame, ratings_snapshot: pd.DataFrame,
                      mu: float, gamma: float, rho: float,
                      show_blowout: bool = False) -> dict:
    """show_blowout=True ONLY for upcoming matches: if the favorite is
    clearly superior, 'projected_home/away' becomes the blowout scoreline
    (blowout_scoreline). Already-played matches always use the original
    most likely scoreline, so their historical results and accuracy badge
    stay exactly the same. The original most likely scoreline is always
    kept in 'modal_home/modal_away'."""
    row = predictions[
        (predictions.matchday == matchday)
        & (predictions.home_team_key == home_key)
        & (predictions.away_team_key == away_key)
    ]
    if not row.empty:
        r = row.iloc[0]
        lh, la = float(r.lambda_home), float(r.lambda_away)
        p_home, p_draw, p_away = float(r.p_home), float(r.p_draw), float(r.p_away)
        live = False
    else:
        lh, la = _predict_lambdas(home_key, away_key, ratings_snapshot, mu, gamma)
        p_home, p_draw, p_away = outcome_probs(lh, la, rho)
        live = True

    matrix = score_matrix(lh, la, rho)
    order = np.argsort(matrix.ravel())[::-1][:3]
    top = []
    for flat_idx in order:
        i, j = divmod(int(flat_idx), matrix.shape[1])
        top.append({"home": i, "away": j, "prob": float(matrix[i, j])})

    modal_h, modal_a = top[0]["home"], top[0]["away"]
    proj_h, proj_a = modal_h, modal_a
    blowout = blowout_scoreline(lh, la, p_home, p_away) if show_blowout else None
    if blowout is not None:
        proj_h, proj_a = blowout

    return {
        "lambda_home": lh, "lambda_away": la,
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "projected_home": proj_h, "projected_away": proj_a,
        "modal_home": modal_h, "modal_away": modal_a,
        "is_blowout": blowout is not None,
        "top_scorelines": top,
        "live_projection": live,
    }


def scoreline_accuracy(proj_h: int, proj_a: int, final_h: int, final_a: int,
                        penalty_per_goal: float = 20.0) -> float:
    """How close the projected exact scoreline (proj_h-proj_a) was to the
    final result (final_h-final_a) -- the badge shown next to the final
    result in the app. 100% if the scoreline matches exactly; it drops
    `penalty_per_goal` percentage points for each goal of total difference
    (|home| + |away|), never below 0. With the default of 20 pts/goal: same
    scoreline -> 100%, one goal off -> 80%, two -> 60%, etc."""
    diff = abs(proj_h - final_h) + abs(proj_a - final_a)
    return max(0.0, 100.0 - penalty_per_goal * diff)


DRAW_MARGIN = 0.06


def predicted_outcome(p_home: float, p_draw: float, p_away: float,
                       draw_margin: float = DRAW_MARGIN) -> str:
    """1X2 label the model 'bets' on for a match, given its 3
    probabilities. With a plain argmax() the draw practically never wins
    (it is the "middle" outcome between two more extreme alternatives): over
    the full history (4 seasons, both leagues, 2158 matches played) the
    model picked Draw as the most likely outcome in only 0.5% of cases,
    against 26% of real draws.

    This adjustment gives the draw a fair chance: if p_draw is within
    `draw_margin` of the highest probability between home/away, Draw is
    predicted. Measured against the same history, this is an honest
    trade-off, not a free improvement: with margin=0.06 1X2 accuracy drops
    ~0.6pp (53.0% -> 52.4%) but the model goes from "almost never" to
    "sometimes" predicting a draw (0.5% -> 5.2% of matches, and of the real
    draws it actually detects, from 0.4% to 6.1%) -- a version that never
    says Draw looks unconvincing even though technically a plain argmax
    maximizes raw accuracy."""
    best_side = "H" if p_home >= p_away else "A"
    best_side_p = max(p_home, p_away)
    if p_draw >= best_side_p - draw_margin:
        return "D"
    return best_side


def matchday_brier_score(matches: pd.DataFrame, predictions: pd.DataFrame,
                          team_key: str | None = None) -> float | None:
    """Average Brier score (0 to 0.667, the lower the better) over the
    matchdays already played: it measures how well calibrated the full set
    of 3 probabilities is, not just whether the most likely outcome was
    right -- so it complements (does not replace) the 1X2 accuracy from
    matchday_accuracy_trend()."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    probs = merged[["p_home", "p_draw", "p_away"]].to_numpy()
    y = merged["result"].map({"H": 0, "D": 1, "A": 2}).to_numpy()
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(probs)), y] = 1
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def matchday_rps_score(matches: pd.DataFrame, predictions: pd.DataFrame,
                        team_key: str | None = None) -> float | None:
    """Average Ranked Probability Score (0 to 1, the lower the better) over
    the matchdays already played. Unlike the Brier score (which treats
    Home/Draw/Away as unrelated categories), RPS respects the natural order
    of the 3 outcomes -- Home, then Draw, then Away, from most to least
    favorable to the home team -- and penalizes a forecast that said Home
    and turned out Draw less than one that said Home and turned out Away.
    It is the de facto standard in the academic football-forecasting
    literature (Constantinou & Fenton), which is why it replaces the generic
    Brier score as the calibration metric shown in the app.

    Formula (Epstein 1969, r=3 categories in H-D-A order):
    RPS = 1/(r-1) * sum_{i=1}^{r-1} (CumForecast_i - CumActual_i)^2
    The last cumulative term (i=r) is always 0 (forecast and actual both sum
    to 1), so it is omitted -- it doesn't change the result, it only avoids
    summing a term that is always zero."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    cum_forecast_1 = merged["p_home"]
    cum_forecast_2 = merged["p_home"] + merged["p_draw"]
    is_home = (merged["result"] == "H").astype(float)
    is_draw = (merged["result"] == "D").astype(float)
    cum_actual_1 = is_home
    cum_actual_2 = is_home + is_draw
    rps = 0.5 * ((cum_forecast_1 - cum_actual_1) ** 2 + (cum_forecast_2 - cum_actual_2) ** 2)
    return float(rps.mean())


def avg_goal_error(matches: pd.DataFrame, predictions: pd.DataFrame,
                    team_key: str | None = None) -> float | None:
    """Average error in total projected goals vs. the actual result, over
    the matchdays already played -- complements RPS (calibration of the 3
    probabilities) with a reading in goals, easier to interpret for someone
    who doesn't work with probability models: "on average, the model is off
    by X goals in total per match".

    The projected scoreline is approximated by rounding lambda_home/lambda_away
    (each team's expected goals) instead of recomputing the full scoreline
    matrix with the Dixon-Coles low-score correction (rho) -- same underlying
    idea as scoreline_accuracy() but without needing rho per matchday, a
    minimal difference for a season-aggregate metric."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "lambda_home", "lambda_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    proj_total = merged["lambda_home"].round() + merged["lambda_away"].round()
    real_total = merged["home_score"] + merged["away_score"]
    return float((proj_total - real_total).abs().mean())


def avg_real_goals(stats_matches: pd.DataFrame, all_matches: pd.DataFrame,
                    team_key: str | None = None) -> tuple[float | None, bool]:
    """Average REAL goals scored per match -- replaces the old use of
    avg_goal_error() in the 'Avg goals' tile, which actually showed the
    model's projection error (|projected goals - actual goals|), not an
    average of goals. This function does return the actual average of goals
    scored.

    stats_matches: matches of the matchday selected in the MATCHDAY filter.
    If it has FINISHED matches, the average is computed only over that
    matchday.

    all_matches: all the matches of the current league/season (already
    filtered by league in app.py via load_matches). It serves as a fallback
    when the selected matchday hasn't been played yet -- instead of "n/a",
    the tile shows the season's average goals so far ("matchdays that
    haven't been played learn from the ones that have"), always within the
    same league so as not to mix LaLiga's scoring rate with Primeira Liga's.

    Returns (value, is_season_average) so the caller can adjust the label
    depending on whether the number is from the exact matchday or from the
    season fallback."""
    def _avg(df: pd.DataFrame) -> float | None:
        finished = df[df.status == "FINISHED"]
        if team_key:
            finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
        if finished.empty:
            return None
        return float((finished.home_score + finished.away_score).mean())

    md_avg = _avg(stats_matches)
    if md_avg is not None:
        return md_avg, False
    return _avg(all_matches), True


def avg_prob_on_actual(matches: pd.DataFrame, predictions: pd.DataFrame,
                        team_key: str | None = None) -> float | None:
    """Average probability (0-100%, the higher the better) the model gave
    to the outcome that actually happened, over the matchdays played.
    It complements 1X2 accuracy (binary: did it get the MOST likely outcome
    right or not) with how "convinced" the model was of the correct outcome
    on average -- for example, a draw the model gave 35% (without it being
    its favorite) counts differently here than one at 5%, even though both
    are a miss in the binary accuracy metric."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    prob_map = {"H": "p_home", "D": "p_draw", "A": "p_away"}
    prob_actual = merged.apply(lambda r: r[prob_map[r["result"]]], axis=1)
    return float(prob_actual.mean() * 100)


def matchday_status(matches: pd.DataFrame) -> tuple[int | None, int | None]:
    """(last matchday played, next matchday) for this league/season."""
    finished = matches[matches.status == "FINISHED"]
    last_finished = int(finished.matchday.max()) if not finished.empty else None
    upcoming_candidates = sorted(matches[matches.matchday > (last_finished or 0)].matchday.unique())
    next_md = int(upcoming_candidates[0]) if upcoming_candidates else None
    return last_finished, next_md


def matchday_accuracy_trend(matches: pd.DataFrame, predictions: pd.DataFrame,
                             team_key: str | None = None) -> tuple[list[int], list[float]]:
    """% of 1X2 hits per matchday played, comparing the projected outcome
    (predicted_outcome(), argmax + draw margin -- see that function)
    against the actual result."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return [], []
    pred_label = merged.apply(
        lambda r: predicted_outcome(r.p_home, r.p_draw, r.p_away), axis=1
    )
    merged["hit"] = (pred_label == merged["result"]).astype(int)
    by_md = merged.groupby("matchday")["hit"].mean().sort_index()
    return by_md.index.tolist(), (by_md.values * 100).tolist()
