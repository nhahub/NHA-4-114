# Backend Section — Speaker Notes
**Slot: 10 minutes · Smart Vision System (SVS) presentation**

Condensed script — one breath per section. Every detail is real, pulled from the actual codebase (`backend/app/`, `backend/ai/`, `frontend/`), not generic definitions.

---

## Timing Cheat Sheet

| Time | Topic | Duration |
|---|---|---|
| 0:00 – 0:30 | Intro | 30 sec |
| 0:30 – 1:30 | FastAPI | 1 min |
| 1:30 – 2:45 | REST APIs | 1:15 |
| 2:45 – 4:15 | WebSockets | 1:30 |
| 4:15 – 5:45 | Redis | 1:30 |
| 5:45 – 7:00 | PostgreSQL | 1:15 |
| 7:00 – 8:30 | Workers | 1:30 |
| 8:30 – 9:30 | AI → Frontend Workflow | 1 min |
| 9:30 – 10:00 | Closing | 30 sec |

---

## Intro (30 sec)

> "I'll cover the backend in one pass: how a raw camera feed becomes a bounding box, a count, and an alert on your screen — through FastAPI, REST, WebSockets, Redis, PostgreSQL, and our background AI workers."

---

## 1. FastAPI (1 min)

- Our whole app is one FastAPI instance, built by `create_app()` in [backend/app/main.py](backend/app/main.py) — mounts REST routers, two WebSocket routes, static file serving, and CORS.
- `lifespan` startup/shutdown brings the WebSocket manager and DB engine up and down cleanly.
- Auto-generates interactive docs at `/docs` — the frontend team built against that directly.

**Say:** "FastAPI is async-native, which matters because we're juggling open WebSocket connections, Redis listeners, and DB queries all at once without blocking each other."

---

## 2. REST APIs (1:15)

Real endpoints, grouped:
- **auth** — `POST /auth/token` (login/JWT), `GET /auth/me`
- **cameras** — full CRUD; creating one spins up a background AI worker
- **zones** — CRUD for polygon zones per camera (JWT-protected)
- **alerts** / **logs** — paginated history, filterable by severity / camera / event type
- **analytics** — `GET /analytics/summary` returns total in/out, live occupancy, active alerts (straight `COUNT` queries against Postgres)

**Say:** "REST is for anything you configure or check on your own schedule — set up a camera, page through yesterday's logs. Ask once, get one answer."

---

## 3. WebSockets (1:30)

- `/ws/cameras/{camera_id}` — live annotated frame + detections per camera
- `/ws/alerts` — global alert stream
- Real payload: `{camera_id, frame (base64 JPEG), occupancy, tracks[{track_id, bbox}], business_events[]}`
- Frontend: `useCameraStream` hook opens the socket → Zustand store → `CameraFeed` draws the frame on `<canvas>`, `TrackOverlay` draws boxes as SVG — no polling.

**Say:** "REST is calling to ask if your delivery arrived. A WebSocket leaves the line open — the moment a new frame or alert exists, it's pushed straight to your screen, up to 15 times a second."

---

## 4. Redis (1:30)

Three real jobs, one piece of infra:
1. **Celery broker + result backend** — how camera-processing tasks get queued.
2. **Pub/Sub bridge** — `camera:{id}:frames`, `camera:{id}:alerts`, `camera:{id}:events`. This is how the AI worker (a separate process) talks to the FastAPI/WebSocket process — they can't call each other directly.
3. Our `ConnectionManager` subscribes per active camera and rebroadcasts every message straight to connected browsers.

**Say:** "Redis is the nervous system between our AI brain and our web server body — two separate processes that talk over shared channels instead of function calls."

---

## 5. PostgreSQL (1:15)

Real tables: `cameras`, `zones` (polygon stored as JSON points), `events` (entry/exit/loitering/zone events), `alerts` (severity + resolved flag), `users`.

**Say:** "If Redis is the live announcement, Postgres is the filing cabinet — the permanent transcript. Redis messages vanish the instant they're delivered; Postgres is how we can still answer 'how many people entered yesterday' months later."

---

## 6. Workers (1:30)

- Video decoding + YOLO inference is heavy — can't run inside an API request without freezing the whole server. So it runs in **Celery background tasks**, one per camera.
- `POST /cameras` creates the DB row *and* dispatches a Celery task; `DELETE` revokes it.
- `camera_worker.py` is the actual loop: reads frames at 15 FPS, runs the AI pipeline, publishes results to Redis. Handles RTSP reconnects automatically.
- Separate `event_worker.py` / `alert_worker.py` processes just persist Redis messages into Postgres — so a slow DB write never blocks the live stream.

**Say:** "Every camera gets its own dedicated background worker — one security guard per screen. One bad camera can't take down the others or the API."

---

## 7. AI → Frontend Workflow (1 min)

Walk this as a single breath, pointing at a diagram slide:

```
Camera feed → camera_worker.py (Celery task, 15 FPS)
   → AI Pipeline: YOLO detection → ByteTrack tracking → business logic
     (entry/exit, zones, loitering, weapon alerts)
   → annotated frame + events → Redis (camera:{id}:frames / alerts / events)
   → ┬─ ConnectionManager → WebSocket → browser canvas + bounding boxes (live)
     └─ event_worker / alert_worker → PostgreSQL (permanent history)
```

**Say:** "Every bounding box you see made this whole trip — camera to YOLO to tracker to Redis to WebSocket to canvas — in under a second. The same event also lands in Postgres, so the live view and the history page always agree."

---

## Closing (30 sec)

> "In one sentence: FastAPI is the front door, REST is for on-demand lookups, WebSockets push live updates, Redis bridges our AI and web processes, Postgres is the permanent record, and Celery workers run the AI per camera without freezing the system. Seven tools, each solving a problem the others can't."
