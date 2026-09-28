# Football Predictor — LaLiga & Primeira Liga

Predictive platform for European football (LaLiga EA Sports + Portuguese Primeira Liga), 2026–2027 season, built using the Dixon-Coles model (bivariate Poisson with time decay) and Monte Carlo simulation (10,000 simulations per match) to project results and the final standings.

## App

```
pip install -r requirements.txt
streamlit run app.py
```

- **Season / League / Team / Matchday filters** — full season coverage (38 LaLiga matchdays, 34 Primeira Liga), with Prev/Next navigation on Matchday.
- **Played matchdays:** projected score vs. actual result side by side, with a scoreline-accuracy badge (how close the projected exact score was to the real one — a full match shows a green checkmark instead of a percentage).
- **Upcoming matchdays:** projected score, Home/Draw/Away probability bar, and the 3 most likely exact scores.
- **Model statistics:** 4 model-performance KPI tiles (1X2 accuracy for the last played matchday, RPS, average goal error, Monte Carlo simulation count — each color-coded red-to-green by how good the value is), and the projected final table (Top 4).

## Model

- **Dixon-Coles** (bivariate Poisson with a low-score correction) fits attack/defense ratings per team from a rolling window of past seasons, with **exponential time decay** (`half_life_days`) so recent matches count more than older ones.
- Ratings are computed **walk-forward, point-in-time** — matchday *N*'s prediction only ever sees data available before matchday *N* was played, to avoid hindsight bias.
- **Monte Carlo simulation** (10,000 runs per league/season) projects the rest of the season from the current ratings to estimate final standings, title/Champions League/relegation probabilities.
- The 1X2 decision rule gives draws a fair chance (`argmax` alone almost never picks a draw, since it's structurally the "middle" outcome) instead of just taking the highest of the three probabilities.
- Model calibration is tracked with the **Ranked Probability Score (RPS)**, not just raw accuracy — RPS respects the natural order of the 3 outcomes (Home, Draw, Away), penalizing a Home-predicted-Draw miss less than a Home-predicted-Away miss, unlike a generic Brier score. It's the standard calibration metric in academic football-forecasting literature (Constantinou & Fenton). A well-calibrated model can be a favorite to "beat the market" even when its top-1 accuracy looks unremarkable.

## Known limitations

- **No injury or lineup data.** Predictions are based purely on each team's historical scoring/conceding pattern (Dixon-Coles ratings) — they don't account for a missing star striker, a suspended defender, or a rotated lineup for a midweek Champions League tie. Incorporating that would need a live injury/lineup feed, which isn't available from the current data sources.
- **Newly promoted teams** start from a prior with limited top-flight history, so their ratings carry more uncertainty early in the season than an established team's.
- **Postponed/rescheduled matches** are shown with whatever real-world status is available (`FINISHED` / `TIMED` / `POSTPONED`) per match, so a matchday can be "in progress" for a while if one fixture is delayed.

## Pipeline / Data Lake

Local Parquet Data Lake (Bronze → Silver → Gold), partitioned by
league/season under `data/`. See the notebooks in the root directory for each stage
(extraction, team resolution, Dixon-Coles ratings, predictions,
season simulations).

- **Bronze:** raw match/team data as pulled from football-data.org.
- **Silver:** team names resolved to canonical `team_key`, match result and goal difference added.
- **Gold:** `team_ratings` (Dixon-Coles attack/defense per team/matchday), `match_predictions` (pre-match probabilities), `season_simulations` (Monte Carlo projections).

## Live app

View it here: [football-predictor-arnoldo.streamlit.app](https://football-predictor-arnoldo.streamlit.app/)
