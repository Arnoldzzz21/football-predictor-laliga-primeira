"""
parquet_io.py
--------------
Helpers de lectura/escritura para el Data Lake local (Bronze/Silver/Gold).

Decisiones de diseño:
- Compresión ZSTD por defecto (mejor ratio que Snappy para datos de partidos,
  que son muy repetitivos: nombres de equipo, ligas, status). Snappy queda
  disponible como fallback si en algún momento se prioriza velocidad de
  lectura sobre tamaño en disco.
- Particionado físico por liga/temporada vía carpetas (Hive-style), NO por
  columna dentro de un único archivo. Esto es clave para el Módulo 1: permite
  que la actualización "on-demand" de la temporada 2026-2027 reescriba
  SOLO esa partición sin tocar ni leer las temporadas históricas.
- Cada escritura agrega una columna `_ingested_at` (lineage) si no existe,
  para poder auditar cuándo entró cada fila al lake.
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
    Escribe una tabla completa como UN archivo parquet en `path`.
    Sobreescribe la partición completa (no hace append) — ese es el
    comportamiento correcto para una partición "temporada estática", y
    también para la partición activa 2026-2027 en cada refresh on-demand
    (se reemplaza completa, no se van acumulando duplicados).
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
        raise FileNotFoundError(f"No existe la partición: {path}")
    # partitioning=None: cada partición es UN archivo concreto (no un directorio
    # a escanear). Sin esto, pyarrow intenta inferir columnas Hive a partir de
    # segmentos "clave=valor" en la ruta (p. ej. "season=2026-2027") y choca con
    # la columna real "season" que ya vive dentro del archivo -- eso revienta
    # con ArrowTypeError ("Unable to merge: Field season has incompatible
    # types: string vs dictionary<...>") en pyarrow >=17 al construir el
    # dataset. Como aquí siempre apuntamos a un archivo exacto, no hay nada
    # que particionar.
    return pq.read_table(path, partitioning=None)


def read_league_season(lake_root: Path, layer: str, league: str, season: str, filename: str = "matches.parquet") -> pa.Table:
    """
    Lee una sola partición liga+temporada de una capa dada.
    Ejemplo: read_league_season(LAKE_ROOT, "bronze", "laliga", "2026-2027")
    """
    path = lake_root / layer / league / f"season={season}" / filename
    return read_partition(path)


def read_league_all_seasons(lake_root: Path, layer: str, league: str, filename: str = "matches.parquet") -> pa.Table:
    """
    Lee y concatena TODAS las temporadas disponibles de una liga en una capa.
    Útil para el modelado (Dixon-Coles necesita histórico completo), sin
    tocar el archivo on-demand de la temporada activa de forma distinta —
    simplemente se incluye como una partición más.
    """
    league_dir = lake_root / layer / league
    tables = []
    for season_dir in sorted(league_dir.glob("season=*")):
        f = season_dir / filename
        if f.exists():
            # partitioning=None por la misma razón que en read_partition().
            tables.append(pq.read_table(f, partitioning=None))
    if not tables:
        raise FileNotFoundError(f"No hay particiones para {league} en {layer}")
    return pa.concat_tables(tables, promote_options="default")
