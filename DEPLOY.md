# Deploy JUNO

O compose oficial de producao e `docker-compose.prod.yml` na raiz do projeto. O compose antigo de `deploy/` foi arquivado em `_archive/legacy_deploy/` para evitar duas fontes concorrentes.

## Preparacao

Copie o exemplo e preencha valores reais:

```powershell
Copy-Item .env.prod.example .env.prod
```

Variaveis obrigatorias:

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `ALLOWED_ORIGINS`
- `LOGIN_RATE_LIMIT`
- `NEXT_PUBLIC_API_URL`
- `NEXTAUTH_SECRET`
- `AUTH_SECRET`

`NEXT_PUBLIC_API_URL` tambem entra como build argument do frontend. Se esse valor mudar, reconstrua a imagem do frontend.

## Validacao do compose

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
```

## Build

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml build
```

## Subida

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Endpoints esperados em uma subida local:

- Frontend: `http://localhost:4000`
- Backend: `http://localhost:8000/health`

## Encerramento

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```
