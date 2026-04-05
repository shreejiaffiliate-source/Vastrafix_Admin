# accounts/utils/geocoding.py

import requests
from django.conf import settings


def get_lat_lng(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        "address": address,
        "key": settings.GOOGLE_MAPS_API_KEY
    }

    response = requests.get(url, params=params).json()

    if response.get("status") == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]

    return None, None