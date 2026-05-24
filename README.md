# UrbanGuard

Real-time city safety intelligence platform. Simulated CCTV streams flow through Kafka into a two-stage neural detector (CLIP zero-shot filter, fine-tuned ResNet-50 severity scorer), get triaged by a LangGraph multi-agent pipeline, and feed a PPO reinforcement-learning policy that learns where to allocate sampling compute as incident patterns shift across city zones.

## What's inside

- `services/ingest` — frame producers, one per simulated camera
- `services/detect` — CLIP + ResNet detection consumer
- `services/agents` — LangGraph triage / route / notify / memory
- `services/rl` — PPO zone-priority policy
- `services/replay` — DuckDB aggregation + Kafka offset replay
- `services/gateway` — public FastAPI for the dashboard (SSE)
- `shared/` — Pydantic models, topic constants, settings
- `frontend/` — Next.js 15 dashboard
- `infra/` — Docker, Kafka init, OSRM build, optional AWS Lambda
- `docs/` — architecture, ADRs, command log

## Quick start

```bash
make up        # bring up kafka, redis, postgres, minio, langfuse, osrm
make ingest    # start a simulated camera fleet from local clips
make smoke     # end-to-end smoke test
```

## Stack

Python 3.12 · uv workspaces · FastAPI · aiokafka · PyTorch (MPS) · CLIP · ResNet-50 · LangGraph · Stable-Baselines3 · DuckDB · Postgres · Redis · MinIO · Langfuse · Next.js 15 · Leaflet.

Heavy training runs on Google Colab; local stack runs entirely on a single Apple Silicon laptop.
