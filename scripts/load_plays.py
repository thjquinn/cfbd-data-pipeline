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
# Backfill settings
# =========================================================

START_YEAR = 2021
END_YEAR = 2025

START_WEEK = 1
END_WEEK = 20

CHUNK_SIZE = 1000


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
# Helper: transform one season of plays
# =========================================================

def transform_plays(plays_df):

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
    # Validate required columns
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
            f"Missing required columns: {missing_columns}"
        )

    # -----------------------------------------------------
    # Reject rows missing critical identifiers
    # -----------------------------------------------------

    invalid_mask = (
        plays_df["id"].isna()
        | plays_df["game_id"].isna()
    )

    invalid_plays_df = plays_df[
        invalid_mask
    ].copy()

    valid_plays_df = plays_df[
        ~invalid_mask
    ].copy()

    # -----------------------------------------------------
    # Serialize nested clock object
    # -----------------------------------------------------

    valid_plays_df["clock"] = (
        valid_plays_df["clock"].apply(
            lambda value:
            json.dumps(value)
            if isinstance(value, dict)
            else value
        )
    )

    # -----------------------------------------------------
    # Convert wallclock to timestamp
    # -----------------------------------------------------

    valid_plays_df["wallclock"] = pd.to_datetime(
        valid_plays_df["wallclock"],
        utc=True,
        errors="coerce"
    )

    return valid_plays_df, invalid_plays_df


# =========================================================
# Pipeline counters
# =========================================================

total_rows_pulled = 0
total_rows_inserted = 0
total_rows_updated = 0
total_rows_rejected = 0


# =========================================================
# Main pipeline
# =========================================================

try:

    print()
    print("=" * 60)
    print("CFBD PLAY-BY-PLAY PIPELINE")
    print("=" * 60)

    print(
        f"Backfilling seasons "
        f"{START_YEAR}-{END_YEAR}"
    )

    # -----------------------------------------------------
    # Load existing play IDs once
    # -----------------------------------------------------

    print()
    print("Reading existing play IDs from PostgreSQL...")

    existing_ids_df = pd.read_sql(
        "SELECT id FROM plays",
        engine
    )

    existing_ids = set(
        existing_ids_df["id"].astype(str)
    )

    print(
        f"Existing plays in database: "
        f"{len(existing_ids):,}"
    )

    # -----------------------------------------------------
    # Prepare PostgreSQL plays table
    # -----------------------------------------------------

    metadata = MetaData()

    plays_table = Table(
        "plays",
        metadata,
        autoload_with=engine
    )

    # -----------------------------------------------------
    # Process one season at a time
    # -----------------------------------------------------

    for year in range(
        START_YEAR,
        END_YEAR + 1
    ):

        print()
        print("=" * 60)
        print(f"PROCESSING {year}")
        print("=" * 60)

        all_year_plays = []

        # -------------------------------------------------
        # Extract each week
        # -------------------------------------------------

        for week in range(
            START_WEEK,
            END_WEEK + 1
        ):

            print(
                f"Pulling {year} "
                f"week {week} plays..."
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

                week_df = pd.DataFrame(
                    plays
                )

                all_year_plays.append(
                    week_df
                )

        # -------------------------------------------------
        # Handle season with no returned data
        # -------------------------------------------------

        if not all_year_plays:

            print()
            print(
                f"No play data returned "
                f"for {year}."
            )

            continue

        # -------------------------------------------------
        # Combine season
        # -------------------------------------------------

        plays_df = pd.concat(
            all_year_plays,
            ignore_index=True
        )

        year_rows_pulled = len(
            plays_df
        )

        total_rows_pulled += (
            year_rows_pulled
        )

        print()
        print(
            f"{year} plays pulled: "
            f"{year_rows_pulled:,}"
        )

        # -------------------------------------------------
        # Transform + validate
        # -------------------------------------------------

        (
            plays_df,
            invalid_plays_df
        ) = transform_plays(
            plays_df
        )

        year_rows_rejected = len(
            invalid_plays_df
        )

        total_rows_rejected += (
            year_rows_rejected
        )

        print(
            f"Rejected plays: "
            f"{year_rows_rejected:,}"
        )

        print(
            f"Valid plays: "
            f"{len(plays_df):,}"
        )

        # -------------------------------------------------
        # Convert IDs to strings
        # -------------------------------------------------

        plays_df["id"] = (
            plays_df["id"].astype(str)
        )

        # -------------------------------------------------
        # Determine insert vs update counts
        # -------------------------------------------------

        source_ids = set(
            plays_df["id"]
        )

        new_ids = (
            source_ids
            - existing_ids
        )

        existing_source_ids = (
            source_ids
            & existing_ids
        )

        year_rows_inserted = len(
            new_ids
        )

        year_rows_updated = len(
            existing_source_ids
        )

        total_rows_inserted += (
            year_rows_inserted
        )

        total_rows_updated += (
            year_rows_updated
        )

        print()
        print("--- UPSERT CHECK ---")

        print(
            f"New plays: "
            f"{year_rows_inserted:,}"
        )

        print(
            f"Existing plays to update: "
            f"{year_rows_updated:,}"
        )

        # -------------------------------------------------
        # Upsert in chunks
        # -------------------------------------------------

        print()
        print(
            f"Upserting {year} plays..."
        )

        for start in range(
            0,
            len(plays_df),
            CHUNK_SIZE
        ):

            chunk_df = plays_df.iloc[
                start:
                start + CHUNK_SIZE
            ].copy()

            # Convert pandas NaN / NaT to Python None
            chunk_df = (
                chunk_df
                .astype(object)
                .where(
                    pd.notna(chunk_df),
                    None
                )
            )

            records = (
                chunk_df.to_dict(
                    orient="records"
                )
            )

            stmt = insert(
                plays_table
            ).values(records)

            update_columns = {
                column.name:
                    stmt.excluded[
                        column.name
                    ]
                for column
                in plays_table.columns
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
                start + CHUNK_SIZE,
                len(plays_df)
            )

            print(
                f"  Processed "
                f"{end:,} / "
                f"{len(plays_df):,}"
            )

        # -------------------------------------------------
        # Update in-memory set
        # -------------------------------------------------

        existing_ids.update(
            source_ids
        )

        print()
        print(
            f"{year} completed successfully."
        )

    # =====================================================
    # Log successful pipeline run
    # =====================================================

    log_pipeline_run(
        pipeline_name="plays_load",
        rows_pulled=total_rows_pulled,
        rows_inserted=total_rows_inserted,
        rows_updated=total_rows_updated,
        rows_rejected=total_rows_rejected,
        status="success"
    )

    # =====================================================
    # Verify database
    # =====================================================

    query = """
    SELECT
        COUNT(*) AS total_plays,
        COUNT(DISTINCT game_id)
            AS total_games
    FROM plays;
    """

    check_df = pd.read_sql(
        query,
        engine
    )

    print()
    print("=" * 60)
    print("DATABASE CONTENTS")
    print("=" * 60)

    print(check_df)

    # -----------------------------------------------------
    # Show plays by season
    # -----------------------------------------------------

    season_query = """
    SELECT
        g.season,
        COUNT(p.id) AS total_plays,
        COUNT(DISTINCT p.game_id)
            AS games_with_plays
    FROM plays p
    JOIN games g
        ON p.game_id = g.id
    GROUP BY g.season
    ORDER BY g.season;
    """

    season_check_df = pd.read_sql(
        season_query,
        engine
    )

    print()
    print("--- PLAYS BY SEASON ---")
    print(season_check_df)

    # -----------------------------------------------------
    # Final summary
    # -----------------------------------------------------

    print()
    print("=" * 60)
    print("PLAY PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print(
        f"Total pulled: "
        f"{total_rows_pulled:,}"
    )

    print(
        f"Total inserted: "
        f"{total_rows_inserted:,}"
    )

    print(
        f"Total existing/upserted: "
        f"{total_rows_updated:,}"
    )

    print(
        f"Total rejected: "
        f"{total_rows_rejected:,}"
    )


# =========================================================
# Failure handling
# =========================================================

except Exception as error:

    print()
    print("=" * 60)
    print("PLAYS PIPELINE FAILED")
    print("=" * 60)

    print(str(error))

    try:

        log_pipeline_run(
            pipeline_name="plays_load",
            rows_pulled=total_rows_pulled,
            rows_inserted=total_rows_inserted,
            rows_updated=total_rows_updated,
            rows_rejected=total_rows_rejected,
            status="failed",
            error_message=str(error)
        )

    except Exception as logging_error:

        print()
        print(
            "Could not write failure "
            "to pipeline_runs:"
        )

        print(
            str(logging_error)
        )

    raise