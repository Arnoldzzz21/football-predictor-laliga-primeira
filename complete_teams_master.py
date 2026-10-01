"""
complete_teams_master.py
Completes teams_master.parquet: fills in football_data_org_id/short_code for
the 5 already-existing promoted teams (by name, no duplicates are created) and
adds the rest of the LaLiga (PD) and Primeira Liga (PPL) teams with
is_promoted_2026_27=False.
Run from the project root: python complete_teams_master.py
"""
import os
import re
import time
import requests
import pandas as pd
import pyarrow as pa
from pathlib import Path
import sys

sys.path.append("src")
from utils.schema import TEAMS_MASTER_SCHEMA
from utils.parquet_io import read_partition, write_partition

TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
if not TOKEN:
    raise RuntimeError("FOOTBALL_DATA_TOKEN is not set in the environment variables")

HEADERS = {"X-Auth-Token": TOKEN}
BASE_URL = "https://api.football-data.org/v4/competitions/{code}/teams"
LEAGUE_META = {
    "laliga":        {"code": "PD",  "country": "Spain",    "flag": "ES"},
    "primeira_liga": {"code": "PPL", "country": "Portugal", "flag": "PT"},
}
TEAMS_MASTER_PATH = Path("data/reference/teams_master.parquet")
SCHEMA_COLS = [f.name for f in TEAMS_MASTER_SCHEMA]


def slugify(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name.lower(), flags=re.UNICODE).strip("_")


def fetch_teams(code: str) -> list[dict]:
    resp = requests.get(BASE_URL.format(code=code), headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["teams"]


def main():
    existing = read_partition(TEAMS_MASTER_PATH).to_pandas()
    existing = existing[SCHEMA_COLS].copy()
    existing_keys = set(existing["team_key"])

    updates = {}
    new_rows = []

    for league, meta in LEAGUE_META.items():
        for t in fetch_teams(meta["code"]):
            key = slugify(t["name"])
            if key in existing_keys:
                updates[key] = (str(t["id"]), t.get("tla") or "")
                continue
            new_rows.append({
                "team_key": key,
                "official_name": t["name"],
                "short_code": t.get("tla") or "",
                "league": league,
                "country": meta["country"],
                "country_flag_iso2": meta["flag"],
                "football_data_org_id": str(t["id"]),
                "api_football_id": None,
                "is_promoted_2026_27": False,
            })
        time.sleep(6)

    print("Matches found for the promoted teams (review before continuing):")
    for key in existing_keys:
        if key in updates:
            print(f"  {key} -> football_data_org_id={updates[key][0]}, short_code={updates[key][1]}")
        else:
            print(f"  {key} -> NO MATCH by name, check manually")

    for key, (fdid, short_code) in updates.items():
        mask = existing["team_key"] == key
        existing.loc[mask, "football_data_org_id"] = fdid
        existing.loc[mask, "short_code"] = short_code

    combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)[SCHEMA_COLS]
    table = pa.Table.from_pandas(combined, schema=TEAMS_MASTER_SCHEMA, preserve_index=False)
    write_partition(table, TEAMS_MASTER_PATH)
    print(f"\nteams_master.parquet: {len(combined)} teams in total ({len(new_rows)} new)")


if __name__ == "__main__":
    main()
