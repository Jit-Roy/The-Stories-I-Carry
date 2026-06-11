import os
import requests
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.tmdb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/w1280"

import time

def _make_request(endpoint, params=None, retries=5):
    if not TMDB_API_KEY:
        print("Error: TMDB_API_KEY is not set.")
        return {}
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY
    headers = {
        "User-Agent": "WorldsIveWatched/1.0",
        "Accept": "application/json"
    }
    for attempt in range(retries):
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error on {endpoint}, retrying ({attempt+1}/{retries})...")
            time.sleep(1.5)
        except Exception as e:
            print(f"API Error ({endpoint}): {e}")
            break
            
    return {}

def _format_movie(item):
    poster = item.get("poster_path")
    backdrop = item.get("backdrop_path")
    return {
        "id": item.get("id"),
        "title": item.get("title") or item.get("name"),
        "poster_path": f"{IMAGE_BASE_URL}{poster}" if poster else None,
        "backdrop_path": f"{BACKDROP_BASE_URL}{backdrop}" if backdrop else None,
        "release_date": item.get("release_date"),
        "vote_average": item.get("vote_average")
    }

def search_movies(query, page=1):
    data = _make_request("/search/movie", {"query": query, "language": "en-US", "page": page, "include_adult": False})
    return [_format_movie(m) for m in data.get("results", [])]

def get_trending(page=1, time_window="day"):
    data = _make_request(f"/trending/movie/{time_window}", {"page": page})
    return [_format_movie(m) for m in data.get("results", [])]

def get_upcoming(page=1):
    data = _make_request("/movie/upcoming", {"language": "en-US", "page": page})
    return [_format_movie(m) for m in data.get("results", [])]

def get_top_rated(page=1):
    data = _make_request("/movie/top_rated", {"language": "en-US", "page": page})
    return [_format_movie(m) for m in data.get("results", [])]

def get_movie_details(movie_id):
    data = _make_request(f"/movie/{movie_id}", {"append_to_response": "credits,videos,similar"})
    if not data: return None
    movie = _format_movie(data)
    collection = data.get("belongs_to_collection")
    movie["series_name"] = collection.get("name") if isinstance(collection, dict) else None
    movie["genres"] = [g["name"] for g in data.get("genres", [])]
    movie["overview"] = data.get("overview")
    movie["runtime"] = data.get("runtime")
    movie["tagline"] = data.get("tagline", "")
    
    # Extended Facts
    movie["status"] = data.get("status", "Unknown")
    movie["budget"] = data.get("budget", 0)
    movie["revenue"] = data.get("revenue", 0)
    movie["original_language"] = data.get("original_language", "").upper()
    movie["homepage"] = data.get("homepage", "")
    movie["production_companies"] = [c["name"] for c in data.get("production_companies", [])]
    
    credits = data.get("credits", {})
    crew = credits.get("crew", [])
    cast = credits.get("cast", [])
    
    movie["director"] = next((member["name"] for member in crew if member.get("job") == "Director"), "Unknown")
    movie["cast"] = [member["name"] for member in cast[:10]]
    
    # Videos
    videos = data.get("videos", {}).get("results", [])
    movie["trailers"] = [v for v in videos if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]]
    
    # Similar
    similar_data = data.get("similar", {}).get("results", [])
    movie["similar"] = [_format_movie(m) for m in similar_data]
    
    return movie

def get_genres():
    data = _make_request("/genre/movie/list", {"language": "en-US"})
    return data.get("genres", [])

def get_movies_by_genre(genre_id, page=1):
    data = _make_request("/discover/movie", {"with_genres": genre_id, "language": "en-US", "page": page})
    return [_format_movie(m) for m in data.get("results", [])]

import database

def advanced_discover(params, page=1):
    # Extract 'show_me' filter locally, it's not a TMDB param
    show_me = params.pop("show_me", None)
    
    default_params = {"language": "en-US", "page": page}
    default_params.update(params)
    default_params["page"] = page
    
    data = _make_request("/discover/movie", default_params)
    results = [_format_movie(m) for m in data.get("results", [])]
    
    if show_me == "unseen":
        watched_movies = database.get_movies("watched")
        watched_ids = {m["id"] for m in watched_movies}
        results = [m for m in results if m["id"] not in watched_ids]
        
    return results
