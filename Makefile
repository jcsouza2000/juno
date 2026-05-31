# JUNO Makefile - comandos uteis para desenvolvimento e deploy

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend build up up-prod down logs shell backup restore test test-backend lint-backend test-frontend migrate clean

help:
	@echo "JUNO DevOps Commands:"
	@echo "  make install          - instalar dependencias backend/frontend"
	@echo "  make dev-backend      - iniciar FastAPI em desenvolvimento"
	@echo "  make dev-frontend     - iniciar Next.js em desenvolvimento"
	@echo "  make build            - build Docker images"
	@echo "  make up               - iniciar stack Docker"
	@echo "  make up-prod          - iniciar stack Docker de producao"
	@echo "  make down             - parar stack"
	@echo "  make logs             - ver logs"
	@echo "  make shell            - shell no container backend"
	@echo "  make backup           - backup do banco"
	@echo "  make restore FILE=... - restore do banco"
	@echo "  make test             - rodar testes/lint/build"
	@echo "  make lint-backend     - rodar ruff no backend"
	@echo "  make migrate          - rodar migrations"
	@echo "  make clean            - limpar containers e volumes"

install: install-backend install-frontend

install-backend:
	cd janus/backend && python -m pip install --upgrade pip && pip install -r requirements-dev.txt

install-frontend:
	cd janus/frontend && npm ci

dev: dev-backend

dev-backend:
	cd janus/backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd janus/frontend && npm run dev

build:
	docker compose -f docker-compose.prod.yml build

up:
	docker compose -f docker-compose.prod.yml up -d

up-prod:
	docker compose -f docker-compose.prod.yml up -d

down:
	docker compose -f docker-compose.prod.yml down

logs:
	docker compose -f docker-compose.prod.yml logs -f

shell:
	docker compose -f docker-compose.prod.yml exec juno-backend sh

backup:
	bash scripts/backup.sh

restore:
	@if [ -z "$(FILE)" ]; then echo "Uso: make restore FILE=backups/juno_db_AAAAMMDD_HHMMSS.sql.gz"; exit 1; fi
	bash scripts/restore.sh "$(FILE)"

test:
	cd janus/backend && ruff check app && pytest app/tests/ -v
	cd janus/frontend && npm run lint && npm run build

test-backend:
	cd janus/backend && ruff check app && pytest app/tests/ -v

lint-backend:
	cd janus/backend && ruff check app

test-frontend:
	cd janus/frontend && npm run lint && npm run build

migrate:
	docker compose -f docker-compose.prod.yml exec juno-backend alembic upgrade head

clean:
	docker compose -f docker-compose.prod.yml down -v
	docker system prune -f
