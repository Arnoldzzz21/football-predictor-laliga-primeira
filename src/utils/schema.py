"""
schema.py
---------
Explicit pyarrow schemas per table. They are defined by hand (instead of
letting pandas/pyarrow infer the type) because in football it is very easy
for a season with no matches played yet (2026-2027 as of today) to have
entire columns of nulls (home_score, away_score, xg) and automatic
inference types them as `null`/`string` instead of `int32`/`float32` —
that breaks concatenation across seasons later on (`read_league_all_seasons`).
"""

import pyarrow as pa

# BRONZE layer: raw data, one row = one match, exactly as it arrives from the
# source (API or scraping), with minimal transformation (only typing and the
# standardized column name — NOT cleaning of team names, that is the job of
# bronze_to_silver.py).
MATCHES_BRONZE_SCHEMA = pa.schema(
    [
        ("league", pa.string()),          # "laliga" | "primeira_liga"
        ("season", pa.string()),          # "2023-2024" ... "2026-2027"
        ("matchday", pa.int32()),         # matchday
        ("match_date", pa.timestamp("s", tz="UTC")),
        ("home_team", pa.string()),       # name exactly as delivered by the source
        ("away_team", pa.string()),
        ("home_team_id", pa.string()),    # source id (to join with teams_master)
        ("away_team_id", pa.string()),
        ("home_score", pa.int32()),       # null if not played yet
        ("away_score", pa.int32()),
        ("status", pa.string()),          # SCHEDULED | LIVE | FINISHED | POSTPONED
        ("home_xg", pa.float32()),        # null if the source doesn't provide it in the plan used
        ("away_xg", pa.float32()),
        ("source", pa.string()),          # "football_data_org" | "api_football" | "scraping:<site>"
    ]
)

# Reference table (`reference/` layer, not versioned by season): maps
# names/ids that change between sources to the same canonical team, and
# stores club-safe metadata (official name, short code, colors/country
# flag — never the crest) for Module 1 (anti-copyright strategy) and
# Module 2 (promoted teams).
TEAMS_MASTER_SCHEMA = pa.schema(
    [
        ("team_key", pa.string()),        # canonical internal id, stable across seasons
        ("official_name", pa.string()),   # full official name
        ("short_code", pa.string()),      # own 3-letter code (doesn't depend on any API)
        ("league", pa.string()),
        ("country", pa.string()),
        ("country_flag_iso2", pa.string()),  # e.g. "ES", "PT" -> to use a flag instead of a crest
        ("football_data_org_id", pa.string()),
        ("api_football_id", pa.string()),
        ("is_promoted_2026_27", pa.bool_()),
    ]
)

MATCHES_SILVER_SCHEMA = pa.schema(
    list(MATCHES_BRONZE_SCHEMA)
    + [
        ("home_team_key", pa.string()),   # canonical team_key resolved against teams_master
        ("away_team_key", pa.string()),
        ("result", pa.string()),          # "H" / "D" / "A"
        ("goal_difference", pa.int32()),  # home_score - away_score
    ]
)


TEAM_RATINGS_SCHEMA = pa.schema([
    ("league", pa.string()),
    ("season", pa.string()),
    ("matchday", pa.int32()),
    ("team_key", pa.string()),
    ("as_of", pa.timestamp("ms", tz="UTC")),
    ("attack", pa.float64()),
    ("defense", pa.float64()),
    ("n_matches", pa.int32()),
    ("n_train", pa.int32()),
    ("prior_applied", pa.bool_()),
    ("is_warmup", pa.bool_()),
    ("is_provisional", pa.bool_()),
    ("mu", pa.float64()),
    ("gamma", pa.float64()),
    ("rho", pa.float64()),
    ("converged", pa.bool_()),
])

MATCH_PREDICTIONS_SCHEMA = pa.schema([
    ("league", pa.string()),
    ("season", pa.string()),
    ("matchday", pa.int32()),
    ("match_date", pa.timestamp("ms", tz="UTC")),
    ("home_team_key", pa.string()),
    ("away_team_key", pa.string()),
    ("lambda_home", pa.float64()),
    ("lambda_away", pa.float64()),
    ("p_home", pa.float64()),
    ("p_draw", pa.float64()),
    ("p_away", pa.float64()),
    ("result", pa.string()),
    ("status", pa.string()),
    ("as_of", pa.timestamp("ms", tz="UTC")),
    ("is_warmup", pa.bool_()),
    ("is_provisional", pa.bool_()),
])

SEASON_SIMULATIONS_SCHEMA = pa.schema([
    ("league", pa.string()),
    ("season", pa.string()),
    ("as_of_matchday", pa.int32()),
    ("team_key", pa.string()),
    ("prob_champion", pa.float64()),
    ("prob_champions_league", pa.float64()),
    ("prob_champions_qualifying", pa.float64()),
    ("prob_relegation", pa.float64()),
    ("prob_relegation_playoff", pa.float64()),
    ("avg_position", pa.float64()),
    ("n_simulations", pa.int32()),
    ("simulated_at", pa.timestamp("us")),
])