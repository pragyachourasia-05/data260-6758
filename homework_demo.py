"""HW8 Part 1 demo: CREATE_LISTING -> GET_LISTING through the FastAPI wrapper and Kafka.

    python homework_demo.py

Needs the Kafka stack running (docker compose up -d kafka kafka-init listing-worker listing-api).
At the end it merges the client, API and worker logs for the two correlation_ids into one ordered sequence.
"""
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.kafka_listings import REQUEST_TOPIC, RESPONSE_TOPIC  # noqa: E402

API = "http://127.0.0.1:8458/kafka/listings"
RAW = Path(__file__).resolve().parent / "reports" / "hw08" / "raw"
client_lines: list[str] = []


def clog(event, **fields):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')} [CLIENT] {event} " + \
        " ".join(f"{k}={json.dumps(v)}" for k, v in fields.items())
    client_lines.append(line)
    print(line, flush=True)


def call(correlation_id, operation, data):
    clog("sending request via FastAPI", correlation_id=correlation_id, operation=operation, data=data)
    response = requests.post(API, json={"correlation_id": correlation_id, "operation": operation, "data": data},
                             timeout=30).json()
    clog("response received by client", correlation_id=response.get("correlation_id"), response=response)
    return response


def container_logs(name, since):
    out = subprocess.run(["docker", "logs", "--since", since, name], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return (out.stdout + out.stderr).splitlines()


def main():
    started = (datetime.now(timezone.utc) - timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Request topic : {REQUEST_TOPIC}\nResponse topic: {RESPONSE_TOPIC}\n")

    # 1-7: CREATE_LISTING
    cid_create = str(uuid.uuid4())
    print("== Step 1: correlation_id for CREATE_LISTING =", cid_create)
    listing = {"property_address": "455 S 5th St, San Jose, CA", "monthly_rent": 2350,
               "property_category": "Apartment",
               "listing_description": "2 bed / 1 bath near SJSU, in-unit laundry, one parking spot"}
    created = call(cid_create, "CREATE_LISTING", listing)
    listing_id = created.get("listing_id")
    print(f"== Step 7: generated listing_id = {listing_id}\n")

    # 8-9: GET_LISTING with that id
    cid_get = str(uuid.uuid4())
    print("== Step 8: correlation_id for GET_LISTING =", cid_get)
    fetched = call(cid_get, "GET_LISTING", {"listing_id": listing_id})

    # 10: show entity and check correlation ids
    print("\n== Step 10: retrieved listing")
    print(json.dumps(fetched.get("listing"), indent=2))
    checks = {
        "create_success": created.get("success") is True,
        "create_correlation_id_preserved": created.get("correlation_id") == cid_create,
        "get_success": fetched.get("success") is True,
        "get_correlation_id_preserved": fetched.get("correlation_id") == cid_get,
        "round_trip_matches": fetched.get("listing", {}).get("listing_id") == listing_id
        and all(fetched["listing"].get(k) == v for k, v in listing.items()),
    }
    for name, ok in checks.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")

    # Error responses also keep the correlation_id
    print("\n== Error cases")
    errors = []
    for op, data in [("GET_LISTING", {"listing_id": str(uuid.uuid4())}),
                     ("CREATE_LISTING", {**listing, "monthly_rent": -5}),
                     ("DELETE_LISTING", {"listing_id": listing_id})]:
        cid = str(uuid.uuid4())
        r = requests.post(API, json={"correlation_id": cid, "operation": op, "data": data}, timeout=30).json()
        errors.append({"operation": op, "sent_correlation_id": cid, "response": r})
        print(f"  {op:15s} -> {json.dumps(r)}  (correlation_id preserved: {r.get('correlation_id') == cid})")

    # Full sequence from all three processes, ordered by timestamp
    wanted = (cid_create, cid_get)
    lines = client_lines + container_logs("s6758_listing_api", started) + container_logs("s6758_listing_worker", started)
    # stable sort on the timestamp only, so lines from one process keep their own order
    seq = sorted((ln for ln in lines if any(c in ln for c in wanted) and ln[:4].isdigit()), key=lambda ln: ln[:27])
    print("\n== Full sequence saved to reports/hw08/raw/part1_sequence.log (show it: python homework_demo.py --sequence)")

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part1_demo.json").write_text(json.dumps({"create": {"correlation_id": cid_create, "response": created},
                                                    "get": {"correlation_id": cid_get, "response": fetched},
                                                    "errors": errors, "checks": checks}, indent=2), encoding="utf-8")
    (RAW / "part1_sequence.log").write_text("\n".join(seq) + "\n", encoding="utf-8")
    return 0 if all(checks.values()) else 1


def show_sequence():
    """Print the saved CREATE -> GET sequence; message bodies are cut so each step fits on one line."""
    print("CREATE_LISTING -> GET_LISTING (client + FastAPI + worker logs, ordered by time)\n")
    for ln in (RAW / "part1_sequence.log").read_text(encoding="utf-8").splitlines():
        print(re.sub(r" (message|response|data)=[{].*$", "", ln))


if __name__ == "__main__":
    raise SystemExit(show_sequence() if "--sequence" in sys.argv else main())
