import os
import subprocess
import sys
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine


# =========================================================
# Configuration
# =========================================================

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

PIPELINE_STEPS = [
    {
        "name": "games",
        "script": "scripts/load_games.py"
    },
    {
        "name": "plays",
        "script": "scripts/load_plays.py"
    }
]


# =========================================================
# Helper: log overall pipeline run
# =========================================================

def log_master_run(
    start_timestamp,
    end_timestamp,
    status,
    completed_steps,
    error_message=None
):
    log_df = pd.DataFrame([{
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "status": status,
        "completed_steps": ",".join(completed_steps),
        "error_message": error_message
    }])

    log_df.to_sql(
        "pipeline_master_runs",
        engine,
        if_exists="append",
        index=False
    )


# =========================================================
# Helper: run one pipeline step
# =========================================================

def run_step(step_name, script_path):
    print()
    print("=" * 60)
    print(f"STARTING STEP: {step_name.upper()}")
    print("=" * 60)

    start_time = datetime.now()

    result = subprocess.run(
        [sys.executable, script_path],
        text=True
    )

    end_time = datetime.now()
    duration = end_time - start_time

    if result.returncode != 0:
        print()
        print(f"{step_name.upper()} FAILED")
        print(f"Duration: {duration}")

        raise RuntimeError(
            f"Pipeline step failed: {step_name}"
        )

    print()
    print(f"{step_name.upper()} COMPLETED")
    print(f"Duration: {duration}")


# =========================================================
# Main pipeline
# =========================================================

def main():

    pipeline_start = datetime.now()
    completed_steps = []

    print()
    print("=" * 60)
    print("CFBD PIPELINE STARTED")
    print("=" * 60)

    try:

        for step in PIPELINE_STEPS:

            run_step(
                step_name=step["name"],
                script_path=step["script"]
            )

            completed_steps.append(
                step["name"]
            )

        pipeline_end = datetime.now()
        total_duration = (
            pipeline_end - pipeline_start
        )

        log_master_run(
            start_timestamp=pipeline_start,
            end_timestamp=pipeline_end,
            status="success",
            completed_steps=completed_steps
        )

        print()
        print("=" * 60)
        print("CFBD PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print(
            f"Completed steps: "
            f"{', '.join(completed_steps)}"
        )

        print(
            f"Total duration: "
            f"{total_duration}"
        )

    except Exception as error:

        pipeline_end = datetime.now()

        total_duration = (
            pipeline_end - pipeline_start
        )

        try:
            log_master_run(
                start_timestamp=pipeline_start,
                end_timestamp=pipeline_end,
                status="failed",
                completed_steps=completed_steps,
                error_message=str(error)
            )

        except Exception as logging_error:
            print()
            print(
                "Could not write pipeline failure "
                "to pipeline_master_runs."
            )
            print(logging_error)

        print()
        print("=" * 60)
        print("CFBD PIPELINE FAILED")
        print("=" * 60)

        print(
            f"Completed steps: "
            f"{', '.join(completed_steps)}"
        )

        print(
            f"Error: "
            f"{error}"
        )

        print(
            f"Total duration: "
            f"{total_duration}"
        )

        sys.exit(1)


# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":
    main()