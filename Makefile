.PHONY: help sync up down logs ps smoke fmt lint test clean ingest detect agents rl gateway replay

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync: ## install python deps via uv
	uv sync --all-packages

up: ## start the local stack (kafka, redis, postgres, minio, langfuse)
	docker compose up -d
	@echo "waiting for kafka..."
	@until docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do sleep 1; done
	@bash infra/kafka/init-topics.sh

down: ## stop the local stack
	docker compose down

logs: ## tail all service logs
	docker compose logs -f --tail=100

ps: ## show running services
	docker compose ps

fmt: ## format code with ruff
	uv run ruff format .
	uv run ruff check --fix .

lint: ## check formatting and lint
	uv run ruff format --check .
	uv run ruff check .

test: ## run all tests
	uv run pytest -q

smoke: ## end-to-end smoke test
	uv run python -m tests.smoke

ingest: ## run the ingest service (dev)
	uv run --package urbanguard-ingest uvicorn ingest.main:app --reload --port 8001

detect: ## run the detect service (dev)
	uv run --package urbanguard-detect python -m detect.main

agents: ## run the agents service (dev)
	uv run --package urbanguard-agents uvicorn agents.main:app --reload --port 8004

rl: ## run the rl policy server (dev)
	uv run --package urbanguard-rl uvicorn rl.policy_server:app --reload --port 8005

gateway: ## run the gateway service (dev)
	uv run --package urbanguard-gateway uvicorn gateway.main:app --reload --port 8000

replay: ## run the replay service (dev)
	uv run --package urbanguard-replay python -m replay.main

clean: ## remove caches and build artefacts
	rm -rf .venv .ruff_cache .pytest_cache .pyright **/__pycache__ build dist *.egg-info
