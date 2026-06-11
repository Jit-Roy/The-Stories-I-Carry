import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("TMDB_API_KEY", "")

url = f"https://image.tmdb.org/t/p/w185/8cdWjvZQUExUUTzyp4v6EDclXz.jpg"
try:
    print("Testing image.tmdb.org...")
    r = requests.get(url, timeout=10)
    print("image.tmdb.org Status:", r.status_code)
except Exception as e:
    print("image.tmdb.org failed:", e)
