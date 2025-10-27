from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr
from enum import Enum
import requests


class SpotifyUserDataType(str, Enum):
    top_tracks = "top_tracks"
    top_artists = "top_artists"
    saved_shows = "saved_shows"
    saved_episodes = "saved_episodes"

    @classmethod
    def _missing_(cls, value):
        return cls.top_tracks


class SpotifyUserTimeRange(str, Enum):
    short_term = "short_term"  # last 4 weeks
    medium_term = "medium_term"  # last 6 months
    long_term = "long_term"  # all time

    @classmethod
    def _missing_(cls, value):
        return cls.medium_term


class SpotifyUserDataToolInput(BaseModel):
    data_type: str = Field(
        default=SpotifyUserDataType.top_tracks,
        description="One of ['top_tracks', 'top_artists', 'saved_shows', 'saved_episodes'].",
    )
    time_range: str = Field(
        default=SpotifyUserTimeRange.medium_term,
        description="For top items: one of ['short_term', 'medium_term', 'long_term']. Not used for saved_shows.",
    )
    limit: int = Field(
        default=10,
        description="Number of items to return (1-50).",
        ge=1,
        le=10,
    )


class SpotifyTasteProfileTool(BaseTool):
    name: str = "Spotify Taste Profile"
    description: str = (
        "Search for the user's taste profile. Returns the user's top tracks, top artists, saved shows (podcasts), or saved episodes (podcast episodes) from Spotify. "
    )
    args_schema: Type[BaseModel] = SpotifyUserDataToolInput

    def __init__(self, spotify_token=None, **kwargs):
        super().__init__(**kwargs)
        self.__dict__['_user_token'] = spotify_token
    
    @property
    def user_token(self):
        """Property to access the stored token"""
        return self.__dict__.get('_user_token')

    def _get_top_items(self, item_type: str, time_range: str, limit: int):
        """Fetch user's top tracks or artists."""
        url = f"https://api.spotify.com/v1/me/top/{item_type}"
        headers = {"Authorization": f"Bearer {self.user_token}"}
        params = {
            "time_range": time_range,
            "limit": limit,
            "offset": 0,
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"Spotify API error: {response.status_code}, {response.text}, User token: {self.user_token}"

        data = response.json()
        items = data.get("items", [])
        
        result = []
        for item in items:
            entry = {
                k: v
                for k, v in item.items()
                if k not in ("available_markets", "images", "album")
            }
            # Include simplified album info for tracks
            if "album" in item and item_type == "tracks":
                entry["album_name"] = item["album"].get("name")
                entry["album_artists"] = [a["name"] for a in item["album"].get("artists", [])]
                
            result.append(entry)

        return result

    def _get_saved_items(self, item_type: str, limit: int):
        """Fetch user's saved shows or episodes."""
        url = f"https://api.spotify.com/v1/me/{item_type}"
        headers = {"Authorization": f"Bearer {self.user_token}"}
        params = {
            "limit": limit,
            "offset": 0,
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"Spotify API error: {response.status_code}, {response.text}, User token: {self.user_token}"

        data = response.json()
        items = data.get("items", [])
        
        result = []
        for item in items:
            # Extract the nested object (show or episode)
            nested_item = item.get(item_type.rstrip('s'), {})  # 'shows' -> 'show', 'episodes' -> 'episode'
            entry = {
                k: v
                for k, v in nested_item.items()
                if k not in ("available_markets", "images", "html_description")
            }
            # Add when it was added
            entry["added_at"] = item.get("added_at")
            # Truncate description
            if "description" in entry:
                entry["description"] = entry["description"][:500]
            # For episodes, add show info
            if item_type == "episodes" and "show" in nested_item:
                entry["show_name"] = nested_item["show"].get("name")
                entry["show_publisher"] = nested_item["show"].get("publisher")
            result.append(entry)

        return result

    def _run(self, data_type: str, time_range: str = "medium_term", limit: int = 10) -> str:
        print(f"Running with spotify token {self.user_token}", flush=True)
        try:
            if data_type == "top_tracks":
                return self._get_top_items("tracks", time_range, limit)
            elif data_type == "top_artists":
                return self._get_top_items("artists", time_range, limit)
            elif data_type == "saved_shows":
                return self._get_saved_items("shows", limit)
            elif data_type == "saved_episodes":
                return self._get_saved_items("episodes", limit)
            else:
                return f"Unknown data_type: {data_type}. Use one of ['top_tracks', 'top_artists', 'saved_shows', 'saved_episodes']"

        except Exception as e:
            return f"Spotify User Data API error: {e}"