"""Standalone live-data client — stands in for a real IoT/telemetry feed.

Every ~10 seconds, for each of the dealer's vehicles, this generates a
plausible next reading (small drift in runtime/idle/fuel, small GPS jitter,
occasionally a larger "drift event" that pushes a machine outside its
geofence) and POSTs it to POST /api/telemetry/report on the running backend.
The backend does the actual DB update + re-runs alert/anomaly/maintenance
checks — this script only ever talks to the API, never touches the DB
directly, so it's a stand-in for exactly the kind of real feed described in
the project brief ("we will be providing live synthetic data").

Usage:
    python live_telemetry_client.py [--url http://127.0.0.1:8000] [--interval 10]
"""
import argparse
import random
import sys
import time

import requests

NORMAL_JITTER_DEG = 0.02
DRIFT_EVENT_PROBABILITY = 0.05
DRIFT_EVENT_JITTER_DEG = 0.09  # deliberately large enough to sometimes breach the 5km geofence


def _jitter(lat: float, lng: float, spread: float) -> tuple[float, float]:
    return lat + random.uniform(-spread, spread), lng + random.uniform(-spread, spread)


def fetch_fleet(base_url: str) -> list[dict]:
    resp = requests.get(f"{base_url}/api/equipment", timeout=10)
    resp.raise_for_status()
    return resp.json()


def next_reading(equipment: dict) -> dict:
    tenure = equipment.get("tenure") or {}
    base_lat = tenure.get("designated_lat") or equipment.get("gps_lat")
    base_lng = tenure.get("designated_lng") or equipment.get("gps_lng")

    if base_lat is None or base_lng is None:
        lat = lng = None
    else:
        spread = DRIFT_EVENT_JITTER_DEG if random.random() < DRIFT_EVENT_PROBABILITY else NORMAL_JITTER_DEG
        lat, lng = _jitter(base_lat, base_lng, spread)

    runtime = max(0.0, (equipment.get("runtime_hours") or 0) + random.uniform(0, 0.4))
    idle = max(0.0, (equipment.get("idle_hours") or 0) + random.uniform(-0.3, 0.5))
    fuel = max(0.0, (equipment.get("fuel_usage") or 0) + random.uniform(-1.0, 2.5))

    return {
        "equipment_code": equipment["equipment_code"],
        "lat": lat,
        "lng": lng,
        "fuel_usage": round(fuel, 1),
        "runtime_hours": round(runtime, 1),
        "idle_hours": round(idle, 1),
    }


def run(base_url: str, interval: int):
    print(f"Live telemetry client starting — posting to {base_url}/api/telemetry/report every {interval}s")
    print("Press Ctrl+C to stop.\n")

    tick = 0
    while True:
        tick += 1
        try:
            fleet = fetch_fleet(base_url)
        except requests.RequestException as e:
            print(f"[tick {tick}] Could not reach backend ({e}); retrying in {interval}s")
            time.sleep(interval)
            continue

        updated = 0
        for equipment in fleet:
            reading = next_reading(equipment)
            try:
                resp = requests.post(f"{base_url}/api/telemetry/report", json=reading, timeout=10)
                resp.raise_for_status()
                updated += 1
            except requests.RequestException as e:
                print(f"  ! failed to report {reading['equipment_code']}: {e}")

        print(f"[tick {tick}] reported {updated}/{len(fleet)} vehicles")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between ticks")
    args = parser.parse_args()

    try:
        run(args.url, args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
