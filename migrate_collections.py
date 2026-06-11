import sqlite3
import tmdb_api

DB_NAME = "movies.db"

def migrate_collections():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get all movies that don't have a series name set yet
    cursor.execute('SELECT tmdb_id, title FROM movies WHERE series_name IS NULL')
    movies = cursor.fetchall()
    
    print(f"Found {len(movies)} movies to check for collections...")
    
    updates = 0
    for tmdb_id, title in movies:
        print(f"Checking '{title}'...")
        details = tmdb_api.get_movie_details(tmdb_id)
        if details and details.get("series_name"):
            series_name = details["series_name"]
            print(f"  -> Found collection: {series_name}")
            cursor.execute('UPDATE movies SET series_name = ? WHERE tmdb_id = ?', (series_name, tmdb_id))
            updates += 1
            
    conn.commit()
    conn.close()
    print(f"Migration complete! Updated {updates} movies with their official TMDB collection names.")

if __name__ == "__main__":
    migrate_collections()
