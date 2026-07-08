.PHONY: env migrate up up-gpu down logs seed smoke lint clean

# Windows: `make` isn't installed by default. Install via `choco install make`
# or `scoop install make`, or use Git Bash with MSYS2's make package. If you
# don't want to install make at all, the raw `docker compose` commands each
# target runs are shown in comments below and in README.md.

env: ## One-time: create .env from .env.example if it doesn't exist yet
	@test -f .env || cp .env.example .env

migrate: env ## Apply Postgres migrations (one-off job, run before `up` brings the gateway up)
	docker compose up -d --wait postgres
	docker compose --profile tools run --rm migrate

up: migrate ## Start the full stack (whisper, llm, tts, intent, qdrant, postgres, gateway), wait for healthy
	docker compose up -d --wait
	docker compose ps

up-gpu: migrate ## Start with GPU passthrough for whisper (requires NVIDIA + nvidia-container-toolkit)
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --wait
	docker compose ps

down: ## Stop and remove all containers
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

seed: migrate ## Seed Postgres + Qdrant with sample memory entries
	docker compose --profile tools run --rm seed

smoke: env ## Run the end-to-end smoke test against the running stack
	docker compose --profile tools run --rm smoke-test

lint: ## Run ruff + black --check + pytest (installs dev tools into venv on demand)
	venv\python.exe -m pip install -q -r requirements-dev.txt
	venv\python.exe -m ruff check .
	venv\python.exe -m black --check .
	venv\python.exe -m pytest tests -q

clean: ## Stop containers and remove volumes (Qdrant data, whisper model cache)
	docker compose down -v
