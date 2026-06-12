# Go-live externo — JUNO Piloto

Checklist para expor o JUNO na internet (domínio real, HTTPS).

## Pré-requisitos

- [ ] Domínio registrado (ex.: `app.seudominio.com.br`, `api.seudominio.com.br`)
- [ ] Servidor ou cloud com Docker + reverse proxy (nginx/traefik/Caddy)
- [ ] Certificado TLS (Let's Encrypt ou corporativo)
- [ ] PostgreSQL gerenciado ou container com backup diário
- [ ] Redis acessível na rede interna

## 1. Gerar `.env.prod` de produção

```powershell
cd C:\Souza\juno
janus\backend\.venv\Scripts\python.exe scripts\generate_env_prod.py
```

Edite `.env.prod` e substitua **todos** os valores localhost:

| Variável | Exemplo go-live |
|----------|-----------------|
| `ALLOWED_ORIGINS` | `https://app.seudominio.com.br` |
| `NEXT_PUBLIC_API_URL` | `https://api.seudominio.com.br` |
| `POSTGRES_PASSWORD` | senha forte única |
| `SECRET_KEY`, `ENCRYPTION_KEY`, `NEXTAUTH_SECRET`, `AUTH_SECRET` | gerados pelo script (não reutilizar dev) |

Validar:

```powershell
powershell -NoProfile -File scripts\prod_hardening_check.ps1 -EnvFile .env.prod
```

Esperado: **0 erros** (sem aviso de localhost).

## 2. Deploy Docker prod

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod -p juno-prod up -d --build
docker exec juno-prod-juno-backend-1 python -m app.bootstrap_prod_local
```

> **Nota:** use `docker-compose.prod.local.yml` **apenas** em máquina de dev (portas 8002/4002). Em servidor real, use só `docker-compose.prod.yml` + proxy HTTPS.

Smoke pós-deploy:

```powershell
powershell -NoProfile -File scripts\pilot_prod_smoke.ps1 -Base https://api.seudominio.com.br -CompanyId 1
```

## 3. Reverse proxy (exemplo nginx)

- Terminar TLS em `443`
- `app.seudominio.com.br` → frontend `:4000`
- `api.seudominio.com.br` → backend `:8000`
- Não expor `:11434` (Ollama) na internet

## 4. Checklist manual UI

Siga `docs/PILOT_E2E_CHECKLIST.md` no browser de produção com login real (`admin@juno.local` ou admin do cliente).

## 5. Go / No-go

| Go | No-go |
|----|-------|
| `prod_hardening_check` sem erros | `JUNO_DEV_AUTH_BYPASS=true` |
| Smoke prod 6/6 na URL pública | SQLite em prod |
| HTTPS ativo | CORS `*` ou segredos de exemplo |
| Checklist manual sem bloqueadores | Erro 500 em rotas críticas |

## Referências

- `docs/PROD_HARDENING_CHECKLIST.md`
- `docs/E2E_VALIDATION_RESULT.md`
- `SECURITY_ENV_REVIEW.md`
