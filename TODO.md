# JUNO / Janus AI - TODO

Estado apos fechamento das pendencias de Docker, warnings, tipagem estrita e chat legado.

## Concluido

- Seguranca: `SECRET_KEY`, `DATABASE_URL`, `ENCRYPTION_KEY` e CORS via ambiente.
- Rate limit no login e `/docs`/`/redoc` desabilitados em producao.
- `requirements*.txt` consolidados.
- Conectores ERP alinhados a `app/connectors/`.
- Models SQLAlchemy ampliados e alinhados as migrations.
- Stub `app/models.pyi` criado para tipagem SQLAlchemy.
- `check_untyped_defs = true` ativado no mypy.
- `mypy app`: 0 erros em 133 arquivos.
- `ruff check app` e `black --check app`: passando.
- `pytest -q --no-cov`: 190 passando, 0 falhando, sem warnings.
- `npm audit --audit-level=moderate`: 0 vulnerabilidades.
- `npm run lint` e `npm run build`: passando.
- Compose oficial de producao consolidado em `docker-compose.prod.yml`.
- Build Docker real validado.
- Alembic `upgrade head` validado em PostgreSQL dentro do container backend.
- Stack Docker real validada: Postgres, Redis, backend e frontend saudaveis.
- `ChatInterface.tsx` legado removido; `/ai` e a interface oficial.
- Documentos legados grandes preservados em `_archive/docs_legacy/`.

## Pendencias restantes

### Publicacao externa

- Revisar `.env.prod` sem expor valores.
- Trocar segredos temporarios/locais por segredos definitivos do ambiente alvo.
- Ajustar `ALLOWED_ORIGINS` e `NEXT_PUBLIC_API_URL` para dominio real.

### Validacao funcional final

- Testar login ponta a ponta.
- Testar fluxo `/ai`.
- Testar upload financeiro e relatorio PDF com dados de demo.
- Testar ao menos um conector ERP em ambiente controlado.

### Operacao local

- Decidir se a stack Docker local deve permanecer rodando.
- Para parar:

```powershell
cd C:\Souza\juno
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

## Regra para proximas alteracoes

Antes de publicar ou commitar:

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

cd C:\Souza\juno\janus\frontend
npm audit --audit-level=moderate
npm run lint
npm run build

cd C:\Souza\juno
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```
