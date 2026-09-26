"""
setup_data_lake.py
-------------------
Módulo 1 — arranque del Data Lake local.

Qué hace:
1. Crea el árbol de carpetas completo (bronze/silver/gold/reference) para
   ambas ligas y las 4 temporadas (3 históricas estáticas + la activa
   2026-2027).
2. Siembra en `bronze/` y `silver/` un archivo `matches.parquet` VACÍO pero
   con el esquema correcto (ver src/utils/schema.py) en cada partición
   liga-temporada QUE TODAVÍA NO EXISTA. Si la partición ya tiene datos
   reales (como el bronze ya extraído con Football_Data_Extraction.ipynb),
   se salta y no la toca — este guard es lo que permite correr este script
   después de haber extraído datos reales, sin perderlos.
3. Siembra `reference/teams_master.parquet` con los equipos ascendidos
   2026-2027 ya cargados desde config/leagues.yaml (Módulo 2 arranca
   con esto ya resuelto, en vez de descubrirlo más adelante).

Ejecutar desde la raíz del proyecto (importante: usa rutas relativas):
    python setup_data_lake.py
"""

from pathlib import Path

import pyarrow as pa
import yaml

from src.utils.parquet_io import write_partition
from src.utils.schema import MATCHES_BRONZE_SCHEMA, TEAMS_MASTER_SCHEMA

LAKE_ROOT = Path("data")
CONFIG_PATH = Path("config/leagues.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def empty_table(schema: pa.Schema) -> pa.Table:
    """Tabla vacía pero tipada — clave para que pyarrow no tenga que adivinar tipos después."""
    return pa.table({name: pa.array([], type=field.type) for name, field in zip(schema.names, schema)}, schema=schema)


def build_folder_tree(config: dict) -> None:
    layers_with_seasons = ["bronze", "silver"]  # gold se genera desde el modelo, no se siembra vacío aquí

    for league_key, league_cfg in config["leagues"].items():
        all_seasons = league_cfg["historical_seasons"] + [league_cfg["active_season"]]

        for layer in layers_with_seasons:
            for season in all_seasons:
                partition_dir = LAKE_ROOT / layer / league_key / f"season={season}"
                out_path = partition_dir / "matches.parquet"

                # Guard: si ya hay datos reales en esta partición (ej. bronze ya
                # extraído con Football_Data_Extraction.ipynb), no lo sobreescribimos
                # con una tabla vacía.
                if out_path.exists():
                    print(f"  [{layer}] {league_key} / {season} -> ya existe, no se sobreescribe")
                    continue

                write_partition(empty_table(MATCHES_BRONZE_SCHEMA), out_path)
                tag = "ACTIVA (on-demand)" if season == league_cfg["active_season"] else "histórica (estática)"
                print(f"  [{layer}] {league_key} / {season} [{tag}] -> {out_path}")

    # gold/ se crea vacío de estructura (sin parquet sembrado) porque su
    # contenido depende del modelo Dixon-Coles (Módulo 3), no de la ingesta.
    for sub in ["team_strength", "match_features", "simulations"]:
        (LAKE_ROOT / "gold" / sub).mkdir(parents=True, exist_ok=True)


def seed_teams_master(config: dict) -> None:
    out_path = LAKE_ROOT / "reference" / "teams_master.parquet"

    # Mismo guard: si ya se sembró (o ya se curó a mano con más equipos que
    # los ascendidos), no lo pisamos.
    if out_path.exists():
        print(f"\n  [reference] teams_master ya existe, no se sobreescribe -> {out_path}")
        return

    rows = {name: [] for name in TEAMS_MASTER_SCHEMA.names}

    for league_key, league_cfg in config["leagues"].items():
        promoted = set(league_cfg.get("promoted_2026_27", []))
        for team_name in promoted:
            rows["team_key"].append(team_name.lower().replace(" ", "_"))
            rows["official_name"].append(team_name)
            rows["short_code"].append("")  # se completa a mano/curado, no se inventa un código
            rows["league"].append(league_key)
            rows["country"].append(league_cfg["country"])
            rows["country_flag_iso2"].append(league_cfg["country_flag_iso2"])
            rows["football_data_org_id"].append(None)
            rows["api_football_id"].append(None)
            rows["is_promoted_2026_27"].append(True)

    table = pa.table(rows, schema=TEAMS_MASTER_SCHEMA)
    write_partition(table, out_path)
    print(f"\n  [reference] teams_master sembrado con {table.num_rows} equipos ascendidos -> {out_path}")


def main() -> None:
    config = load_config()
    print("Creando árbol del Data Lake...\n")
    build_folder_tree(config)
    seed_teams_master(config)
    print("\nListo. Estructura creada bajo ./data/")


if __name__ == "__main__":
    main()
