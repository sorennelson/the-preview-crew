from tools.custom_tool import SpotifyToolInput, SpotifySearchType, OpenAIImageGenerationTool
import os
# tool = SpotifyToolInput(query="One Dance", search_type=SpotifySearchType.album)
# print(tool)


image_tool = OpenAIImageGenerationTool(openai_api_key=os.getenv("OPENAI_API_KEY"), file_path="/Users/sorennelson/Documents/Dev/The Preview/the_preview/files")
result = image_tool._run(prompt="A surreal landscape of floating islands")
print(result)

