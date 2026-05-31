# JUNO — Checklist de Validação no Windows real

Checklist pragmático para você rodar antes de subir pra demo/cliente. Todos
os passos rodam na venv do JUNO (`janus\backend\.venv\`).

## 1. Instalar deps novas (Ontology Engine + SDK)

```cmd
cd C:\Souza\Flutter\JANUS_AI\janus\backend
.venv\Scripts\pip install -r requirements.txt
```

Devem aparecer instalados: `PyYAML 6.0.3`, `asteval 1.0.5`, `Jinja2 3.1.6`.

> O SmartJuno.bat agora também detecta e instala automaticamente
> se faltarem.

## 2. Rodar a migration Alembic

```cmd
.venv\Scripts\alembic current   :: confirma head antes
.venv\Scripts\alembic upgrade head
```

A migration `ontology_sem8` cria a tabela `user_markings`. Em SQLite dev,
`create_all` também cria — sem conflito.

## 3. Validar a ontologia

```cmd
set PYTHONPATH=.
.venv\Scripts\python -m app.ontology.cli validate --skip-models
```

Esperado: `✓ Todas as validações passaram` com 5 ObjectTypes, 7 ActionTypes,
1 MarkingSet.

## 4. Rodar os testes da ontologia

```cmd
.venv\Scripts\python -m pytest app/ontology/tests/ -v --no-cov
```

Devem passar 132+ testes. `pytest.ini` foi atualizado para coletar o
diretório automaticamente, então `pytest` puro também funciona.

## 5. Suite completa

```cmd
.venv\Scripts\python -m pytest -v --no-cov
```

Se algum teste antigo quebrar (provavelmente em `app/tests/` legado), abra
issue separada — não está no escopo do Ontology Engine.

## 6. Subir o backend

```cmd
SmartJuno.bat
```

O script agora:
- Detecta `PyYAML/asteval/Jinja2` faltantes e instala
- Seta `ONTOLOGY_ENABLED=true` automaticamente
- Faz health-check antes de abrir o browser

## 7. Smoke test manual

Depois do `SmartJuno.bat`:

```cmd
:: 7.1 Tipos carregados
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:9050/api/v1/ontology/types

:: 7.2 Markings declaradas
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:9050/api/v1/markings

:: 7.3 Buscar produto
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:9050/api/v1/ontology/Produto/10

:: 7.4 Lineage (vazio até primeira action)
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:9050/api/v1/ontology/lineage/Produto/10

:: 7.5 Tools auto-geradas para a IA
curl -H "Authorization: Bearer SEU_TOKEN" http://localhost:9050/api/v1/ontology/tools

:: 7.6 Metrics
curl http://localhost:9050/metrics | findstr juno_ontology
```

## 8. UI

- `http://localhost:4000/ai` — Coordinator agora propõe Actions com card de confirmação
- `http://localhost:4000/admin/markings` — admin gerencia grants (não-admin é redirecionado)

## 9. Gaps conhecidos (não corrigidos nesta entrega)

- **Services legados (`/dashboard/cfo/1`, `/insights/1`) ainda bypassam markings.** Use
  `app/services/ontology_dashboards.py` (`*_v2`) ao migrar rotas.
- **Latência do Coordinator:** com 29 tools, o probe do Ollama vai
  para ~20-30s por turno. Reduza desligando ontology no `.env`
  (`ONTOLOGY_ENABLED=false`) ou rode com modelo maior.
- **Apresentação PowerPoint** ainda na v0.1.1 — regenere quando for demo.
- **audit_logs:** rode `python scripts/audit_retention.py --keep-days 365`
  por cron quando ultrapassar ~1M rows.

## 10. Reverter (se algo der ruim)

```cmd
:: Desliga Ontology sem mexer em código
echo ONTOLOGY_ENABLED=false >> janus\backend\.env

:: Reverte migration de markings
.venv\Scripts\alembic downgrade audit_2026_05
```
