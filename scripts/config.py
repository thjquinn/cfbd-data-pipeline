"""Shared configuration helpers for the CFBD pipeline scripts."""

import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()

DB_VARS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def require_env(*names):
    """Exit with a clear message if any environment variable is missing."""
    missing = [name for name in names if not os.getenv(name)]

    if missing:
        raise SystemExit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )


def get_api_headers():
    require_env("CFBD_API_KEY")
    return {"Authorization": f"Bearer {os.getenv('CFBD_API_KEY')}"}


def get_engine():
    require_env(*DB_VARS)

    url = URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )

    return create_engine(url)


def log_pipeline_run(
    engine,
    pipeline_name,
    rows_pulled,
    rows_inserted,
    rows_updated,
    rows_rejected,
    status,
    error_message=None,
):
    log_df = pd.DataFrame([{
        "pipeline_name": pipeline_name,
        "rows_pulled": rows_pulled,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "rows_rejected": rows_rejected,
        "status": status,
        "error_message": error_message,
    }])

    log_df.to_sql("pipeline_runs", engine, if_exists="append", index=False)
