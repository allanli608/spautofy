from flask import Flask, redirect, request, session, url_for, render_template
from flask_session import Session
from spotipy import Spotify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from openai import OpenAI
from collections import Counter
import requests
from spotipy.exceptions import SpotifyException
from config import OPEN_AI_API_KEY, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, FLASK_SECRET_KEY

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY  # Change this to a random secret key

# Configure Flask-Session with server-side storage (filesystem in this example)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Spotify API credentials
SPOTIPY_CLIENT_ID = SPOTIFY_CLIENT_ID
SPOTIPY_CLIENT_SECRET = SPOTIFY_CLIENT_SECRET
SPOTIPY_REDIRECT_URI = "http://localhost:5000/callback"  # Update with your redirect URI

# OpenAI API key
OPENAI_API_KEY = OPEN_AI_API_KEY # Replace with your OpenAI API key

# Set up OpenAI API
client = OpenAI(api_key=OPENAI_API_KEY)

# Spotify OAuth configuration
sp_oauth = SpotifyOAuth(
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    SPOTIPY_REDIRECT_URI,
    scope="user-library-read playlist-modify-public playlist-modify-private user-read-private",
    cache_path=".spotipyoauthcache",
)

def create_spotify_client():
    token_info = sp_oauth.get_access_token()
    if token_info:
        spotify_token = token_info['access_token']
        return Spotify(auth=spotify_token, requests_timeout=10, retries=10)
    else:
        # Handle case when no access token is available
        return None

# Generalized genres list
generalized_genres = ["pop", "rap", "classical", "lo-fi", "breakcore", "indie"]

def majority_vote(matches):
    # Count the occurrences of each match
    match_counts = Counter(matches)

    # Find the most common match (mode)
    most_common_matches = match_counts.most_common()

    # Check if there is a clear majority or if it's a tie
    if len(most_common_matches) > 1 and most_common_matches[0][1] == most_common_matches[1][1]:
        # It's a tie, return all matching genres
        return [match[0] for match in most_common_matches]
    else:
        # Return the most common match
        return [most_common_matches[0][0]]

def add_songs_to_playlist(sp, playlist_id, track_uris):
    chunk_size = 100
    for i in range(0, len(track_uris), chunk_size):
        chunk = track_uris[i:i + chunk_size]
        sp.playlist_add_items(playlist_id, chunk)
        
# Home route
@app.route("/")
def index():
    if not session.get("token_info"):
        return render_template("index.html")
    return render_template("authenticated.html")

# /login route
@app.route("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# /callback route
@app.route("/callback")
def callback():
    token_info = sp_oauth.get_access_token(request.args["code"])
    session["token_info"] = token_info
    return redirect(url_for("index"))

# /logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# /stats route
@app.route("/stats")
def stats():
    if not session.get("token_info"):
        return redirect(url_for("login"))

    # Use create_spotify_client function to get the authenticated Spotify client
    sp = create_spotify_client()

    if not sp:
        return redirect(url_for("login"))

    limit = 30
    offset = 0
    track_data = []
    genre_data = []

    while True:
        try:
            results = sp.current_user_saved_tracks(limit=limit, offset=offset)
            tracks = results['items']
        except requests.exceptions.ReadTimeout:
            # Handle timeout error and retry
            print('Spotify timed out... trying again...')
            continue

        # Break the loop if no more tracks
        if not tracks:
            break

        # Extract track data
        for track in tracks:
            track_id = track['track']['id']
            track_name = track['track']['name']
            artist_id = track['track']['artists'][0]['id']
            artist_name = track['track']['artists'][0]['name']

            # Fetch artist genres using SpotifyOAuth
            artist_info = sp.artist(artist_id)
            artist_genres = artist_info['genres']

            track_data.append({
                'id': track_id,
                'name': track_name,
                'artist_id': artist_id,
                'artist_name': artist_name
            })

            genre_data.append(artist_genres)

        # Move to the next set of tracks
        offset += limit

    # Store genre_data in the session
    session["genre_data"] = genre_data
    session["track_data"] = track_data
    print(session["genre_data"])
    print(session["track_data"])
    return render_template("stats.html", track_data=track_data, genre_data=genre_data)

# /generalize route
@app.route("/generalize")
def generalize():
    # Retrieve genre_data from the session
    genre_data = session.get("genre_data", [])
    print(genre_data)
    generalized_genre_data = []

    for subgenres in genre_data:
        matching_genres = []

        if not subgenres:
            # If subgenres is empty, output "Other"
            generalized_genre_data.append(["Uncategorizable"])
            continue

        for subgenre in subgenres:
            # Check if any generalized genre is a substring of the subgenre
            matches = [gen for gen in generalized_genres if gen.lower() in subgenre.lower()]
            matching_genres.extend(matches)

        if matching_genres:
            # If there are matches, use the matching genres based on majority vote
            generalized_genre_data.append(majority_vote(matching_genres))
        else:
            # If no match, call OpenAI to determine the genre
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Output one of: rap, pop, lo-fi, breakcore, classical, indie. The output should best describe the inputted list of subgenres. Nothing else should be outputted."
                    },
                    {
                        "role": "user",
                        "content": str(subgenres)
                    }
                ],
                temperature=1,
                max_tokens=100,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            # Extract the generated genre from the OpenAI response
            generated_genre = response.choices[0].message.content
            print(f"Generated genre: {generated_genre}")
            
            # Append the generated genre to the result
            generalized_genre_data.append([generated_genre])

    # Store generalized_genre_data in the session
    session["generalized_genre_data"] = generalized_genre_data

    return render_template("generalize.html", generalized_data=generalized_genre_data)

@app.route("/make_playlists")
def make_playlists():
    # Retrieve data from the session
    generalized_genre_data = session.get("generalized_genre_data", [])
    track_data = session.get("track_data", [])
    # Define generalized genres
    generalized_genres = ["pop", "rap", "classical", "lo-fi", "breakcore", "indie"]

    # Initialize dictionaries to store song IDs for each genre
    playlist_songs = {genre: [] for genre in generalized_genres}
    uncategorizable_songs = []

    # Create Spotify client object
    sp = create_spotify_client()

    # Iterate through the generalized genres and populate the playlist_songs
    for i, genres in enumerate(generalized_genre_data):
        if (len(genres) == 1) and genres[0].lower() not in [g.lower() for g in generalized_genres]:
            uncategorizable_songs.append(track_data[i].get("id"))  # Add the song to uncategorizable list
        else:
            for genre in genres:
                # Check if the genre is in the generalized genres list
                if genre.lower() in [g.lower() for g in generalized_genres]:
                    # Check if the index i is within the range of track_data
                    if i < len(track_data):
                        playlist_songs[genre].append(track_data[i].get("id")) # Add the song to the corresponding genre list

 # Remove duplicates from each playlist
    for genre, songs in playlist_songs.items():
        playlist_songs[genre] = list(set(songs))

    # Create playlists and add songs to them
    playlists_with_genres = [(genre, []) for genre in generalized_genres]
    uncategorizable_songs_names = []

    # Create the uncategorizable playlist
    uncategorizable_playlist = None
    try:
        uncategorizable_playlist = sp.user_playlist_create(sp.me()['id'], name="Uncategorizable")
    except spotipy.SpotifyException as e:
        print(f"Error creating uncategorizable playlist: {e}")

    # Add songs to the uncategorizable playlist in chunks
    if uncategorizable_playlist:
        uncategorizable_track_uris = [f"spotify:track:{song}" for song in uncategorizable_songs]
        add_songs_to_playlist(sp, uncategorizable_playlist['id'], uncategorizable_track_uris)

        # Populate uncategorizable_songs_names with the song names
        uncategorizable_songs_names.extend([track['track']['name'] for track in sp.playlist_tracks(uncategorizable_playlist['id'])['items']])

    for genre, songs in playlist_songs.items():
        if songs:
            try:
                # Create a new playlist
                playlist = sp.user_playlist_create(sp.me()['id'], name=f"({genre})")

                # Add songs to the playlist in chunks
                add_songs_to_playlist(sp, playlist['id'], [f"spotify:track:{song}" for song in songs])

                # Retrieve the full playlist object
                full_playlist = sp.playlist(playlist['id'])
                playlists_with_genres[generalized_genres.index(genre)][1].extend([track['track']['name'] for track in full_playlist['tracks']['items']])
            except spotipy.SpotifyException as e:
                print(f"Error creating playlist for {genre}: {e}")

    print(uncategorizable_songs_names)
    # Render the make_playlists template with the playlists and uncategorizable songs
    return render_template("make_playlists.html", playlists=playlists_with_genres, uncategorizable_songs=uncategorizable_songs_names, genrelist=generalized_genres)

if __name__ == "__main__":
    app.run(debug=True)
