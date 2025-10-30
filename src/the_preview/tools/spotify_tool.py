from .spotify_auth import get_spotify_token
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from enum import Enum
import hashlib, base64, time, os, requests


CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


class SpotifySearchType(str, Enum):
    track = "track"
    album = "album"
    artist = "artist"
    genre = "genre"
    playlist = "playlist"
    episode = "episode"
    show = "show"

    @classmethod
    def _missing_(cls, value):
        """Return default value if not found"""
        return cls.track


class SpotifyToolInput(BaseModel):
    """Combined input schema for SpotifyTool."""

    query: str = Field(..., description="Spotify search query.")
    search_type: str = Field(
        default=SpotifySearchType.track,
        description="One of ['track', 'album', 'artist', 'genre', 'playlist', 'episode', 'show']. Type of Spotify search query.",
    )


class SpotifyTool(BaseTool):
    name: str = "Spotify Search"
    description: str = (
        "Returns a list of music or podcasts (based on the given query type) by searching Spotify for the given search term."
    )
    args_schema: Type[BaseModel] = SpotifyToolInput
    _token_cache = {"access_token": None, "expires_at": 0}

    def _get_valid_token(self):
        now = time.time()
        if (
            self._token_cache["access_token"]
            and now < self._token_cache["expires_at"]
        ):
            return self._token_cache["access_token"]

        token_data = get_spotify_token(CLIENT_ID, CLIENT_SECRET)
        if not token_data:
            raise RuntimeError("Failed to get Spotify token")

        self._token_cache["access_token"] = token_data["access_token"]
        self._token_cache["expires_at"] = now + token_data["expires_in"] - 30
        return self._token_cache["access_token"]

    def _run(self, query: str, search_type: str) -> str:
        try:
            
            spotify_token = self._get_valid_token()

            url = "https://api.spotify.com/v1/search"
            headers = {"Authorization": f"Bearer {spotify_token}"}
            limit = 10
            params = {"q": query, "type": search_type, "limit": limit, "market": "US"}
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print("Spotify API error: reponse != 200", response)
                # raise Exception(
                #     f"Spotify API error: {response.status_code}, {response.text}"
                # )
                return f"Spotify API error: {response}"

            data = response.json()
            result = []
            key_map = {
                "track": "tracks",
                "album": "albums",
                "artist": "artists",
                "genre": "genres",
                "playlist": "playlists",
                "episode": "episodes",
                "show": "shows"
            }
            root_key = key_map.get(search_type, "tracks")
            items = data.get(root_key, {}).get("items", [])

            for item in items:
                if search_type == "track" and item.get("explicit"):
                  continue

                # Copy all top-level fields except available_markets and images
                entry = {k: v for k, v in item.items() if k not in ("available_markets", "images", "html_description", "album")}

                # Include simplified album info for tracks
                if "album" in item:
                    entry["album_name"] = item["album"].get("name")
                    entry["album_artists"] = [a["name"] for a in item["album"].get("artists", [])]

                # truncate description
                if "description" in entry and entry["description"]:
                    entry["description"] = entry["description"][:500]
                
                result.append(entry)

            return result

        except Exception as e:
            print(f"Spotify API error: {e}")
            return f"Spotify API error: {e}"


