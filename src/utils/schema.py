"""
schema.py
---------
Esquemas pyarrow explícitos por tabla. Se definen a mano (en vez de dejar
que pandas/pyarrow infieran el tipo) porque en fútbol es muy fácil que una
temporada sin partidos jugados todavía (2026-2027 al día de hoy) tenga
columnas enteras de nulls (home_score, away_score, xg) y la inferencia
automática las tipe como `null`/`string` en vez de `int32`/`float32` —
eso rompe la concatenación entre temporadas más adelante (`read_league_all_seasons`).
"""

import pyarrow as pa

# Capa BRONZE: datos crudos, un renglón = un partido, tal como llega de la
# fuente (API o scraping), con mínima transformación (solo tipado y el
# nombre de columna estandarizado — NO limpieza de nombres de equipo, eso
# es trabajo de bronze_to_silver.py).
MATCHES_BRONZE_SCHEMA = pa.schema(
    [
        ("league", pa.string()),          # "laliga" | "primeira_liga"
        ("season", pa.string()),          # "2023-2024" ... "2026-2027"
        ("matchday", pa.int32()),         # jornada
        ("match_date", pa.timestamp("s", tz="UTC")),
        ("home_team", pa.string()),       # nombre tal como lo entrega la fuente
        ("away_team", pa.string()),
        ("home_team_id", pa.string()),    # id de la fuente (para cruzar con teams_master)
        ("away_team_id", pa.string()),
        ("home_score", pa.int32()),       # null si aún no se juega
        ("away_score", pa.int32()),
        ("status", pa.string()),          # SCHEDULED | LIVE | FINISHED | POSTPONED
        ("home_xg", pa.float32()),        # null si la fuente no lo entrega en el plan usado
        ("away_xg", pa.float32()),
        ("source", pa.string()),          # "football_data_org" | "api_football" | "scraping:<sitio>"
    ]
)

# Tabla de referencia (capa `reference/`, no versionada por temporada):
# mapea nombres/ids que cambian entre fuentes al mismo equipo canónico, y
# guarda metadata de club-safe (nombre oficial, siglas, colores/bandera del
# país — nunca el escudo) para el Módulo 1 (estrategia anti-copyright) y
# el Módulo 2 (ascendidos).
TEAMS_MASTER_SCHEMA = pa.schema(
    [
        ("team_key", pa.string()),        # id canónico interno, estable entre temporadas
        ("official_name", pa.string()),   # nombre oficial completo
        ("short_code", pa.string()),      # sigla de 3 letras propia (no depende de ninguna API)
        ("league", pa.string()),
        ("country", pa.string()),
        ("country_flag_iso2", pa.string()),  # ej. "ES", "PT" -> para usar bandera en vez de escudo
        ("football_data_org_id", pa.string()),
        ("api_football_id", pa.string()),
        ("is_promoted_2026_27", pa.bool_()),
    ]
)

MATCHES_SILVER_SCHEMA = pa.schema(
    list(MATCHES_BRONZE_SCHEMA)
    + [
        ("home_team_key", pa.string()),   # team_key canónico resuelto contra teams_master
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