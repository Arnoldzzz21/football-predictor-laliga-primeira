"""
parquet_io.py
--------------
Read/write helpers for the local Data Lake (Bronze/Silver/Gold).

Design decisions:
- ZSTD compression by default (better ratio than Snappy for match data,
  which is very repetitive: team names, leagues, status). Snappy remains
  available as a fallback if read speed is ever prioritized over disk
  size.
- Physical partitioning by league/season via folders (Hive-style), NOT by
  a column inside a single file. This is key for Module 1: it lets the
  "on-demand" update of the 2026-2027 season rewrite ONLY that partition
  without touching or reading the historical seasons.
- Each write adds an `_ingested_at` column (lineage) if it doesn't exist,
  so we can audit when each row entered the lake.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DEFAULT_COMPRESSION = "zstd"


def write_partition(
    table: pa.Table,
    path: Path,
    compression: str = DEFAULT_COMPRESSION,
    add_lineage: bool = True,
) -> Path:
    """
    Writes a full table as ONE parquet file at `path`.
    Overwrites the whole partition (no append) -- that is the correct
    behavior for a "static season" partition, and also for the active
    2026-2027 partition on each on-demand refresh (it is replaced
    entirely, duplicates don't accumulate).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if add_lineage and "_ingested_at" not in table.column_names:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        lineage_col = pa.array([now] * table.num_rows, type=pa.string())
        table = table.append_column("_ingested_at", lineage_col)

    pq.write_table(table, path, compression=compression)
    return path


def read_partition(path: Path) -> pa.Table:
    if not path.exists():
        raise FileNotFoundError(f"Partition does not exist: {path}")
    # partitioning=None: each partition is ONE concrete file (not a directory
    # to scan). Without this, pyarrow tries to infer Hive columns from
    # "key=value" segments in the path (e.g. "season=2026-2027") and clashes
    # with the real "season" column that already lives inside the file --
    # that blows up with ArrowTypeError ("Unable to merge: Field season has
    # incompatible types: string vs dictionary<...>") in pyarrow >=17 when
    # building the dataset. Since here we always point at an exact file,
    # there is nothing to partition.
    return pq.read_table(path, partitioning=None)


def read_league_season(lake_root: Path, layer: str, league: str, season: str, filename: str = "matches.parquet") -> pa.Table:
    """
    Reads a single league+season partition from a given layer.
    Example: read_league_season(LAKE_ROOT, "bronze", "laliga", "2026-2027")
    """
    path = lake_root / layer / league / f"season={season}" / filename
    return read_partition(path)


def read_league_all_seasons(lake_root: Path, layer: str, league: str, filename: str = "matches.parquet") -> pa.Table:
    """
    Reads and concatenates ALL available seasons of a league in a layer.
    Useful for modeling (Dixon-Coles needs the full history), without
    treating the active season's on-demand file differently --
    it is simply included as one more partition.
    """
    league_dir = lake_root / layer / league
    tables = []
    for season_dir in sorted(league_dir.glob("season=*")):
        f = season_dir / filename
        if f.exists():
            # partitioning=None for the same reason as in read_partition().
            tables.append(pq.read_table(f, partitioning=None))
    if not tables:
        raise FileNotFoundError(f"No partitions found for {league} in {layer}")
    return pa.concat_tables(tables, promote_options="default")
