# ASTA Testing Guide

## 1. Setup

```bash
cd asta
uv venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.env .env
```

Optional: put your model at `models/model-best.h5` and TLE file at `data/tle_active.txt`.

## 2. Quick Syntax Sanity

```bash
python -m compileall app main.py config.py
```

## 3. Batch Mode Smoke Test

Put test frames in `data/` (`.png` and/or `.fits`), then run:

```bash
python main.py --mode batch --input ./data --output ./outputs
```

Check outputs:

- `outputs/satellite_summary.json`
- `outputs/satellite_frames.json`
- `outputs/satellite_trails.json`
- `outputs/astrometry_review_queue.json`
- `outputs/id_od_review_queue.json`
- `outputs/workflow_events.json`
- `outputs/satellite_report.csv`
- `outputs/annotated/*.png`

## 4. Realtime API Test

Start API with `uvicorn`:

```bash
uvicorn main:create_uvicorn_app --factory --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl -X PUT http://127.0.0.1:8000/config \
  -H 'content-type: application/json' \
  -d '{"weather_quality_threshold": 0.2}'
curl http://127.0.0.1:8000/config
```

## 5. WebSocket Frame Ingest Test (PNG)

Create a sample payload:

```bash
python - <<'PY'
import base64, json
from pathlib import Path

img = Path("data/test.png").read_bytes()
payload = {
    "type": "frame",
    "frame_id": "frame-001",
    "format": "png",
    "data": base64.b64encode(img).decode(),
    "timestamp_utc": "2026-03-28T12:00:00Z"
}
Path("ws_payload.json").write_text(json.dumps(payload))
print("wrote ws_payload.json")
PY
```

Send it:

```bash
python - <<'PY'
import asyncio, json
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/frames") as ws:
        msg = json.loads(open("ws_payload.json").read())
        await ws.send(json.dumps(msg))
        print(await ws.recv())

asyncio.run(main())
PY
```

Expected immediate response shape:

```json
{
  "type": "detection",
  "frame_id": "frame-001",
  "timestamp_utc": "2026-03-28T12:00:00Z",
  "detections": [],
  "weather": {}
}
```

## 6. Acceptance Checklist Mapping

- Realtime startup: `python main.py --mode realtime`
  Alternative: `uvicorn main:create_uvicorn_app --factory`
- GUI startup: `python main.py --mode gui`
- Health: `GET /health`
- Config update: `PUT /config` then `GET /config`
- WS ingest: `/ws/frames` with base64 PNG/FITS frame
- Batch artifacts: run batch and inspect `outputs/`
- Weather skip: set `WEATHER_SKIP_BAD_FRAMES=true` and use poor-quality frame
- Strict NORAD fail queue: ensure `id_od_review_queue.json` has `reason` + `evidence`
- Worker resilience: invalid frame should log error and continue
- Model load: place valid `models/model-best.h5` and process one frame
