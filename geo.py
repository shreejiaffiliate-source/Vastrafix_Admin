import requests

address = "Vavol, Gujarat, India"

def get_lat_lng_from_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }

    response = requests.get(url, params=params, headers={
        "User-Agent": "your-app-name"
    })

    data = response.json()
    if not data:
        return None, None

    return float(data[0]["lat"]), float(data[0]["lon"])