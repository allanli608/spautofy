from flask import Flask, render_template, redirect, url_for, request, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time

app = Flask(__name__, template_folder='template')
app.secret_key = 'SDUGSOUDGHU2389261'

# Spotify API credentials
app.config['SPOTIPY_CLIENT_ID'] = '6692ee51d1fe43f1837fcd26ee450018'
app.config['SPOTIPY_CLIENT_SECRET'] = 'a89e6d1320784f5f8332b5fd20ab4997'
app.config['SPOTIPY_REDIRECT_URI'] = 'http://localhost:5000/callback'

# Constants: Benchmark audio features for each genre
BENCHMARKS = {
    'pop': {'danceability': 0.7, 'energy': 0.7, 'tempo': 120, 'valence': 0.6},
    'rap': {'danceability': 0.675, 'energy': 0.775, 'tempo': 100, 'valence': 0.5},
    'lofi': {'danceability': 0.5, 'energy': 0.35, 'tempo': 80, 'valence': 0.4},
    'indie': {'danceability': 0.5, 'energy': 0.5, 'tempo': 100, 'valence': 0.5},
    'jazz': {'danceability': 0.4, 'energy': 0.35, 'tempo': 90, 'valence': 0.4},
    'classical': {'danceability': 0.2, 'energy': 0.2, 'tempo': 60, 'valence': 0.25},
    'electronic': {'danceability': 0.7, 'energy': 0.8, 'tempo': 130, 'valence': 0.7}
}

# Set similarity threshold as a constant
SIMILARITY_THRESHOLD = 0.1

# Initialize Spotify API object
sp = None

def initialize_spotify_api():
    global sp
    sp_oauth = SpotifyOAuth(
        app.config['SPOTIPY_CLIENT_ID'],
        app.config['SPOTIPY_CLIENT_SECRET'],
        app.config['SPOTIPY_REDIRECT_URI'],
        scope='playlist-modify-private user-library-read playlist-read-private'
    )
    token_info = session.get('token_info')
    if token_info is None or 'access_token' not in token_info:
        return None
    
    # Check if the token has expired
    current_time = int(time.time())
    token_expiration = token_info.get('expires_at', 0)
    if current_time > token_expiration:
        return None

    sp = spotipy.Spotify(auth=token_info['access_token'])
    return sp

def analyze_song(song_id):
    audio_features = sp.audio_features(tracks=[song_id])
    return audio_features[0] if audio_features else None

def squared_difference(dict1, dict2):
    squared_diff = 0
    for feature in dict1.keys():
        if feature in dict2:
            value1 = dict1.get(feature, 0)
            value2 = dict2.get(feature, 0)
            if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
                squared_diff += (float(value1) - float(value2)) ** 2
    return squared_diff

def categorize_song(audio_features):
    min_difference = float('inf')
    best_genre = None
    for genre, benchmark in BENCHMARKS.items():
        squared_diff = squared_difference(audio_features, benchmark)
        if squared_diff < min_difference:
            min_difference = squared_diff
            best_genre = genre
    return best_genre

def create_private_playlist(name):
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, name, public=False)
    return playlist['id']

def add_songs_to_private_playlist(playlist_id, song_ids):
    sp.playlist_add_items(playlist_id, song_ids)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    sp_oauth = SpotifyOAuth(
        app.config['SPOTIPY_CLIENT_ID'],
        app.config['SPOTIPY_CLIENT_SECRET'],
        app.config['SPOTIPY_REDIRECT_URI'],
        scope='playlist-modify-private user-library-read playlist-read-private'
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth = SpotifyOAuth(
        app.config['SPOTIPY_CLIENT_ID'],
        app.config['SPOTIPY_CLIENT_SECRET'],
        app.config['SPOTIPY_REDIRECT_URI'],
        scope='playlist-modify-private user-library-read playlist-read-private'
    )
    token_info = sp_oauth.get_access_token(request.args['code'])
    session['token_info'] = token_info

    initialize_spotify_api()

    # Add a link/button to initiate categorization
    categorization_link = '<a href="/categorize">Start Categorization</a>'
    
    return f'Authentication successful! You can now {categorization_link}.'

@app.route('/categorize')
def categorize():
    if 'token_info' not in session or initialize_spotify_api() is None:
        return redirect(url_for('login'))

    limit = 50
    offset = 0
    liked_songs = []

    while True:
        results = sp.current_user_saved_tracks(offset=offset, limit=limit)
        if not results['items']:
            break  # No more tracks to retrieve
        liked_songs.extend(results['items'])
        offset += limit

    genre_song_ids = {genre: [] for genre in BENCHMARKS.keys()}

    for song in liked_songs:
        track = song['track']  # Get the 'track' dictionary
        audio_features = analyze_song(track['id'])  # Access 'id' within 'track'
        if audio_features:
            genre = categorize_song(audio_features)
            genre_song_ids[genre].append(track['id'])  # Access 'id' within 'track'

    for genre, song_ids in genre_song_ids.items():
        playlist_id = create_private_playlist(genre)
        add_songs_to_private_playlist(playlist_id, song_ids)
        print(f"Created private playlist '{genre.capitalize()}' and added {len(song_ids)} songs.")

    return 'Categorization completed!'

if __name__ == '__main__':
    app.run(debug=True)
