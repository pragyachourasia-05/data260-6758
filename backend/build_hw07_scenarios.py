"""HW7 Part 4: build the two bike-share scenario CSVs from public Bay Wheels trip data.

Source: https://s3.amazonaws.com/baywheels-data (Lyft's public monthly trip files).
Each scenario CSV is ONE hypothetical rider's trip history assembled from real trips
(real start/end times, durations and bike types), so the agent can decide month by month:

  payperuse   - a light rider: 8 short classic rides (3-12 min) per month, May 2020 - Aug 2026
  membership  - a heavy rider: 32 longer classic rides (20-60 min) per month, Jan 2025 - Aug 2026

Sampling is seeded (SEED = 6758). Each zip is downloaded to a temp file, sampled, then deleted.

    python backend/build_hw07_scenarios.py
"""
import hashlib
import io
import json
import re
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SEED = 6758
BUCKET = "https://s3.amazonaws.com/baywheels-data"
ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "reports" / "hw07" / "cases" / "bikeshare"
RAW = ROOT / "reports" / "hw07" / "raw"
COLS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name", "end_station_name"]
SCENARIOS = {
    "payperuse": {"first": "202005", "last": "202608", "per_month": 8, "min": 3, "max": 12},
    "membership": {"first": "202501", "last": "202608", "per_month": 32, "min": 20, "max": 60},
}


def list_monthly_files() -> dict[str, str]:
    xml = urllib.request.urlopen(BUCKET, timeout=60).read().decode()
    keys = re.findall(r"<Key>([^<]+)</Key>", xml)
    return {k[:6]: k for k in keys if re.match(r"^\d{6}-baywheels-tripdata\.csv\.zip$", k)}


def load_month(key: str) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(urllib.request.urlopen(f"{BUCKET}/{key}", timeout=300).read())
        path = Path(tmp.name)
    try:
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX"))
            df = pd.read_csv(io.BytesIO(zf.read(name)), usecols=lambda c: c in COLS, low_memory=False)
    finally:
        path.unlink()  # keep only the sampled rows
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    df["ended_at"] = pd.to_datetime(df["ended_at"], errors="coerce")
    df["minutes"] = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60
    # "docked_bike" (2020-2021 files) is the classic pedal bike
    return df[df["rideable_type"].isin(["classic_bike", "docked_bike"])].dropna(subset=["minutes"])


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    files = list_monthly_files()
    months = sorted(files)
    picked = {name: [] for name in SCENARIOS}
    log = []
    for month in months:
        wanted = [n for n, s in SCENARIOS.items() if s["first"] <= month <= s["last"]]
        if not wanted:
            continue
        df = load_month(files[month])
        for name in wanted:
            s = SCENARIOS[name]
            pool = df[(df["minutes"] >= s["min"]) & (df["minutes"] <= s["max"])]
            sample = pool.sample(n=min(s["per_month"], len(pool)), random_state=SEED + int(month))
            picked[name].append(sample)
            log.append({"month": month, "scenario": name, "file": files[month], "pool": int(len(pool)), "sampled": int(len(sample))})
        print(f"{month}: {len(df):>7} classic trips -> " + ", ".join(f"{n} +{SCENARIOS[n]['per_month']}" for n in wanted), flush=True)

    built = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for name, parts in picked.items():
        out = pd.concat(parts).sort_values("started_at")
        out["rideable_type"] = "classic_bike"
        csv_path = CASES / f"scenario_{name}.csv"
        out[COLS].to_csv(csv_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
        by_month = out.groupby(out["started_at"].dt.strftime("%Y-%m"))["minutes"].agg(["count", "mean"]).round(2)
        summary = {
            "scenario": name,
            "built_at": built,
            "source_bucket": BUCKET,
            "seed": SEED,
            "rule": SCENARIOS[name],
            "rows": int(len(out)),
            "months": int(by_month.shape[0]),
            "first_trip": str(out["started_at"].min()),
            "last_trip": str(out["started_at"].max()),
            "minutes": {"mean": round(float(out["minutes"].mean()), 2), "median": round(float(out["minutes"].median()), 2),
                        "min": round(float(out["minutes"].min()), 2), "max": round(float(out["minutes"].max()), 2)},
            "rides_over_45_min": int((out["minutes"] > 45).sum()),
            "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "per_month": {m: {"rides": int(r["count"]), "avg_min": float(r["mean"])} for m, r in by_month.iterrows()},
            "source_files": [e for e in log if e["scenario"] == name],
        }
        (RAW / f"part4_{name}_trip_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"wrote {csv_path.relative_to(ROOT)}: {len(out)} rows over {by_month.shape[0]} months")


if __name__ == "__main__":
    main()
