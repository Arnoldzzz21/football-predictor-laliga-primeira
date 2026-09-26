import pandas as pd


def resolve_team_key(df: pd.DataFrame, teams_master: pd.DataFrame) -> pd.DataFrame:
    """
    Map home_team_id/away_team_id (source ids, from Bronze) to the
    canonical team_key using teams_master.football_data_org_id as
    the join key. Raises if any team id fails to resolve, since an
    unresolved id usually means a coverage gap in teams_master.
    """
    id_to_key = dict(
        zip(teams_master["football_data_org_id"], teams_master["team_key"])
    )

    df = df.copy()
    df["home_team_key"] = df["home_team_id"].map(id_to_key)
    df["away_team_key"] = df["away_team_id"].map(id_to_key)

    unresolved = df[df["home_team_key"].isna() | df["away_team_key"].isna()]
    if not unresolved.empty:
        raise ValueError(
            f"{len(unresolved)} matches have unresolved team ids. "
            "Check teams_master coverage before continuing."
        )

    return df