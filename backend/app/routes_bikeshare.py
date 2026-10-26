"""HW7 Part 4: UI page + run endpoint for the bike-share membership agent.

GET  /bikeshare       the page (CSV upload, pricing URL, Run, timeline, results)
POST /bikeshare/run   multipart form: file=<trips.csv>, pricing_url=<url>, label=<optional scenario name>
Each run is saved to reports/hw07/raw/part4_runs/<run_id>.json together with the exact pricing-page
text snapshot, its source URL, capture time and SHA-256.
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import bikeshare_agent
from . import bikeshare_tools as bt

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "backend" / "uploads"
RUNS = ROOT / "reports" / "hw07" / "raw" / "part4_runs"

router = APIRouter(tags=["HW7 Bike-share agent"])


@router.get("/bikeshare", include_in_schema=False)
def bikeshare_page():
    return FileResponse(ROOT / "frontend" / "bikeshare.html")


@router.get("/bikeshare/runs/{run_id}")
def get_run(run_id: str):
    """A saved run (same JSON the Run button returns), so a result can be reopened in the UI."""
    if not re.fullmatch(r"[0-9A-Za-z-]+", run_id):
        raise HTTPException(status_code=400, detail="bad run id")
    path = RUNS / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    record.pop("pricing_snapshot", None)
    return record


@router.post("/bikeshare/run")
def run_bikeshare(file: UploadFile = File(...), pricing_url: str = Form(...), label: str = Form("")):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv trip file.")
    if not re.match(r"^https?://", pricing_url.strip()):
        raise HTTPException(status_code=400, detail="pricing_url must start with http:// or https://")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    csv_path = UPLOADS / f"{run_id}_uploaded.csv"
    csv_path.write_bytes(file.file.read())
    try:
        result = bikeshare_agent.run(str(csv_path), pricing_url.strip())
    finally:
        bt._DB.pop(str(csv_path.resolve()), None)
    page = bt._PAGES.get(pricing_url.strip())
    result.update({"run_id": run_id, "label": label or Path(file.filename).stem, "uploaded_name": file.filename})
    record = {**result, "pricing_snapshot": {
        "url": pricing_url.strip(),
        "captured_at": page["captured_at"] if page else None,
        "sha256": page["sha256"] if page else None,
        "raw_html_sha256": page["raw_html_sha256"] if page else None,
        "text": page["text"] if page else None,
    }}
    (RUNS / f"{run_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return result
