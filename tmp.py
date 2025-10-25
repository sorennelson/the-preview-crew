
import requests

host = "http://127.0.0.1"
port = "8000"
movie_title = "What should I do on my trip to Vegas"

res = requests.get(f"{host}:{port}/{movie_title}")
print(res.json())