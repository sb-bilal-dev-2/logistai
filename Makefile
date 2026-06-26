# Convenience targets. Use `make <target>`; Docker targets need Docker installed.
.PHONY: help install migrate seed run once test analytics docker docker-postgres docker-ollama ollama-pull docker-down

help:
	@echo "install         install core deps (offline, no AI SDK)"
	@echo "migrate         apply DB migrations (alembic upgrade head)"
	@echo "run             seed + live generate/match loop"
	@echo "once            single generate/match tick + analytics"
	@echo "test            run the test suite"
	@echo "analytics       print agent performance summary"
	@echo "docker          docker compose up (SQLite, zero config)"
	@echo "docker-postgres docker compose up with Postgres"
	@echo "docker-ollama   docker compose up with a local LLM (Ollama)"
	@echo "ollama-pull     pull the local LLM model into the ollama container"
	@echo "docker-down     stop + remove docker stack"

install:
	python -m pip install -r requirements.txt

migrate:
	python -m alembic upgrade head

seed: migrate
	python -m app.seed

run: migrate
	python -m app.runner

once: migrate
	python -m app.runner --once

test:
	python -m pytest

analytics:
	python -m app.analytics

docker:
	docker compose up --build

docker-postgres:
	docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build

docker-ollama:
	docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build

ollama-pull:
	docker compose -f docker-compose.yml -f docker-compose.ollama.yml exec ollama ollama pull $(or $(OLLAMA_MODEL),llama3.2)

docker-down:
	docker compose -f docker-compose.yml -f docker-compose.postgres.yml -f docker-compose.ollama.yml down -v
