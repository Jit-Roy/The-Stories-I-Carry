import sqlite3
import os

DB_NAME = "movies.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            tmdb_id INTEGER UNIQUE,
            title TEXT,
            poster_path TEXT,
            status TEXT, -- "watched" or "watch_later"
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            series_name TEXT
        )
    ''')
    
    # Simple migration: try adding the series_name column in case the db is older
    try:
        cursor.execute('ALTER TABLE movies ADD COLUMN series_name TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    
    conn.commit()
    conn.close()

def add_movie(tmdb_id, title, poster_path, status, series_name=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO movies (tmdb_id, title, poster_path, status, series_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (tmdb_id, title, poster_path, status, series_name))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        # If movie already exists, just update the status
        cursor.execute('''
            UPDATE movies SET status = ? WHERE tmdb_id = ?
        ''', (status, tmdb_id))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error adding movie: {e}")
        success = False
    finally:
        conn.close()
        
    return success

def remove_movie(tmdb_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM movies WHERE tmdb_id = ?', (tmdb_id,))
    conn.commit()
    conn.close()

def get_movies(status=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if status:
        cursor.execute('SELECT tmdb_id, title, poster_path, status, series_name FROM movies WHERE status = ? ORDER BY added_at DESC', (status,))
    else:
        cursor.execute('SELECT tmdb_id, title, poster_path, status, series_name FROM movies ORDER BY added_at DESC')
        
    movies = cursor.fetchall()
    conn.close()
    
    # Return as list of dicts for easier handling
    return [
        {
            "id": m[0],
            "title": m[1],
            "poster_path": m[2],
            "status": m[3],
            "series_name": m[4]
        }
        for m in movies
    ]

def set_series(tmdb_id, series_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # convert empty strings to None
    series_name = series_name.strip() if series_name and series_name.strip() else None
    cursor.execute('''
        UPDATE movies SET series_name = ? WHERE tmdb_id = ?
    ''', (series_name, tmdb_id))
    conn.commit()
    conn.close()
