import requests

def get_spotify_token(client_id, client_secret):
    """
    Send a POST request to Spotify's API to get an access token using client credentials flow.
    
    Args:
        client_id (str): Your Spotify app's client ID
        client_secret (str): Your Spotify app's client secret
    
    Returns:
        dict: Response from Spotify API containing access token
    """
    url = "https://accounts.spotify.com/api/token"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return None
