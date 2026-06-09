# Architecture

A short tour of the repo, optimized for a reader who has just opened it.

## Directory layout

```
UrbanGuard/
├── pyproject.toml              # uv workspace root, ruff + pytest config
├── uv.lock                     # single resolved env across all services
├── docker-compose.yml          # kafka (KRaft) + redis + postgres + minio + langfuse
├── Makefile                    # `make up`, `make test`, per-service `make <svc>`
├── .env.example                # every setting; .env is gitignored
│
├── shared/                     # cross-service Pydantic models, Kafka helpers, settings
│   └── src/shared/
│       ├── models.py           # Frame, Alert, Incident, RLFeedback
│       ├── topics.py           # RAW_FRAMES, ALERTS, RL_FEEDBACK
│       ├── settings.py         # pydantic-settings
│       ├── kafka_io.py         # producer / consumer / send_model / consume_model
│       ├── observability.py    # langfuse trace context + prometheus installer
│       └── testing.py          # live skip markers (kafka / postgres / redis)
│
├── services/
│   ├── ingest/    src/ingest/   { camera, video_loader, main }
│   ├── detect/    src/detect/   { clip_classifier, resnet_scorer, consumer, model_loader }
│   ├── agents/    src/agents/   { graph, llm_provider, state, nodes/{triage,route,notify,memory} }
│   ├── rl/        src/rl/       { env, train, policy_server, feedback_consumer }
│   ├── replay/    src/replay/   { aggregate, replay, main }
│   └── gateway/   src/gateway/  { main, sse, routes/{alerts,heatmap,cameras} }
│
├── frontend/                   # Next.js 15 dashboard
│   ├── app/{page.tsx, layout.tsx, globals.css}
│   ├── components/HeatmapLayer.tsx
│   └── lib/api.ts
│
├── infra/
│   ├── kafka/init-topics.sh
│   ├── postgres/init-multiple-dbs.sh
│   └── lambda/                 # optional AWS SAM template (Phase 9)
│
├── tests/                      # cross-service / shared tests
├── docs/                       # this file, architecture notes
└── .github/workflows/ci.yml    # ruff + pytest on push/PR
```

## Kafka topics

| Topic | Producer | Consumer | Volume |
|---|---|---|---|
| `raw-frames` | ingest | detect | high (N cameras × 2 fps × ~50KB JPEG) |
| `alerts` | detect | agents, gateway (SSE) | low (~one per incident) |
| `rl-feedback` | agents (future), replay | rl feedback consumer | medium |

Each topic uses the **sticky partition assignor** + **idempotent producer** + **manual commit** pattern in [`shared/kafka_io.py`](../shared/src/shared/kafka_io.py).

## Service ports (defaults from `.env.example`)

| Service | Port |
|---|---|
| Gateway | 8000 |
| Ingest | 8001 |
| Detect (no HTTP, consumer only) | — |
| Agents | 8004 |
| RL policy server | 8005 |
| Kafka | 9092 |
| Postgres | 5432 |
| Redis | 6379 |
| MinIO | 9000 (console 9001) |
| Langfuse | 3001 |
| Next.js dev | 3000 |

## Where to look next

- **Tour the *why* phase by phase**: `learning/00_overview.md` then `01..09_*.md`. (The `learning/` folder is gitignored — it's the author's personal track. If you're reading this on GitHub, you only have the architecture; for the narrative version, talk to the author.)
- **Specific design decisions**: `docs/adr/` (one ADR per non-trivial choice; create new files as decisions land).
- **Real bugs encountered**: `learning/difficulties.md` (also gitignored). Six logged so far: aiokafka assignor strings, cramjam vs lz4, pytest module collisions, SQLAlchemy + greenlet, eager skip markers, async engine across loops.
