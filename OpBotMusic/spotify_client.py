"""Wrapper delgado sobre spotipy para leer que esta sonando en Spotify."""

import os
from dataclasses import dataclass
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "user-read-currently-playing user-read-playback-state"
CACHE_PATH = ".spotify_cache"


@dataclass
class TrackInfo:
    track_id: str
    name: str
    artist: str
    progress_ms: int
    duration_ms: int
    is_playing: bool

    @property
    def query(self) -> str:
        return f"{self.artist} - {self.name}"


def _build_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
        scope=SCOPE,
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


class SpotifyClient:
    def __init__(self) -> None:
        self._sp = _build_client()

    def get_current_playback(self) -> Optional[TrackInfo]:
        playback = self._sp.current_playback()
        if not playback or not playback.get("item"):
            return None

        item = playback["item"]
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        return TrackInfo(
            track_id=item["id"],
            name=item["name"],
            artist=artists,
            progress_ms=playback.get("progress_ms") or 0,
            duration_ms=item.get("duration_ms") or 0,
            is_playing=bool(playback.get("is_playing")),
        )
