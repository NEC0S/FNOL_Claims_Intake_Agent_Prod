import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("fnol.weather")

_HAIL_STORM_CODES = {96, 99}  # WMO weather interpretation codes: thunderstorm with hail


def _geocode_location(location: str) -> Optional[Dict[str, float]]:
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        return None
    return {"latitude": results[0]["latitude"], "longitude": results[0]["longitude"]}


def check_weather(location: str, incident_date_str: str, claimed_damage_type: str) -> Dict[str, Any]:
    geo = _geocode_location(location)
    if geo is None:
        return {
            "condition": "unknown",
            "source": "open-meteo",
            "matches_claim": None,
            "note": f"Could not geocode location {location!r}; weather cross-check skipped.",
        }

    resp = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": geo["latitude"],
            "longitude": geo["longitude"],
            "start_date": incident_date_str,
            "end_date": incident_date_str,
            "daily": "precipitation_sum,weathercode",
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    daily = resp.json().get("daily", {})
    codes = daily.get("weathercode") or []
    precip = (daily.get("precipitation_sum") or [None])[0]
    code = codes[0] if codes else None

    hail_or_storm = code in _HAIL_STORM_CODES
    condition = "storm_with_hail" if hail_or_storm else ("precipitation" if (precip or 0) > 0 else "clear")
    matches = hail_or_storm if claimed_damage_type == "hail" else True

    return {
        "condition": condition,
        "source": "open-meteo",
        "weather_code": code,
        "precipitation_mm": precip,
        "matches_claim": matches,
    }
