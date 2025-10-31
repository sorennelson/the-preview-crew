from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from enum import Enum

from openai import OpenAI
import hashlib, base64, time, os, requests

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
                model="gpt-image-1", # mini
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
