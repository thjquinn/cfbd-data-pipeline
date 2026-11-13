"""Smoke check: confirm the CFBD API key works."""

import requests
from config import get_api_headers


def main():
    response = requests.get(
        "https://api.collegefootballdata.com/games",
        headers=get_api_headers(),
        params={"year": 2025},
        timeout=60,
    )

    response.raise_for_status()

    games = response.json()

    print(f"Games returned: {len(games)}")

    if games:
        print(games[0])


if __name__ == "__main__":
    main()
