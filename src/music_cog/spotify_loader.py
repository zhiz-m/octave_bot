import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Union
from music_cog.song import Song
import asyncio

class SpotifyLoader(spotipy.Spotify):
    def __init__(self):
        super().__init__(client_credentials_manager=SpotifyClientCredentials(client_id='5f573c9620494bae87890c0f08a60293',client_secret='212476d9b0f3472eaa762d90b19b0ba8'))
    
    # will only get a single artist
    def load_playlist(self, url: str) -> Union[list[Song], None]:
        try:
            data = self.playlist_tracks(url)
        except:
            return
        
        entries = data.get("items")
        if not entries:
            return
        
        songs = list()

        for entry in entries:
            title = entry["track"]["name"]
            artist = entry["track"]["artists"][0]["name"]
            duration = entry["track"]["duration_ms"] // 1000
            info = {
                "duration": duration,
                "title": title,
                "artist": artist
            }
            songs.append(Song(info))
        
        return songs
    
    @staticmethod
    async def load_spotify_playlist(url: str, loop: asyncio.BaseEventLoop):
        client = SpotifyLoader()
        songs = await loop.run_in_executor(None, client.load_playlist, url)
        return songs

