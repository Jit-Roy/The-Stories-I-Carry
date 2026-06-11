import tmdb_api
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("TMDB_API_KEY", "")

print(f"API Key Length: {len(api_key)}")
print(f"Is v4 Token? {'Yes' if len(api_key) > 50 else 'No'}")

print("\n--- Testing /trending/movie/week ---")
trending = tmdb_api.get_trending()
print(f"Trending results count: {len(trending)}")

print("\n--- Testing /movie/top_rated ---")
top_rated = tmdb_api.get_top_rated()
print(f"Top Rated results count: {len(top_rated)}")

print("\n--- Testing /movie/upcoming ---")
upcoming = tmdb_api.get_upcoming()
print(f"Upcoming results count: {len(upcoming)}")

print("\n--- Testing /genre/movie/list ---")
genres = tmdb_api.get_genres()
print(f"Genres count: {len(genres)}")

print("\n--- Testing /search/movie ---")
search = tmdb_api.search_movies("inception")
print(f"Search results count: {len(search)}")
