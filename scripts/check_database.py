"""Smoke check: confirm the PostgreSQL connection works."""

from config import get_engine
from sqlalchemy import text


def main():
    with get_engine().connect() as connection:
        print(connection.execute(text("SELECT version();")).fetchone())


if __name__ == "__main__":
    main()
