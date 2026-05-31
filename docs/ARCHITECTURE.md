# Arquitetura — JUNO Backend

## Visão geral

O JUNO Backend é um monolito FastAPI com fronteiras claras entre camadas.
Mesmo sendo monolito, ele é desenhado para ser fatiável em microserviços
no futuro (cada router/service pode virar um serviço independente).

```
HTTP -> Routers (app.routers / app.api)
            |
            v
        Services (app.services)
            |
            v
        Models (app.models)  <->  Conectores (app.connectors)
            |
            v
       Database (PostgreSQL via SQLAlchemy)
```

## Camadas

### `app.config`
Settings central baseada em `pydantic-settings`. Tudo que é configuração
vem daqui — nada de `os.getenv()` espalhado pelo código.

### `app.core`
Utilidades transversais:
- `logger.py`: logging estruturado (JSON em prod, texto em dev).
- `pagination.py`: helper `PaginationParams` + função `paginate(query, params)`.

### `app.schemas`
DTOs Pydantic. **Regra dura**: nunca retornar um model SQLAlchemy direto em
um endpoint — sempre converter para um schema daqui.

### `app.services`
Lógica de negócio. Recebem `db: Session` por injeção. Não importam `fastapi`,
o que os torna testáveis sem subir o app.

### `app.routers`
Endpoints HTTP. Cada router deve ser *fino*: parse de input → chamada de
service → response. Lógica complexa não pertence aqui.

### `app.api`
Endpoints `/api/v1/*` (versão alternativa, herança das fases 5-12). Convém
consolidar com `app.routers` em uma fase futura.

### `app.connectors`
Adapters para ERPs (TOTVS, SAP, Oracle, Infor, Senior, Sankhya, genérico).
Cada conector herda de `ERPConnectorBase` e implementa `connect`,
`validate_connection`, `fetch_data`, `get_schema`. O `ERPConnectorFactory`
faz o roteamento.

### `app.integrations`
- `erp_importer.py`: importação a partir de arquivos CSV/Excel enviados pelo
  usuário (file-based).
- `connector_importer.py`: persiste dados vindos dos conectores ao vivo
  (chamado por `ERPConnectorBase.sync_entity`).

## Segurança

- JWT (HS256) para autenticação. `SECRET_KEY` via env var, obrigatória em prod.
- Rate limiting via `slowapi` no `/auth/login` (5/min por IP). Configurável.
- CORS por env var (`ALLOWED_ORIGINS`).
- Em produção, `/docs` e `/redoc` ficam desabilitados.
- Senhas com bcrypt (`passlib`).
- Auditoria de eventos em `app.audit_logger` (a integrar nos routers).

## Banco de dados

- ORM: SQLAlchemy 2.0.
- Migrations: Alembic.
- Em dev, SQLite local (sem credenciais). Em prod, PostgreSQL.

## Logging

- Em dev: texto plano colorizado.
- Em prod: JSON estruturado, fácil de plugar em ELK / Loki / CloudWatch.
- Nível padrão: `INFO` (configurável via `LOG_LEVEL`).

## Pendências conhecidas (pós-auditoria 2026-05)

Ver [MIGRATION_NOTES.md](MIGRATION_NOTES.md) para o status detalhado.

Resumo:
- `app/connectors/base.py` referencia models (`ERPConnection`, `ERPSyncLog`,
  `ERPFieldMapping`) que ainda não estão em `app/models.py`. Esses models
  existem em backups de fase 7-8 e precisam ser portados se o ERP for
  ativado em runtime.
- `app/api/erp.py` usa `current_user.company_id` (campo único), enquanto o
  `User` model atual tem relação many-to-many com `Company`. Reescrever
  esse endpoint antes de incluí-lo no `main.py`.
- `app/api/*.py` (ai, reports, security, health) não estão incluídos no
  `main.py` atual — apenas o router de `auth`. Integrar gradualmente.
