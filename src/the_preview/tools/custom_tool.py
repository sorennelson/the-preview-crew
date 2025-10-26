from .spotify_auth import get_spotify_token
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from enum import Enum

from openai import OpenAI
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
            limit = 5
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
                # Copy all top-level fields except available_markets and images
                entry = {k: v for k, v in item.items() if k not in ("available_markets", "images", "html_description")}
                # If a 'description' is present, shrink to 1000 characters
                if "description" in entry and entry["description"]:
                    entry["description"] = entry["description"][:1000]
                
                result.append(entry)

            return result

        except Exception as e:
            print(f"Spotify API error: {e}")
            return f"Spotify API error: {e}"
        
        return str(response.json())


class ImageGenerationInput(BaseModel):
    """Input schema for OpenAI Image Generation Tool."""
    
    prompt: str = Field(..., description="Text description of the image to generate.")


class OpenAIImageGenerationTool(BaseTool):
    name: str = "OpenAI Image Generation"
    description: str = (
        "Generates images using OpenAI's API based on a text prompt. "
        "Returns the URL of the generated image."
    )
    args_schema: Type[BaseModel] = ImageGenerationInput
    openai_api_key: str = None
    file_path: str = None
    outbound_file_path: str = None

    def __init__(self, openai_api_key: str, file_path: str, outbound_file_path: str):
        super().__init__()
        self.openai_api_key = openai_api_key
        self.file_path = file_path
        self.outbound_file_path = outbound_file_path

    def _generate_random_hash(self, prompt: str = "") -> str:
        """Generate a random hash for filename"""
        timestamp = str(int(time.time() * 1000))  # milliseconds
        random_data = f"{timestamp}_{prompt}_{self.openai_api_key[:8]}"
        return hashlib.md5(random_data.encode()).hexdigest()

    def _upload_base64_image(self, b64_data: str, prompt: str = "") -> str:
        """Upload base64 image data and return the URL"""
        
        try:
            # Generate random filename
            filename = f"{self._generate_random_hash(prompt)}.png"
            
            # Ensure the images directory exists
            images_dir = os.path.join(self.file_path, "images")
            os.makedirs(images_dir, exist_ok=True)
            
            image_path = os.path.join(images_dir, filename)
            with open(image_path, "wb") as f:
                f.write(base64.b64decode(b64_data))

            outbound_file_path = os.path.join(self.outbound_file_path, "images", filename)

            return outbound_file_path
                
        except Exception as e:
            # Return placeholder URL if upload fails
            print(f"Error uploading image: {str(e)}")
            return None

    def _run(self, prompt: str) -> str:
        try:
            if not self.file_path:
                return "Error generating image"

            # Create client instance for each request
            client = OpenAI(api_key=self.openai_api_key)
            response = client.images.generate(
                model="gpt-image-1-mini",
                prompt=prompt,
                size="1024x1024",
                quality="low",
            )
            
            # Get base64 data from response
            b64_data = response.data[0].b64_json

            # Upload the image and get URL
            image_url = self._upload_base64_image(b64_data, prompt)
            return f"<IMAGE:{image_url}>" if image_url else "Error generating image"
            
        except Exception as e:
            return f"Error generating image: {str(e)}"
