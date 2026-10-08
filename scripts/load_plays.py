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
# Pipeline
# =========================================================

rows_pulled = 0
rows_inserted = 0
rows_updated = 0
rows_rejected = 0

try:

    # -----------------------------------------------------
    # Extract plays from CFBD
    # -----------------------------------------------------

    all_plays = []

    year = 2025

    for week in range(1, 21):

        print(
            f"Pulling {year} week {week} plays..."
        )

        response = requests.get(
            "https://api.collegefootballdata.com/plays",
            headers=headers,
            params={
                "year": year,
                "week": week,
                "seasonType": "regular"
            },
            timeout=60
        )

        response.raise_for_status()

        plays = response.json()

        print(
            f"  Found {len(plays):,} plays"
        )

        if plays:
            week_df = pd.DataFrame(plays)
            all_plays.append(week_df)

    if not all_plays:
        raise ValueError(
            "CFBD returned no play data."
        )

    # -----------------------------------------------------
    # Combine weeks
    # -----------------------------------------------------

    plays_df = pd.concat(
        all_plays,
        ignore_index=True
    )

    rows_pulled = len(plays_df)

    print()
    print(
        f"Total plays pulled: "
        f"{rows_pulled:,}"
    )

    # -----------------------------------------------------
    # Rename API columns to database column names
    # -----------------------------------------------------

    plays_df = plays_df.rename(columns={
        "gameId": "game_id",
        "driveId": "drive_id",
        "driveNumber": "drive_number",
        "playNumber": "play_number",
        "offenseConference": "offense_conference",
        "offenseScore": "offense_score",
        "defenseConference": "defense_conference",
        "defenseScore": "defense_score",
        "offenseTimeouts": "offense_timeouts",
        "defenseTimeouts": "defense_timeouts",
        "yardsToGoal": "yards_to_goal",
        "yardsGained": "yards_gained",
        "playType": "play_type",
        "playText": "play_text"
    })

    # -----------------------------------------------------
    # Validate required API columns
    # -----------------------------------------------------

    required_columns = [
        "id",
        "game_id",
        "period",
        "play_type"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in plays_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: "
            f"{missing_columns}"
        )

    # -----------------------------------------------------
    # Reject invalid rows
    # -----------------------------------------------------

    invalid_mask = (
        plays_df["id"].isna()
        | plays_df["game_id"].isna()
    )

    invalid_plays_df = plays_df[
        invalid_mask
    ].copy()

    rows_rejected = len(
        invalid_plays_df
    )

    plays_df = plays_df[
        ~invalid_mask
    ].copy()

    print(
        f"Rejected plays: "
        f"{rows_rejected:,}"
    )

    print(
        f"Valid plays: "
        f"{len(plays_df):,}"
    )

    # -----------------------------------------------------
    # Transform nested clock field
    # -----------------------------------------------------

    plays_df["clock"] = plays_df[
        "clock"
    ].apply(
        lambda value:
        json.dumps(value)
        if isinstance(value, dict)
        else value
    )

    # -----------------------------------------------------
    # Convert wallclock to timestamp
    # -----------------------------------------------------

    plays_df["wallclock"] = pd.to_datetime(
        plays_df["wallclock"],
        utc=True,
        errors="coerce"
    )

    # -----------------------------------------------------
    # Determine insert vs update counts
    # -----------------------------------------------------

    existing_ids_df = pd.read_sql(
        "SELECT id FROM plays",
        engine
    )

    existing_ids = set(
        existing_ids_df["id"].tolist()
    )

    source_ids = set(
        plays_df["id"].tolist()
    )

    new_ids = source_ids - existing_ids
    existing_source_ids = source_ids & existing_ids

    rows_inserted = len(new_ids)
    rows_updated = len(existing_source_ids)

    print()
    print("--- UPSERT CHECK ---")

    print(
        f"New plays: "
        f"{rows_inserted:,}"
    )

    print(
        f"Existing plays to update: "
        f"{rows_updated:,}"
    )

    # -----------------------------------------------------
    # Prepare PostgreSQL table
    # -----------------------------------------------------

    metadata = MetaData()

    plays_table = Table(
        "plays",
        metadata,
        autoload_with=engine
    )

    # -----------------------------------------------------
    # Upsert in chunks
    # -----------------------------------------------------

    chunk_size = 5000

    print()
    print(
        "Upserting plays into PostgreSQL..."
    )

    for start in range(
        0,
        len(plays_df),
        chunk_size
    ):

        chunk_df = plays_df.iloc[
            start:start + chunk_size
        ].copy()

        # Convert pandas NaN / NaT values into None
        chunk_df = chunk_df.astype(object).where(
            pd.notna(chunk_df),
            None
        )

        records = chunk_df.to_dict(
            orient="records"
        )

        stmt = insert(
            plays_table
        ).values(records)

        update_columns = {
            column.name:
                stmt.excluded[column.name]
            for column in plays_table.columns
            if column.name != "id"
        }

        upsert_stmt = (
            stmt.on_conflict_do_update(
                index_elements=["id"],
                set_=update_columns
            )
        )

        with engine.begin() as connection:
            connection.execute(
                upsert_stmt
            )

        end = min(
            start + chunk_size,
            len(plays_df)
        )

        print(
            f"  Processed {end:,} / "
            f"{len(plays_df):,} plays"
        )

    # -----------------------------------------------------
    # Log successful pipeline run
    # -----------------------------------------------------

    log_pipeline_run(
        pipeline_name="plays_load",
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
        COUNT(*) AS total_plays,
        COUNT(DISTINCT game_id) AS total_games
    FROM plays;
    """

    check_df = pd.read_sql(
        query,
        engine
    )

    print()
    print("--- DATABASE CONTENTS ---")
    print(check_df)

    print()
    print(
        "Plays pipeline completed successfully."
    )

# =========================================================
# Failure handling
# =========================================================

except Exception as error:

    print()
    print("PLAYS PIPELINE FAILED")
    print(str(error))

    try:
        log_pipeline_run(
            pipeline_name="plays_load",
            rows_pulled=rows_pulled,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_rejected=rows_rejected,
            status="failed",
            error_message=str(error)
        )

    except Exception as logging_error:
        print(
            "Could not write failure to "
            "pipeline_runs:"
        )
        print(str(logging_error))

    raise