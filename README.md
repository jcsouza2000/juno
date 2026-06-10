# JANUS_AI / JUNO

[![CI](https://github.com/jcsouza2000/juno/actions/workflows/ci.yml/badge.svg)](https://github.com/jcsouza2000/juno/actions/workflows/ci.yml)

Repositorio: **https://github.com/jcsouza2000/juno**

Plataforma de diagnostico industrial B2B com IA local, ontology engine, conectores ERP, dashboards executivos, auditoria e controles de seguranca.

## Estado validado em 2026-05-25

| Area | Estado |
| --- | --- |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PostgreSQL em producao e SQLite em dev |
| Frontend | Next.js 16.2.6, React 19.2.4, TypeScript, Tailwind |
| IA | Ollama `qwen3:8b` local; OpenAI mantido como motor legado/opcional |
| Ontology | ObjectTypes, ActionTypes, markings, snapshots, lineage e SDK generator |
| ERP | Conectores TOTVS, Senior, SAP, Sankhya, Oracle, Infor e Generic |
| Seguranca | JWT, rate limit, CORS por env, Fernet para segredos ERP, LGPD/GDPR, auditoria |
| Qualidade | `mypy` com `check_untyped_defs`, `ruff`, `black`, `pytest`, `npm audit`, `npm lint`, `npm build` passando |
| Docker | Build, migrations e stack real validados com containers saudaveis |

## Validacao

Backend:

```powershell
cd C:\Souza\juno\janus\backend
.\.venv\Scripts\mypy app
.\.venv\Scripts\ruff check app
.\.venv\Scripts\black --check app
$env:PYTHONPATH='.'; $env:JUNO_ENV='development'; `
  $env:SECRET_KEY='test-secret-key-must-have-at-least-32-chars'; `
  $env:ENCRYPTION_KEY='N6zYqfBC2CxUgdztuLcM5nVSyxe7S6TjzS-ZmrkcmCM='; `
  $env:DATABASE_URL='sqlite:///./validation.db'; `
  .\.venv\Scripts\pytest -q --no-cov
```

Frontend:

```powershell
cd C:\Souza\juno\janus\frontend
npm audit --audit-level=moderate
npm run lint
npm run build
```

Docker:

```powershell
cd C:\Souza\juno
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Resultado de referencia: 190 testes backend passando, sem warnings; 0 vulnerabilidades npm moderadas ou superiores; frontend build compilado; Postgres, Redis, backend e frontend saudaveis no Docker.

## Estrutura

```text
C:\Souza\juno
|-- janus/
|   |-- backend/          FastAPI, SQLAlchemy, Alembic, pytest, mypy
|   |-- frontend/         Next.js App Router
|   `-- examples/         dados e templates de demonstracao
|-- deploy/               nginx, prometheus, grafana
|-- docs/                 arquitetura, changelog, notas de migracao
|-- infrastructure/       infraestrutura/IaC
|-- ml-pipeline/          artefatos de pipeline ML
|-- scripts/              utilitarios mantidos
|-- _archive/             documentos e composes legados preservados
|-- docker-compose.prod.yml
|-- Manual_Juno.txt
`-- Juno.pptx
```

## Setup local

Backend:

```powershell
cd C:\Souza\juno\janus\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd C:\Souza\juno\janus\frontend
npm install
npm run dev
```

Acessos:

- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs` apenas fora de producao
- Frontend: `http://localhost:4000`

## Producao

Use apenas o compose consolidado:

```powershell
cd C:\Souza\juno
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build
```

Antes de publicacao externa, revisar `SECURITY_ENV_REVIEW.md` e garantir valores fortes e definitivos para:

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `ALLOWED_ORIGINS`
- `LOGIN_RATE_LIMIT`
- `NEXT_PUBLIC_API_URL`
- `NEXTAUTH_SECRET`
- `AUTH_SECRET`

## Documentacao

- `Manual_Juno.txt` - manual operacional atual.
- `Manual_Usuario_Juno.txt` - manual passo a passo por aba do menu para usuarios e implantadores.
- `Juno.pptx` - apresentacao executiva atual.
- `_archive/docs_legacy/` - documentos originais preservados byte a byte.
- `docs/CHANGELOG.md` - historico consolidado.
- `docs/MIGRATION_NOTES.md` - notas tecnicas da auditoria.
- `SECURITY_ENV_REVIEW.md` - checklist de publicacao segura.

## Pendencias restantes

- Revisar os valores definitivos do `.env.prod` antes de publicacao externa.
- Testar login e fluxo `/ai` com usuarios reais/dados de demo no ambiente alvo.
- Decidir se a stack Docker local deve permanecer rodando ou ser parada apos validacao.

## Licenca

Proprietario - todos os direitos reservados.
