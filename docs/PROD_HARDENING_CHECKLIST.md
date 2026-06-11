# Checklist de hardening para produção — JUNO Piloto

Use antes de expor o JUNO a clientes externos ou internet pública.

## 1. Variáveis de ambiente

Copie `.env.prod.example` → `.env.prod` e preencha **valores exclusivos** (nunca reutilize chaves de dev).

| Variável | Obrigatório | Valor esperado |
|----------|-------------|----------------|
| `JUNO_ENV` | Sim | `production` |
| `JUNO_DEV_AUTH_BYPASS` | Sim | `false` |
| `DATABASE_URL` | Sim | `postgresql://...` (não SQLite) |
| `SECRET_KEY` | Sim | ≥ 32 chars, gerada com `secrets.token_urlsafe(64)` |
| `ENCRYPTION_KEY` | Sim | Fernet válida |
| `ALLOWED_ORIGINS` | Sim | Domínios HTTPS reais (sem `localhost`) |
| `NEXT_PUBLIC_API_URL` | Sim | URL pública da API |
| `NEXTAUTH_SECRET` / `AUTH_SECRET` | Sim | ≥ 32 chars |
| `LOGIN_RATE_LIMIT` | Recomendado | `5/minute` |
| `LOG_FORMAT` | Recomendado | `json` |

Validação automatizada:

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\prod_hardening_check.ps1 -EnvFile C:\Souza\juno\.env.prod
```

## 2. Infraestrutura

- [ ] Docker Desktop ativo; `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`
- [ ] `alembic upgrade head` executado no container backend
- [ ] PostgreSQL com backup diário configurado
- [ ] Redis disponível (rate limit / filas)
- [ ] HTTPS terminado no reverse proxy (nginx/traefik)
- [ ] Ollama acessível apenas na rede interna (não expor `:11434` na internet)

## 3. Segurança de aplicação

- [ ] Login real testado (admin + usuário comum)
- [ ] `403` ao acessar tenant alheio via API
- [ ] Purge `/data/{id}/purge` restrito a admin do tenant
- [ ] Ativação de versão restrita a admin do tenant
- [ ] Nenhum `.env` real no Git (`git status --ignored`)
- [ ] Revisão `SECURITY_ENV_REVIEW.md` concluída

## 4. Dados e retenção

- [ ] Job snapshot diário agendado (`scripts/schedule_daily_snapshot.ps1` como Admin)
- [ ] Política de retenção documentada para o cliente
- [ ] Uploads versionados (Fase B) — admin sabe usar `/data`

## 5. Smoke pós-deploy

```powershell
powershell -NoProfile -File C:\Souza\juno\scripts\pilot_e2e_smoke.ps1 -Base https://api.seudominio.com.br -CompanyId 1
```

Esperado: **10/10 OK** (inclui comparativos por cenário e versionamento).

## 6. Checklist manual UI

Siga `docs/PILOT_E2E_CHECKLIST.md` no browser de produção/staging.

## 7. Go / No-go

**Go** se: smoke 10/10, checklist manual sem bloqueadores, segredos rotacionados, bypass desligado.

**No-go** se: SQLite em prod, bypass ativo, CORS com `*`, ou EV/comparativos retornando erro 500.
