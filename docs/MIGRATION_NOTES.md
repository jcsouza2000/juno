# Notas de migração — Auditoria 2026-05

Este documento registra o que **foi feito** durante a auditoria de
maio/2026 e o que ficou em **dívida técnica para a próxima rodada**.

## ✅ Concluído nesta auditoria

### Segurança (CRÍTICO)
- `SECRET_KEY` hardcoded removida de `app/auth.py`. Agora vem via env.
- Credenciais Postgres removidas do fallback em `app/database.py`. Dev cai
  para SQLite local sem credenciais.
- CORS por env (`ALLOWED_ORIGINS`).
- Rate limiting (`slowapi`) ativado no `/auth/login` (5/min, configurável).
- `/docs` e `/redoc` desabilitados automaticamente em produção.
- CI scan que falha se `SECRET_KEY` antiga ou credenciais antigas
  reaparecerem no código.

### Estrutura / limpeza
- Backend legado `janus/app/` removido inteiro.
- Conectores ERP duplicados (`app/erp_connectors/`) removidos. Mantido
  apenas `app/connectors/` (escolha do usuário).
- Router antigo `app/routers/erp.py` (que usava `erp_connectors/`) removido.
- 8 arquivos `main_update_fase*.py` (fases 5-12) removidos e
  consolidados em `docs/CHANGELOG.md`.
- `app/erp_importer_v2.py` movido para `app/integrations/connector_importer.py`
  para ficar perto do `erp_importer.py` (file-based).
- CSVs `romi_products.csv`, `fachini_products.csv` e templates movidos para
  `janus/examples/` (são dados de demo).
- Venvs duplicados `.venv/` e `.venv-1/` na raiz foram apagados.
- `.gitignore` central criado na raiz cobrindo venvs, node_modules, .env,
  caches, backups antigos.

### Estrutura nova
- `app/config.py` — Settings central com `pydantic-settings`.
- `app/core/logger.py` — logging estruturado.
- `app/core/pagination.py` — `PaginationParams` + `paginate()`.
- `app/schemas/` — schemas Pydantic separados dos models SQLAlchemy.
- `app/services/` — camada de lógica de negócio entre routers e models.
- `app/tests/conftest.py` — fixtures pytest (SQLite em memória, TestClient).
- `pytest.ini`, `pyproject.toml` (ruff/black/mypy).
- `requirements-dev.txt` separado.
- `.github/workflows/ci.yml` — CI completa (lint, tests, build, secrets scan).
- `README.md` na raiz, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`.

### Routers
- `routers/auth.py` reescrito: usa schemas Pydantic, rate limit, logging
  estruturado, não vaza `hashed_password`.

### Testes
- 3 arquivos de teste novos: `test_health.py`, `test_auth.py`, `test_config.py`.
- Cobertura inicial de auth e config; antigos `test_ml.py`, `test_reports.py`,
  `test_security.py` mantidos mas precisam de revisão.

## 🚧 Pendências conhecidas (para próxima rodada)

### 1. Models ERP faltando em `app/models.py`
`app/connectors/base.py` importa `ERPConnection`, `ERPSyncLog` e
`ERPFieldMapping` de `app.models`, mas o `models.py` atual não tem essas
classes. Elas existem nos backups `models.py.backup.fase7/8`.

**Ação:** portar essas três classes para `models.py` quando o módulo ERP
for ativado. Gerar migration Alembic correspondente.

### 2. `app/api/erp.py` assume `User.company_id`
O endpoint usa `current_user.company_id` (single), enquanto o `User` model
atual tem relação many-to-many com `Company`.

**Ação:** decidir entre (a) adicionar `company_id` direto no User (caso de
uso de single-tenancy ativo) ou (b) reescrever o endpoint para iterar
sobre `user.companies`.

### 3. Routers `app/api/*.py` não incluídos no main.py
Apenas `routers/auth` está no `main.py`. Os routers em `api/` (ai, reports,
security, health, etc.) ainda não foram integrados.

**Ação:** integrar um por um, após validar que cada um compila e tem
testes mínimos.

### 4. Models de fases anteriores em backups
Há `models.py.backup.fase5/6/7/8` no projeto. Eles contêm models que
podem ainda ser necessários (ML, reports, etc.). Conferir, portar o que
for usado, deletar os backups.

### 5. Backups de código (`*.backup.fase*`)
Arquivos como `main.py.backup.fase2.20260511_1518`,
`ai_coordinator.py.backup.fase2.*` e similares devem ser deletados depois
de confirmação de que o `.gitignore` agora pega o padrão `*.backup.*`.

**Ação sugerida:**
```bash
find janus -name "*.backup.fase*" -type f -delete
```

### 6. Setup scripts `setup_fase*_completo.ps1`
Há 14+ scripts PowerShell de setup, um por fase. Eles totalizam ~1MB
e contêm código gerador. São equivalentes a "migrations não-versionadas".

**Ação:** decidir se ainda servem. Se sim, mover para `scripts/setup/`.
Se não, deletar.

### 7. Documentos de análise `_01_*.txt`, `_02_*.txt` ... `_08_git.txt`
Total ~13MB de análises antigas (tree dumps, stats). Estão no `.gitignore`
agora, mas continuam ocupando espaço no working dir.

**Ação sugerida:**
```bash
rm _01_*.txt _02_*.txt _03_*.txt _04_*.txt _05_*.txt _06_*.txt _07_*.txt _08_*.txt
```

### 8. Bancos `.db` antigos
`janus.db`, `juno.db`, `juno_migrated.db`, `alembic_bootstrap.db` — bancos
SQLite antigos no projeto, totalizando ~500KB. Estão no `.gitignore`.

**Ação sugerida:** deletar todos. Recriar via Alembic quando necessário.

### 9. Setup_Fase2_completo.ps1, scripts antigos na raiz
Arquivos `analise_janus_ai.ps1`, `check_line*.py`, `check_quotes.py`,
`fix_fase13.py` no raiz. Parecem one-off.

**Ação sugerida:** mover para `scripts/oneoff/` ou deletar.

## Como rodar a checklist

```bash
# Testes
cd janus/backend
pytest

# Lint
ruff check app/

# Verificar padroes de secrets antigos conhecidos
grep -rn "<secret-key-antiga>" janus/ \
  --include="*.py" --exclude-dir=.venv
grep -rn "<senha-db-antiga>" janus/ \
  --include="*.py" --exclude-dir=.venv
# (esperado: nenhum resultado)
```
