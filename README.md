# asta

realtime satellite detection and identification platform

it watches frames and politely asks  
is that a satellite or just camera drama

## what this does

- ingests fits and png frames
- checks weather quality before processing
- detects streaks with keras plus opencv fallback
- matches detections against tle catalogs
- writes annotated images and json csv reports
- exposes rest and websocket endpoints for realtime ingest

## quick setup

```bash
cd asta
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.env .env
```

optional but recommended

- put your model at `models/model-best.h5`
- put your tle file at `data/tle_active.txt`

## run realtime with uvicorn

```bash
uvicorn main:create_uvicorn_app --factory --host 0.0.0.0 --port 8000
```

## run desktop gui mode

```bash
python main.py --mode gui
```

gui features

- choose input and output directories
- run batch processing with live progress logs
- start and stop realtime api from the same window

health and config checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl -X PUT http://127.0.0.1:8000/config \
  -H 'content-type: application/json' \
  -d '{"weather_quality_threshold": 0.2}'
curl http://127.0.0.1:8000/config
```

## websocket test

create payload from a local png

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

send payload

```bash
python - <<'PY'
import asyncio, json
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/frames") as ws:
        await ws.send(json.dumps(json.loads(open("ws_payload.json").read())))
        print(await ws.recv())

asyncio.run(main())
PY
```

expected response shape

```json
{
  "type": "detection",
  "frame_id": "frame-001",
  "timestamp_utc": "2026-03-28T12:00:00Z",
  "detections": [],
  "weather": {}
}
```

## batch test

drop test files into `data/` then run

```bash
python main.py --mode batch --input ./data --output ./outputs
```

check outputs

- `outputs/satellite_summary.json`
- `outputs/satellite_frames.json`
- `outputs/satellite_trails.json`
- `outputs/astrometry_review_queue.json`
- `outputs/id_od_review_queue.json`
- `outputs/workflow_events.json`
- `outputs/satellite_report.csv`
- `outputs/annotated/*.png`

## tiny acceptance walk

- realtime boots successfully
- `GET /health` reports queue size
- `PUT /config` updates values
- websocket accepts base64 frame
- batch writes all artifacts
- bad weather frames get skipped if configured
- strict id misses land in `id_od_review_queue.json`

## one honest warning

if the frame quality is chaotic  
the model may become dramatically cautious
