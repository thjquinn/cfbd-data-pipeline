import os
import json

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert


# =========================================================
# Configuration
# =========================================================

load_dotenv()

API_KEY = os.getenv("CFBD_API_KEY")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# =========================================================
# Helper: log pipeline run
# =========================================================

def log_pipeline_run(
    pipeline_name,
    rows_pulled,
    rows_inserted,
    rows_updated,
    rows_rejected,
    status,
    error_message=None
):
    log_df = pd.DataFrame([{
        "pipeline_name": pipeline_name,
        "rows_pulled": rows_pulled,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "rows_rejected": rows_rejected,
        "status": status,
        "error_message": error_message
    }])

    log_df.to_sql(
        "pipeline_runs",
        engine,
        if_exists="append",
        index=False
    )


# =========================================================
# Helper: serialize nested API values
# =========================================================

def serialize_nested(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)

    return value


# =========================================================
# Pipeline
# =========================================================

rows_pulled = 0
rows_inserted = 0
rows_updated = 0
rows_rejected = 0

try:

    # -----------------------------------------------------
    # Extract games from CFBD
    # -----------------------------------------------------

    all_games = []

    for year in range(2015, 2026):

        print(f"Pulling {year} games...")

        response = requests.get(
            "https://api.collegefootballdata.com/games",
            headers=headers,
            params={"year": year},
            timeout=60
        )

        response.raise_for_status()

        games = response.json()

        print(f"  Found {len(games):,} games")

        if games:
            year_df = pd.DataFrame(games)
            all_games.append(year_df)

    if not all_games:
        raise ValueError("CFBD returned no game data.")

    # -----------------------------------------------------
    # Combine seasons
    # -----------------------------------------------------

    games_df = pd.concat(
        all_games,
        ignore_index=True
    )

    rows_pulled = len(games_df)

    print()
    print(f"Total games pulled: {rows_pulled:,}")

    # -----------------------------------------------------
    # Validate required API columns
    # -----------------------------------------------------

    required_columns = [
        "id",
        "season",
        "homeId",
        "awayId",
        "homeTeam",
        "awayTeam"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in games_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # -----------------------------------------------------
    # Reject invalid rows
    # -----------------------------------------------------

    invalid_mask = (
        games_df["id"].isna()
        | games_df["season"].isna()
        | games_df["homeId"].isna()
        | games_df["awayId"].isna()
        | games_df["homeTeam"].isna()
        | games_df["awayTeam"].isna()
    )

    invalid_games_df = games_df[
        invalid_mask
    ].copy()

    rows_rejected = len(invalid_games_df)

    games_df = games_df[
        ~invalid_mask
    ].copy()

    print(f"Rejected games: {rows_rejected:,}")
    print(f"Valid games: {len(games_df):,}")

    # -----------------------------------------------------
    # Transform fields
    # -----------------------------------------------------

    games_df["startDate"] = pd.to_datetime(
        games_df["startDate"],
        utc=True,
        errors="coerce"
    )

    for column in games_df.columns:
        games_df[column] = games_df[column].map(
            serialize_nested
        )

    # -----------------------------------------------------
    # Determine insert vs update counts
    # -----------------------------------------------------

    existing_ids_df = pd.read_sql(
        "SELECT id FROM games",
        engine
    )

    existing_ids = set(
        existing_ids_df["id"].tolist()
    )

    source_ids = set(
        games_df["id"].tolist()
    )

    new_ids = source_ids - existing_ids
    existing_source_ids = source_ids & existing_ids

    rows_inserted = len(new_ids)
    rows_updated = len(existing_source_ids)

    print()
    print("--- UPSERT CHECK ---")
    print(f"New games: {rows_inserted:,}")
    print(f"Existing games to update: {rows_updated:,}")

    # -----------------------------------------------------
    # Prepare PostgreSQL table
    # -----------------------------------------------------

    metadata = MetaData()

    games_table = Table(
        "games",
        metadata,
        autoload_with=engine
    )

    # -----------------------------------------------------
    # Upsert in chunks
    # -----------------------------------------------------

    chunk_size = 1000

    print()
    print("Upserting games into PostgreSQL...")

    for start in range(
        0,
        len(games_df),
        chunk_size
    ):

        chunk_df = games_df.iloc[
            start:start + chunk_size
        ].copy()

        # Convert pandas NaN / NaT values into Python None
        chunk_df = chunk_df.astype(object).where(
            pd.notna(chunk_df),
            None
        )

        records = chunk_df.to_dict(
            orient="records"
        )

        stmt = insert(
            games_table
        ).values(records)

        update_columns = {
            column.name: stmt.excluded[column.name]
            for column in games_table.columns
            if column.name != "id"
        }

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_columns
        )

        with engine.begin() as connection:
            connection.execute(upsert_stmt)

        end = min(
            start + chunk_size,
            len(games_df)
        )

        print(
            f"  Processed {end:,} / "
            f"{len(games_df):,} games"
        )

    # -----------------------------------------------------
    # Log successful pipeline run
    # -----------------------------------------------------

    log_pipeline_run(
        pipeline_name="games_load",
        rows_pulled=rows_pulled,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_rejected=rows_rejected,
        status="success"
    )

    # -----------------------------------------------------
    # Verify database
    # -----------------------------------------------------

    query = """
    SELECT
        season,
        COUNT(*) AS number_of_games
    FROM games
    GROUP BY season
    ORDER BY season;
    """

    check_df = pd.read_sql(
        query,
        engine
    )

    print()
    print("--- DATABASE CONTENTS ---")
    print(check_df)

    print()
    print("Games pipeline completed successfully.")

# =========================================================
# Failure handling
# =========================================================

except Exception as error:

    print()
    print("GAMES PIPELINE FAILED")
    print(str(error))

    try:
        log_pipeline_run(
            pipeline_name="games_load",
            rows_pulled=rows_pulled,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_rejected=rows_rejected,
            status="failed",
            error_message=str(error)
        )

    except Exception as logging_error:
        print(
            "Could not write failure to pipeline_runs:"
        )
        print(str(logging_error))

    raise