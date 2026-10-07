# Football Predictor — LaLiga & Primeira Liga

Predictive platform for European football (LaLiga EA Sports + Portuguese Primeira Liga), 2026–2027 season. It fits a **Dixon-Coles** model (bivariate Poisson with time decay) on past results and runs a **Monte Carlo** simulation (10,000 runs) to project every match and the final standings. Everything is served in a Streamlit app that refreshes itself automatically.

**Live app:** [football-predictor-arnoldo.streamlit.app](https://football-predictor-arnoldo.streamlit.app/)

| | |
|---|---|
| **Leagues** | LaLiga (Spain), Primeira Liga (Portugal) |
| **Data** | 4 seasons (2023-24 → 2026-27), 54 teams, 2,744 matches |
| **Model** | Dixon-Coles + exponential time decay, walk-forward ratings |
| **Simulation** | 10,000 Monte Carlo runs per league/season |
| **Metrics** | 1X2 hit rate, Ranked Probability Score (RPS), average probability on the actual result |
| **Stack** | Python, pandas, pyarrow (Parquet), scipy, Streamlit, GitHub Actions |

## How it's built

The project is an end-to-end pipeline, one notebook per stage:

```text
1. SOURCE ── football-data.org API
   │   Pulls LaLiga and Primeira Liga results (4 seasons). Goals only, no xG.
   ▼
2. BRONZE ── Football_Data_Extraction.ipynb
   │   Stores matches exactly as they arrive (14 columns) as ZSTD-compressed Parquet,
   │   partitioned by league and season. Every row carries its ingestion timestamp (_ingested_at).
   ▼
3. SILVER ── Teams_Master_Builder + Matches_Silver_Builder
   │   Cleans team names with a unique ID (team_key, 54 teams),
   │   and adds the match result (H/D/A) and the goal difference.
   ▼
4. GOLD ── the modelling layer, in 3 notebooks
   │   a) Team_Ratings_Builder       → attack and defense strength per team, matchday by matchday
   │   b) Match_Predictions_Builder  → pre-match probabilities for every fixture
   │   c) Season_Simulations_Builder → 10,000 simulations of the rest of the season
   ▼
5. APP ── app.py + src/app/
   │   Streamlit reads the Gold layer and shows the projected score, probabilities,
   │   metrics (hit rate, RPS) and the projected final table.
   ▼
6. AUTOPILOT ── GitHub Actions
       Runs the 5 notebooks, commits the new data to the repo and Streamlit updates itself.
```

### Data lake

Local Parquet lake (Bronze → Silver → Gold), partitioned Hive-style by league and season under `data/`. Keeping the raw layer untouched means any later stage can be rebuilt from scratch.

| Layer | Contents |
|---|---|
| **Bronze** | Raw match/team data exactly as pulled from football-data.org (14 columns). |
| **Silver** | Team names resolved to a canonical `team_key`; match `result` and `goal_difference` added. |
| **Gold** | `team_ratings` (attack/defense per team per matchday), `match_predictions` (pre-match probabilities), `season_simulations` (Monte Carlo projections, active season only). |

### Repository structure

```text
football-predictor/
├── app.py                           # Streamlit entry point
├── src/
│   ├── app/                         # UI: theme, components, cached data access
│   └── utils/                       # dixon_coles, parquet_io, schema, team_resolution
├── config/leagues.yaml              # league and season configuration
├── data/                            # local Parquet data lake
│   ├── bronze/<league>/season=…/    # raw matches from the API
│   ├── silver/<league>/season=…/    # resolved teams + result
│   ├── gold/<league>/season=…/      # team_ratings, match_predictions
│   ├── gold/season_simulations/     # Monte Carlo projections
│   └── reference/teams_master.parquet
├── Football_Data_Extraction.ipynb   # 1. API → Bronze
├── Teams_Master_Builder.ipynb       #    canonical team list
├── Matches_Silver_Builder.ipynb     # 2. Bronze → Silver
├── Team_Ratings_Builder.ipynb       # 3. Silver → Gold ratings (Dixon-Coles)
├── Match_Predictions_Builder.ipynb  # 4. ratings → pre-match predictions
├── Season_Simulations_Builder.ipynb # 5. Monte Carlo standings
├── Model_Comparison.ipynb           #    XGBoost challenger
└── .github/workflows/weekly-refresh.yml   # automatic refresh
```

## The model

- **Dixon-Coles** fits an attack and a defense rating per team, plus a global home advantage `γ` and baseline `μ`:
  `λ_home = exp(μ + γ + att_home − def_away)`, `λ_away = exp(μ + att_away − def_home)`.
  A `ρ` parameter corrects the probability of low scores (0-0, 1-0, 0-1, 1-1), which a plain Poisson gets wrong.
- **Exponential time decay** (`half_life_days = 365`): a match's weight halves every year, so recent form counts more.
- **Ridge shrinkage** (`reg = 5`) keeps ratings from overreacting to small samples; newly promoted teams start from the average of past promoted teams.
- **Walk-forward, point-in-time ratings** — matchday *N* is only predicted with data available before it was played, to avoid hindsight bias. Matchdays already written are frozen and never overwritten.
- **Score matrix** — probability of every scoreline from 0-0 to 10-10, from which the Home/Draw/Away probabilities are derived.
- **Decision rule for the 1X2 pick** — a plain `argmax` almost never picks a draw, so a draw is predicted when its probability is within `DRAW_MARGIN = 0.06` of the top outcome. For strong favorites (≥ 65%) the projected scoreline is widened so blowouts look like blowouts.
- **Monte Carlo** (10,000 runs per league/season) projects the remaining fixtures to estimate title, Champions League and relegation probabilities.
- **Calibration** is tracked with the **Ranked Probability Score (RPS)**, not just accuracy — RPS respects the natural order of Home, Draw, Away (a Home-predicted-Draw miss costs less than Home-predicted-Away), which is the standard metric in football-forecasting research (Constantinou & Fenton).
- `Model_Comparison.ipynb` benchmarks an **XGBoost challenger** against Dixon-Coles.

## App

```bash
pip install -r requirements.txt
streamlit run app.py
```

- **Season / League / Team / Matchday filters** — full season coverage (38 LaLiga matchdays, 34 Primeira Liga) with Prev/Next navigation on Matchday.
- **Played matchdays:** projected score vs. actual result side by side, with a scoreline-accuracy badge (how close the projected exact score was to the real one; an exact match shows a green check).
- **Upcoming matchdays:** projected score, Home/Draw/Away probability bar, and the 3 most likely exact scores.
- **Model statistics:** 4 KPI tiles for the selected matchday — 1X2 accuracy, RPS, average goals, and average probability the model gave to the result that actually happened — plus the projected final table (Top 4).

## Automatic refresh

A GitHub Actions workflow (`.github/workflows/weekly-refresh.yml`) runs once a week, after the weekend's matches are in:

1. Install dependencies and run the five pipeline notebooks with `nbconvert`.
2. Commit the updated `data/` folder only if something changed.
3. The push redeploys the Streamlit app with the new results and projections.

It can also be started manually from **Actions → Weekly data refresh → Run workflow**. The API key is stored as the repository secret `FOOTBALL_DATA_TOKEN`; locally, set it as an environment variable of the same name. A Windows-friendly script, `refresh_weekly.ps1`, runs the same sequence on a local machine.

## Known limitations

- **No injury or lineup data.** Predictions rely purely on each team's historical scoring/conceding pattern — they don't account for a missing star striker, a suspended defender, or a rotated lineup. That would need a live injury/lineup feed, which the current data sources don't provide.
- **Newly promoted teams** start from a prior with limited top-flight history, so their ratings carry more uncertainty early in the season.
- **Postponed/rescheduled matches** are shown with whatever real-world status is available (`FINISHED` / `TIMED` / `POSTPONED`) per match, so a matchday can stay "in progress" while one fixture is delayed.
- **Goals only, no xG.** The free API tier doesn't expose expected goals or shot data.

## Next steps

- Blend the model with bookmaker odds (football-data.co.uk) and measure the RPS improvement.
- Sweep `half_life_days` (180–730) and compare calibration.
- Show uncertainty ranges for newly promoted teams.

---

Built by [Arnoldo Cuéllar](https://github.com/Arnoldzzz21).
