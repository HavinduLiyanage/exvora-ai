from __future__ import annotations
from typing import Optional, Tuple, Dict
import time, math, random
from app.config import get_settings

_settings = get_settings()

# ------------------
# Simple in-process TTL cache
# key: (from_id, to_id, mode, depart_bucket_min)
# ------------------
_CACHE: Dict[tuple, tuple] = {}  # key -> (expires_at, duration_min, distance_km, source)

def _now() -> float:
    return time.time()

def _bucket_minutes(hhmm: str, bucket: int = 15) -> int:
    h, m = map(int, hhmm.split(":"))
    total = h * 60 + m
    return (total // bucket) * bucket

def _cache_get(key: tuple) -> Optional[tuple]:
    v = _CACHE.get(key)
    if not v: return None
    expires, dur, dist, source = v
    if _now() > expires:
        _CACHE.pop(key, None)
        return None
    return dur, dist, source

def _cache_set(key: tuple, dur: int, dist: float, source: str):
    ttl = int(_settings.TRANSFER_CACHE_TTL_SECONDS or 600)
    _CACHE[key] = (_now() + ttl, dur, dist, source)

# ------------------
# Heuristic fallback
# ------------------
def _heuristic_eta(from_place_id: str, to_place_id: str, mode: str) -> tuple[int, float, str]:
    # Very rough: vary to avoid identical outputs
    if mode.upper() == "WALK":
        minutes = random.randint(8, 22)
        km = round(minutes * 0.07, 2)  # ~4-5 km/h walking
    else:
        minutes = random.randint(10, 28)
        km = round(minutes * 0.25, 2)  # ~15 km/h avg urban w/ stops
    return minutes, km, "heuristic"

# ------------------
# Google client (lazy)
# ------------------
_gmaps = None
def _gmaps():
    global _gmaps
    if _gmaps is None:
        import googlemaps
        if not _settings.GOOGLE_MAPS_API_KEY:
            raise RuntimeError("GOOGLE_MAPS_API_KEY not set")
        _gmaps = googlemaps.Client(key=_settings.GOOGLE_MAPS_API_KEY)
    return _gmaps

def _google_eta(from_place_id: str, to_place_id: str, mode: str, depart_time_str: str) -> tuple[int, float, str]:
    # Use Distance Matrix: place_id:prefix
    g = _gmaps()
    origins = [f"place_id:{from_place_id}"]
    destinations = [f"place_id:{to_place_id}"]
    mode_l = mode.lower()
    # We don't set departure_time when walking; for driving, use 'now'
    depart = "now" if mode_l in ("drive", "driving") else None
    resp = g.distance_matrix(
        origins=origins,
        destinations=destinations,
        mode="driving" if mode_l in ("drive","driving") else "walking",
        departure_time=depart,
    )
    rows = resp.get("rows", [])
    if not rows or not rows[0].get("elements"):
        raise RuntimeError("No elements in Google response")
    el = rows[0]["elements"][0]
    if el.get("status") != "OK":
        raise RuntimeError(f"Google element status {el.get('status')}")
    dur_sec = el["duration"]["value"]
    meters = el["distance"]["value"]
    dur_min = max(1, int(math.ceil(dur_sec / 60)))
    km = round(meters / 1000.0, 2)
    return dur_min, km, "google_routes_live"

# ------------------
# Public API
# ------------------
# call_count limiter (per-process, reset heuristically each request by caller if needed)
_calls_this_request = 0

def reset_transfer_call_counter():
    global _calls_this_request
    _calls_this_request = 0

def verify(from_place_id: str, to_place_id: str, mode: str, depart_time: str) -> dict:
    """
    Returns: {"duration_minutes": int, "distance_km": float, "source": "google_routes_live"|"heuristic"}
    May raise RuntimeError if USE_GOOGLE_ROUTES=true and Google call hard-fails; caller should map to 424.
    """
    global _calls_this_request
    mode = (mode or "DRIVE").upper()
    depart_bucket = _bucket_minutes(depart_time or "09:00", 15)
    key = (from_place_id, to_place_id, mode, depart_bucket)

    # cache
    cached = _cache_get(key)
    if cached:
        dur, dist, src = cached
        return {"duration_minutes": dur, "distance_km": dist, "source": src}

    # choose backend
    if _settings.USE_GOOGLE_ROUTES:
        limit = int(_settings.TRANSFER_MAX_CALLS_PER_REQUEST or 30)
        if _calls_this_request >= limit:
            # fail "softly": fall back to heuristic
            dur, dist, src = _heuristic_eta(from_place_id, to_place_id, mode)
            _cache_set(key, dur, dist, src)
            return {"duration_minutes": dur, "distance_km": dist, "source": src}
        try:
            dur, dist, src = _google_eta(from_place_id, to_place_id, mode, depart_time)
            _calls_this_request += 1
            _cache_set(key, dur, dist, src)
            return {"duration_minutes": dur, "distance_km": dist, "source": src}
        except Exception as e:
            # Propagate: caller decides whether to 424 or fallback
            raise
    # fallback path
    dur, dist, src = _heuristic_eta(from_place_id, to_place_id, mode)
    _cache_set(key, dur, dist, src)
    return {"duration_minutes": dur, "distance_km": dist, "source": src}
