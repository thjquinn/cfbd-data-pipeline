"""Export a team ratings snapshot for the Streamlit app.

Per FBS team (latest season with data): season-average offensive PPA, season-average
defensive PPA allowed, and the most recent postgame Elo. The app uses these to
prefill model inputs so it does not need a database connection.
"""

from pathlib import Path

import pandas as pd
from config import get_engine

APP_DIR = Path(__file__).resolve().parent.parent / "app"

QUERY = """
WITH elo AS (
    SELECT DISTINCT ON (team) team, conference, season, elo
    FROM (
        SELECT home_team AS team, home_conference AS conference, season, start_date,
               home_postgame_elo AS elo
        FROM vw_games WHERE home_postgame_elo IS NOT NULL
        UNION ALL
        SELECT away_team, away_conference, season, start_date, away_postgame_elo
        FROM vw_games WHERE away_postgame_elo IS NOT NULL
    ) t
    ORDER BY team, start_date DESC
)
SELECT e.team, e.conference, e.season,
       p.avg_ppa AS off_ppa,
       p.avg_ppa_allowed AS def_ppa_allowed,
       e.elo
FROM elo e
JOIN vw_team_season_profile p ON p.team = e.team AND p.season = e.season
WHERE e.season = (SELECT MAX(season) FROM vw_games WHERE home_postgame_elo IS NOT NULL)
ORDER BY e.team
"""


def main():
    df = pd.read_sql(QUERY, get_engine()).dropna()
    APP_DIR.mkdir(exist_ok=True)
    df.round(4).to_csv(APP_DIR / "team_ratings.csv", index=False)
    print(f"Wrote {len(df)} teams (season {df.season.iloc[0]})")


if __name__ == "__main__":
    main()
