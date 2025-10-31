"""Simulate persistent cache behavior for station search keys.

This script mirrors the radius normalization and cache key generation logic used
in `app/main.py` and demonstrates that with canonical buckets [5000,10000,15000]
persistent cache keys are stable for repeated visits to the same rounded coords.

It does NOT require Redis; it uses an in-memory dict to simulate set/get.
"""
from math import radians, sin, cos, asin, sqrt
from typing import List, Tuple

# canonical radius buckets
RADIUS_STANDARDS = [5000, 10000, 15000]

# emulate settings.CACHE_COORD_ROUND_DECIMALS used in app/core/config.py
CACHE_COORD_ROUND_DECIMALS = 8


def normalize_radius(requested_radius: float, standards: List[int] = RADIUS_STANDARDS) -> int:
    try:
        rr = int(round(float(requested_radius)))
    except Exception:
        rr = int(requested_radius)
    return next((r for r in standards if rr <= r), standards[-1])


def haversine_distance_m(lat1, lon1, lat2, lon2):
    # return distance in meters
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))


def make_cache_keys(lat: float, lon: float, radius: float, page: int = 1, limit: int = 20) -> Tuple[str, str, int]:
    lat_round = round(lat, CACHE_COORD_ROUND_DECIMALS)
    lon_round = round(lon, CACHE_COORD_ROUND_DECIMALS)
    actual_radius = normalize_radius(radius)
    cache_key = f"stations:lat{lat_round}:lon{lon_round}:r{actual_radius}:p{page}:l{limit}"
    persistent_key = f"stations_persistent:lat{lat_round}:lon{lon_round}:r{actual_radius}:p{page}:l{limit}"
    return cache_key, persistent_key, actual_radius


def simulate_visit(store: dict, lat: float, lon: float, radius: float, page: int =1, limit: int =20, payload=None):
    cache_key, persistent_key, actual_radius = make_cache_keys(lat, lon, radius, page, limit)
    hit = persistent_key in store
    if hit:
        return True, persistent_key, store[persistent_key], actual_radius
    else:
        # simulate writing a static snapshot (exclude dynamic fields)
        store[persistent_key] = payload or {"stations": [{"station_id": "S1", "lat": str(lat), "lon": str(lon)}], "note": "persisted"}
        return False, persistent_key, store[persistent_key], actual_radius


if __name__ == "__main__":
    # in-memory store
    store = {}

    # scenario 1: user visits region A with radius 4500 (maps to 5000)
    lat_a = 37.551
    lon_a = 126.988
    radius_a = 4500
    print("-- First visit: region A, radius=4500 --")
    hit, key, val, actual = simulate_visit(store, lat_a, lon_a, radius_a)
    print(f"hit={hit}, key={key}, actual_radius={actual}")
    print(f"stored_value={val}\n")

    # user navigates away and returns with same coords and same requested radius
    print("-- Return visit: region A, radius=4500 --")
    hit2, key2, val2, actual2 = simulate_visit(store, lat_a, lon_a, radius_a)
    print(f"hit={hit2}, key={key2}, actual_radius={actual2}")
    print(f"retrieved_value={val2}\n")

    # scenario 2: user uses slightly different coords within rounding tolerance
    lat_a2 = 37.5510000001
    lon_a2 = 126.9880000002
    print("-- Slightly different coords (within rounding) --")
    hit3, key3, val3, actual3 = simulate_visit(store, lat_a2, lon_a2, radius_a)
    print(f"hit={hit3}, key={key3}, actual_radius={actual3}")
    print(f"retrieved_value={val3}\n")

    # scenario 3: visit with larger radius 12000 (maps to 15000)
    print("-- Visit with radius=12000 (maps to 15000) --")
    hit4, key4, val4, actual4 = simulate_visit(store, lat_a, lon_a, 12000)
    print(f"hit={hit4}, key={key4}, actual_radius={actual4}")
    print(f"stored_value={val4}\n")

    # scenario 4: check distance filtering: a station at ~6km should be excluded when requested radius=4500
    # place station at ~6km away (approx) by shifting latitude
    lat_far = 37.605
    lon_far = 126.988
    d = haversine_distance_m(lat_a, lon_a, lat_far, lon_far)
    print(f"distance to far station ~{int(d)} m")
    # simulate that persistent store contains both stations
    store_key = make_cache_keys(lat_a, lon_a, radius_a)[1]
    store[store_key] = {"stations": [{"station_id": "S1", "lat": str(lat_a), "lon": str(lon_a)}, {"station_id": "S2", "lat": str(lat_far), "lon": str(lon_far)}]}
    # On retrieval we would compute distances and filter by user radius (4500)
    filtered = []
    for s in store[store_key]["stations"]:
        dist = haversine_distance_m(lat_a, lon_a, float(s["lat"]), float(s["lon"]))
        if dist <= radius_a:
            filtered.append((s["station_id"], int(dist)))
    print(f"stations within requested radius (4500): {filtered}")
