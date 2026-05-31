# Revisao de seguranca de ambientes

Data da revisao: 2026-05-24.

## Arquivos locais sensiveis

Os arquivos abaixo existem localmente ou podem existir por ambiente e devem continuar fora do Git:

- `.env.prod`
- `deploy/.env.production`
- `deploy/.env.staging`
- `janus/backend/.env`
- `janus/frontend/.env.local`

O `.gitignore` da raiz mantem `.env*` ignorado, com excecao apenas para exemplos versionaveis.

## Variaveis obrigatorias para producao

Antes de subir a stack real, preencher valores fortes e exclusivos:

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `ALLOWED_ORIGINS`
- `LOGIN_RATE_LIMIT`
- `NEXT_PUBLIC_API_URL`
- `NEXTAUTH_SECRET`
- `AUTH_SECRET`

## Comandos seguros para gerar segredos

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -base64 32
```

## Regra antes de commit/publicacao

Rodar estes comandos e revisar qualquer saida:

```powershell
git status --ignored
rg -n "SECRET_KEY|POSTGRES_PASSWORD|ENCRYPTION_KEY|NEXTAUTH_SECRET|AUTH_SECRET|password|token" -g "!node_modules" -g "!.venv" -g "!*.lock"
```

Nao commitar valores reais, dumps de banco, chaves, tokens, logs de producao ou arquivos `.env`.
