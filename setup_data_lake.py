"""
setup_data_lake.py
-------------------
Module 1 — local Data Lake bootstrap.

What it does:
1. Creates the full folder tree (bronze/silver/gold/reference) for both
   leagues and the 4 seasons (3 static historical ones + the active
   2026-2027 one).
2. Seeds `bronze/` and `silver/` with an EMPTY `matches.parquet` that has
   the correct schema (see src/utils/schema.py) in every league-season
   partition THAT DOESN'T EXIST YET. If the partition already has real data
   (such as the bronze already extracted with Football_Data_Extraction.ipynb),
   it is skipped and left untouched — this guard is what makes it safe to
   run this script after real data has been extracted, without losing it.
3. Seeds `reference/teams_master.parquet` with the 2026-2027 promoted teams
   already loaded from config/leagues.yaml (Module 2 starts with this
   already resolved, instead of discovering it later).

Run from the project root (important: it uses relative paths):
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
    """Empty but typed table — key so pyarrow doesn't have to guess types later."""
    return pa.table({name: pa.array([], type=field.type) for name, field in zip(schema.names, schema)}, schema=schema)


def build_folder_tree(config: dict) -> None:
    layers_with_seasons = ["bronze", "silver"]  # gold is generated from the model, it is not seeded empty here

    for league_key, league_cfg in config["leagues"].items():
        all_seasons = league_cfg["historical_seasons"] + [league_cfg["active_season"]]

        for layer in layers_with_seasons:
            for season in all_seasons:
                partition_dir = LAKE_ROOT / layer / league_key / f"season={season}"
                out_path = partition_dir / "matches.parquet"

                # Guard: if there is already real data in this partition (e.g.
                # bronze already extracted with Football_Data_Extraction.ipynb),
                # we don't overwrite it with an empty table.
                if out_path.exists():
                    print(f"  [{layer}] {league_key} / {season} -> already exists, not overwritten")
                    continue

                write_partition(empty_table(MATCHES_BRONZE_SCHEMA), out_path)
                tag = "ACTIVE (on-demand)" if season == league_cfg["active_season"] else "historical (static)"
                print(f"  [{layer}] {league_key} / {season} [{tag}] -> {out_path}")

    # gold/ is created as an empty structure (no seeded parquet) because its
    # content depends on the Dixon-Coles model (Module 3), not on ingestion.
    for sub in ["team_strength", "match_features", "simulations"]:
        (LAKE_ROOT / "gold" / sub).mkdir(parents=True, exist_ok=True)


def seed_teams_master(config: dict) -> None:
    out_path = LAKE_ROOT / "reference" / "teams_master.parquet"

    # Same guard: if it was already seeded (or already curated by hand with
    # more teams than just the promoted ones), we don't overwrite it.
    if out_path.exists():
        print(f"\n  [reference] teams_master already exists, not overwritten -> {out_path}")
        return

    rows = {name: [] for name in TEAMS_MASTER_SCHEMA.names}

    for league_key, league_cfg in config["leagues"].items():
        promoted = set(league_cfg.get("promoted_2026_27", []))
        for team_name in promoted:
            rows["team_key"].append(team_name.lower().replace(" ", "_"))
            rows["official_name"].append(team_name)
            rows["short_code"].append("")  # filled in by hand/curated, a code is not made up
            rows["league"].append(league_key)
            rows["country"].append(league_cfg["country"])
            rows["country_flag_iso2"].append(league_cfg["country_flag_iso2"])
            rows["football_data_org_id"].append(None)
            rows["api_football_id"].append(None)
            rows["is_promoted_2026_27"].append(True)

    table = pa.table(rows, schema=TEAMS_MASTER_SCHEMA)
    write_partition(table, out_path)
    print(f"\n  [reference] teams_master seeded with {table.num_rows} promoted teams -> {out_path}")


def main() -> None:
    config = load_config()
    print("Creating the Data Lake tree...\n")
    build_folder_tree(config)
    seed_teams_master(config)
    print("\nDone. Structure created under ./data/")


if __name__ == "__main__":
    main()
