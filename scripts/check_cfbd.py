import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CFBD_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

url = "https://api.collegefootballdata.com/games"

params = {
    "year": 2025
}

response = requests.get(
    url,
    headers=headers,
    params=params
)

response.raise_for_status()

games = response.json()

print(f"Games returned: {len(games)}")
print(games[0])