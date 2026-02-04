import os
import time
import json
import sqlite3
import requests
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, Response


app = Flask(__name__)

# ==========================================
#               KONFIGURACJA
# ==========================================

# >>> TUTAJ WKLEJ SWÓJ KLUCZ <<<
TMDB_API_KEY = "Klucz_API" 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "movie_data.db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)

# ==========================================
#               BAZA DANYCH
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Dodano season_number
    conn.execute('''
        CREATE TABLE IF NOT EXISTS anime_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT UNIQUE NOT NULL,
            mal_id INTEGER,
            media_type TEXT,
            title TEXT,
            total_episodes INTEGER,
            season_number INTEGER DEFAULT 1,  -- NOWE POLE
            episode_number TEXT, 
            asset_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
#           FUNKCJE POMOCNICZE (TMDB)
# ==========================================

def download_image(image_url, tmdb_id, media_type):
    if not image_url: return None
    prefix = media_type if media_type else "unknown"
    filename = f"{prefix}_{tmdb_id}.jpg"
    save_path = os.path.join(ASSETS_DIR, filename)
    
    if os.path.exists(save_path): return f"assets/{filename}"
    
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
            return f"assets/{filename}"
    except Exception as e: print(f"Błąd obrazka: {e}")
    return None

def fetch_tmdb_details(tmdb_id, media_type=None):
    params = {'api_key': TMDB_API_KEY, 'language': 'pl-PL'}

    def try_fetch(m_type):
        try:
            url = f"{TMDB_BASE_URL}/{m_type}/{tmdb_id}"
            r = requests.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                poster = data.get('poster_path')
                return {
                    'title': data.get('title') if m_type == 'movie' else data.get('name'),
                    'episodes': 1 if m_type == 'movie' else data.get('number_of_episodes'),
                    'image_url': f"{TMDB_IMAGE_BASE}{poster}" if poster else None,
                    'media_type': m_type,
                    'found': True
                }
        except: pass
        return None

    if media_type: return try_fetch(media_type)
    
    res = try_fetch('movie')
    if res: return res
    res = try_fetch('tv')
    if res: return res
    return None

@app.route('/process_custom', methods=['POST'])
def process_custom():
    try:
        # Pobieramy dane z formularza (Multipart Form Data)
        title = request.form.get('title')
        media_type = request.form.get('media_type')
        files_json = request.form.get('files')
        
        # Plik okładki (opcjonalny)
        cover_file = request.files.get('cover')

        if not title or not files_json:
            return jsonify({'success': False, 'error': 'Brak tytułu lub plików'})

        files = json.loads(files_json)
        
        # Generujemy unikalne ujemne ID na podstawie czasu (timestamp)
        # Dzięki temu nigdy nie pokryje się z TMDB
        custom_id = int(time.time()) * -1 
        
        # Obsługa okładki
        asset_url = None
        if cover_file:
            # Zapisujemy jako custom_12345.jpg
            filename = f"custom_{abs(custom_id)}.jpg"
            save_path = os.path.join(ASSETS_DIR, filename)
            cover_file.save(save_path)
            asset_url = f"assets/{filename}"
        
        conn = get_db_connection()
        cnt = 0
        
        for f in files:
            # Domyślny sezon 1
            season_num = f.get('season_number', '1')
            if not season_num: season_num = '1'

            conn.execute('''
                INSERT INTO anime_files (filename, filepath, mal_id, media_type, title, total_episodes, season_number, episode_number, asset_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    mal_id=excluded.mal_id,
                    media_type=excluded.media_type,
                    title=excluded.title,
                    total_episodes=excluded.total_episodes,
                    season_number=excluded.season_number,
                    episode_number=excluded.episode_number,
                    asset_url=excluded.asset_url
            ''', (
                f['filename'], 
                f['filepath'], 
                custom_id,          # Nasze ujemne ID
                media_type,
                title, 
                len(files),         # Total episodes = ile plików dodajemy
                season_num,
                f.get('episode_number', ''), 
                asset_url
            ))
            cnt += 1
            
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'updated': cnt, 
            'data': {
                'title': title, 
                'asset_url': asset_url,
                'media_type': media_type
            }
        })

    except Exception as e:
        print(f"Custom Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
#               TRASY (ROUTES)
# ==========================================

@app.route('/')
def library():
    conn = get_db_connection()
    series = conn.execute('''
        SELECT mal_id, title, asset_url, media_type, COUNT(*) as file_count 
        FROM anime_files 
        WHERE mal_id IS NOT NULL 
        GROUP BY mal_id, media_type
        ORDER BY title
    ''').fetchall()
    conn.close()
    return render_template('library.html', series=series)

@app.route('/series/<string:tmdb_id>')
def series_details(tmdb_id):
    try:
        tmdb_id = int(tmdb_id)
    except ValueError:
        return "Błędne ID", 400

    conn = get_db_connection()
    
    # POPRAWKA: Usunąłem ", year" z tego zapytania poniżej:
    info = conn.execute('SELECT title, asset_url, total_episodes, media_type FROM anime_files WHERE mal_id = ? LIMIT 1', (tmdb_id,)).fetchone()
    
    episodes = conn.execute('''
        SELECT * FROM anime_files 
        WHERE mal_id = ? 
        ORDER BY season_number ASC, CAST(episode_number AS FLOAT) ASC
    ''', (tmdb_id,)).fetchall()
    conn.close()
    
    if not info and not episodes:
        return "Nie znaleziono takiej serii w bazie", 404

    return render_template('series.html', info=info, episodes=episodes)

@app.route('/delete_file/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    try:
        conn = get_db_connection()
        # Rozdzielamy to na dwie linie:
        conn.execute('DELETE FROM anime_files WHERE id = ?', (file_id,))
        conn.commit() # Teraz commit jest wywoływany poprawnie na połączeniu
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/watch/<int:file_id>')
def watch_video(file_id):
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM anime_files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    if not file: return "Nie znaleziono pliku", 404
    return render_template('player.html', file=file)

@app.route('/stream/<int:file_id>')
def stream_video(file_id):
    conn = get_db_connection()
    file_data = conn.execute('SELECT filepath FROM anime_files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    if not file_data or not os.path.exists(file_data['filepath']):
        return "Plik nie istnieje na dysku", 404
    return send_file(file_data['filepath'])

@app.route('/stream_remux/<int:file_id>')
def stream_remux(file_id):
    conn = get_db_connection()
    file_data = conn.execute('SELECT filepath FROM anime_files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    
    if not file_data or not os.path.exists(file_data['filepath']):
        return "Brak pliku", 404

    path = file_data['filepath']

    # FFmpeg: Kopiujemy wideo (h265), konwertujemy audio (aac), pakujemy w MP4
    cmd = [
        'ffmpeg',
        '-re',              # Czytaj w czasie rzeczywistym
        '-i', path,
        '-map', '0:v:0',    # Pierwszy strumień wideo
        '-map', '0:a:0',    # Pierwszy strumień audio
        '-c:v', 'copy',     # <--- 0% CPU usage na wideo (Kopiuj bit-w-bit)
        '-c:a', 'aac',      # Audio na AAC (przeglądarki to lubią)
        '-b:a', '192k',
        '-ac', '2',         # Stereo
        '-f', 'mp4',        # Kontener MP4 (dla Chrome'a)
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof', # Streaming mode
        'pipe:1'
    ]

    # Uruchom proces i przesyłaj wyjście prosto do przeglądarki
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

    def generate():
        try:
            while True:
                data = process.stdout.read(32 * 1024)
                if not data: break
                yield data
        finally:
            process.kill()

    return Response(generate(), mimetype='video/mp4')
# --- MANAGER ---

@app.route('/manager')
def manager():
    conn = get_db_connection()
    files = conn.execute('SELECT * FROM anime_files ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('manager.html', db_files=files)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route('/select_folder_dialog')
def select_folder_dialog():
    try:
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        path = filedialog.askdirectory(); root.destroy()
        return jsonify({'path': path})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/scan_folder', methods=['POST'])
def scan_folder():
    path = request.json.get('path')
    if not path or not os.path.exists(path): return jsonify({'error': 'Brak folderu'}), 400
    
    exts = ('.mkv', '.mp4', '.avi', '.mp3', '.flac', '.webm', '.mov', '.wmv')
    found = []
    conn = get_db_connection()
    try:
        for r, d, f in os.walk(path):
            for file in f:
                if file.lower().endswith(exts):
                    full = os.path.normpath(os.path.join(r, file))
                    db = conn.execute('SELECT * FROM anime_files WHERE filepath = ?', (full,)).fetchone()
                    item = {'filename': file, 'filepath': full, 'in_db': bool(db)}
                    if db:
                        item.update({
                            'title': db['title'], 
                            'episode_number': db['episode_number'], 
                            'season_number': db['season_number'], # ODCZYT SEZONU
                            'total_episodes': db['total_episodes'], 
                            'asset_url': db['asset_url'],
                            'media_type': db['media_type']
                        })
                    else:
                        item.update({'title': None, 'episode_number': None, 'season_number': 1, 'total_episodes': None, 'asset_url': None, 'media_type': None})
                    found.append(item)
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: conn.close()
    found.sort(key=lambda x: x['filename'])
    return jsonify({'files': found})

@app.route('/search_anime')
def search_tmdb():
    query = request.args.get('q')
    if not query: return jsonify({'results': []})
    
    url = f"{TMDB_BASE_URL}/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'pl-PL', 'include_adult': 'false'}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get('results', [])
            results = []
            for item in data:
                media_type = item.get('media_type')
                if media_type not in ['movie', 'tv']: continue
                
                is_movie = (media_type == 'movie')
                title = item.get('title') if is_movie else item.get('name')
                date = item.get('release_date') if is_movie else item.get('first_air_date')
                year = date[:4] if date else '????'
                poster = item.get('poster_path')
                
                results.append({
                    'mal_id': item['id'],
                    'title': title,
                    'image_url': f"{TMDB_IMAGE_BASE}{poster}" if poster else None,
                    'episodes': 'Film' if is_movie else 'Serial',
                    'year': year,
                    'media_type': media_type
                })
            return jsonify({'results': results})
    except: pass
    return jsonify({'results': []})

@app.route('/process_files', methods=['POST'])
def process_files():
    data = request.json
    tmdb_id = data.get('mal_id')
    media_type_hint = data.get('media_type') 
    files = data.get('files', [])

    if not tmdb_id or not files: return jsonify({'error': 'Błąd danych'}), 400
    
    tmdb_data = fetch_tmdb_details(tmdb_id, media_type_hint)
    if not tmdb_data or not tmdb_data['found']: return jsonify({'error': 'Nie znaleziono w TMDB'}), 404
    
    final_media_type = tmdb_data['media_type']
    asset = download_image(tmdb_data['image_url'], tmdb_id, final_media_type)
    
    conn = get_db_connection()
    cnt = 0
    
    for f in files:
        try:
            # Domyślnie sezon 1, jeśli pusty
            season_num = f.get('season_number', '1')
            if not season_num: season_num = '1'

            conn.execute('''
                INSERT INTO anime_files (filename, filepath, mal_id, media_type, title, total_episodes, season_number, episode_number, asset_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    mal_id=excluded.mal_id,
                    media_type=excluded.media_type,
                    title=excluded.title,
                    total_episodes=excluded.total_episodes,
                    season_number=excluded.season_number,
                    episode_number=excluded.episode_number,
                    asset_url=excluded.asset_url
            ''', (
                f['filename'], 
                f['filepath'], 
                tmdb_id, 
                final_media_type,
                tmdb_data['title'], 
                tmdb_data['episodes'],
                season_num,
                f.get('episode_number', ''), 
                asset
            ))
            cnt += 1
        except Exception as e:
            print(f"DB Error: {e}")
            pass
            
    conn.commit()
    conn.close()
    return jsonify({
        'success': True, 
        'updated': cnt, 
        'data': {
            'title': tmdb_data['title'], 
            'total_episodes': tmdb_data['episodes'], 
            'asset_url': asset,
            'media_type': final_media_type
        }
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
