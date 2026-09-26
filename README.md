# Football Predictor — LaLiga & Primeira Liga

Predictive platform for European football (LaLiga EA Sports + Portuguese Primeira Liga), 2026–2027 season, built using the Dixon-Coles model (bivariate Poisson with time decay) and Monte Carlo simulation (10,000 simulations per match) to project results and the final standings.

## App

```
pip install -r requirements.txt
streamlit run app.py
```

- Projected score vs. actual result per matchday played.
- Next matchday: projected score, 1X2 probability, and the 3
  most likely exact scores.
- Model's historical accuracy, attacking heat map, and projected
  table (Top 4).

## Pipeline / Data Lake


Local Parquet Data Lake (Bronze → Silver → Gold), partitioned by
league/season under `data/`. See the notebooks in the root directory for each stage
(extraction, team resolution, Dixon-Coles ratings, predictions,
season simulations).

