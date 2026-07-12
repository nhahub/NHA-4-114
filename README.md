# Smart Vision System for Small Businesses

An integrated AI-powered real-time video monitoring and analysis platform designed for small businesses such as retail stores, shopping malls, and warehouses. The system transforms raw surveillance camera streams into intelligent, actionable data — including visitor counting, movement behavior analysis, security alerts, and occupancy analytics — all through a unified dashboard.

---

## Table of Contents

* Overview
* Key Features
* System Architecture
* Technology Stack
* Project Structure
* Getting Started
* API Reference
* Frontend Dashboard
* Development Phases
* Use Cases
* Design Principles

---

## Overview

Traditional surveillance systems in small businesses are limited to passive recording, lacking the ability to analyze customer movement, count visitors accurately, detect suspicious behavior in real time, or generate actionable business insights. Smart Vision System addresses these gaps by combining computer vision and AI to turn existing cameras into an intelligent monitoring platform.

The system processes live video feeds through a multi-stage AI pipeline — detection, tracking, and business logic analysis — and delivers real-time results to a web-based dashboard alongside historical analytics and event logging.

### What It Provides

| Capability            | Description                                                                |
| --------------------- | -------------------------------------------------------------------------- |
| Person Detection      | Real-time detection using YOLOv8 with bounding boxes and confidence scores |
| Multi-Object Tracking | Persistent ID assignment via ByteTrack for reliable movement analysis      |
| Entry/Exit Counting   | Automatic counting at virtual lines placed at entrances and exits          |
| Zone Monitoring       | Polygon-based occupancy tracking with configurable thresholds              |
| Behavior Analysis     | Loitering detection via centroid displacement tracking                     |
| Heatmap Generation    | Density grid accumulation with Gaussian blur visualization                 |
| Weapon Detection      | Dedicated fine-tuned YOLO model for guns and knives                        |
| Smart Alerts          | Severity-based alert system with cooldown deduplication                    |
| Event Logging         | Full event history with timestamps, camera IDs, and event types            |

---

## Key Features

### Real-Time Monitoring

* Live video streams with detection bounding boxes, tracking IDs, and threat highlighting
* Multi-camera display support
* FPS and processing time overlay

### Analytics Dashboard

* Entry/exit traffic statistics
* Occupancy and zone-level activity
* Heatmap visualization
* Historical trend analysis

### Smart Alert System

| Alert Type        | Severity | Trigger                          |
| ----------------- | -------- | -------------------------------- |
| zone_overcrowding | High     | Zone occupancy exceeds threshold |
| loitering         | Medium   | Person stationary too long       |
| crossing_event    | Low      | Line crossing detected           |
| zone_occupancy    | Low      | Informational snapshot           |
| weapon_detected   | Critical | Gun or knife detected            |

### Operator Tools

* Interactive line drawing for entry/exit counting
* Polygon zone configuration
* Real-time visualization tools

---

## System Architecture

```
Frontend Dashboard (Next.js)
        ↓ WebSocket + REST API
Backend Service Layer (FastAPI)
        ↓ Redis Pub/Sub + PostgreSQL
AI Processing Layer (YOLOv8 + ByteTrack)
        ↓ Frame Capture Layer
Camera Input (RTSP / USB / Video)
```

### Data Flow

```
Camera → Frame Capture → AI Pipeline → Redis → WebSocket → Dashboard
```

### Processing Sequence (per frame)

1. Line setup (once)
2. Frame capture
3. YOLO detection
4. ByteTrack assignment
5. Track state update
6. Entry/exit detection
7. Zone monitoring
8. Behavior analysis
9. Heatmap update
10. Alert generation
11. Frame annotation
12. Redis publish
13. WebSocket broadcast
14. PostgreSQL logging

---

## Technology Stack

### AI & Computer Vision

* YOLOv8n — Person detection
* YOLOv8 custom — Weapon detection
* ByteTrack — Object tracking
* OpenCV — Frame processing
* supervision — Tracking utilities

### Backend

* FastAPI — API + WebSocket
* PostgreSQL — Data storage
* Redis — Pub/Sub messaging
* SQLAlchemy (async) — ORM
* Celery — Worker tasks
* MinIO — Object storage

### Frontend

* Next.js — UI framework
* Zustand — State management
* React Query — Data fetching
* WebSocket API — Live updates

### Infrastructure

* Docker Compose — Local deployment
* Kubernetes — Scaling
* Nginx — Reverse proxy

---

## Project Structure

```
smart-vision-system/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/v1/
│   │   ├── websocket/
│   │   ├── workers/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── db/
│   │   └── core/
│   ├── ai/
│   │   ├── detector/
│   │   ├── tracker/
│   │   ├── business_logic/
│   │   ├── pipeline.py
│   │   └── frame_annotator.py
│   ├── tests/
│   └── Dockerfile
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   └── Dockerfile
│
├── infrastructure/
│   ├── docker-compose.yml
│   ├── nginx/
│   └── k8s/
│
├── models/
│   ├── yolov8n.pt
│   └── yolov8_weapon_v1.pt
│
└── docs/
    ├── architecture.md
    ├── api-reference.md
    ├── project_structure.md
    └── deployment.md
```

---

## Getting Started

### Prerequisites

* Python 3.10+
* Node.js 18+
* Docker & Docker Compose
* PostgreSQL 15+
* Redis 7+

### Quick Start

```bash
git clone <repository-url>
cd smart-vision-system
docker-compose -f infrastructure/docker-compose.yml up --build
```

* Backend: [http://localhost:8000](http://localhost:8000)
* Frontend: [http://localhost:3000](http://localhost:3000)

---

## API Reference

### REST API

* `/api/v1/cameras`
* `/api/v1/alerts`
* `/api/v1/analytics`
* `/api/v1/logs`
* `/api/v1/health`

### WebSocket

* `/ws/cameras/{camera_id}`
* `/ws/alerts`

---

## Frontend Dashboard

Pages:

* `/monitor` — Live monitoring
* `/alerts` — Alerts
* `/analytics` — Insights
* `/logs` — Event logs
* `/cameras` — Camera management

---

## Development Phases

| Phase   | Scope              | Status    |
| ------- | ------------------ | --------- |
| Phase 1 | AI pipeline        | Completed |
| Phase 2 | Backend services   | Next      |
| Phase 3 | Frontend dashboard | Planned   |

---

## Use Cases

* Retail analytics
* Mall crowd monitoring
* Warehouse safety
* Security surveillance
* Visitor behavior analysis

---

## Design Principles

* Separation of concerns
* Decoupled architecture
* Modular AI pipeline
* Fault tolerance
* Scalability
* Reproducibility

---

## License

Academic graduation project

---

## Value

The system transforms CCTV into an intelligent analytics platform providing:

* Security enhancement
* Visitor intelligence
* Operational insights
* Business decision support
