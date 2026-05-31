# Scripts JUNO

## `setup_secrets.ps1`

Configura o backend localmente em uma chamada. Gera chaves criptográficas
seguras, escreve no `.env` e (opcionalmente) sobe a API.

**Importante**: as chaves são geradas localmente pelo Python na sua máquina.
Elas nunca aparecem na tela e nunca passam pelo chat com a IA.

### Uso típico (primeira vez)

```powershell
cd C:\Souza\Flutter\JANUS_AI
.\scripts\setup_secrets.ps1 -SmokeTest -StartServer
```

Isso:
1. Cria a `venv` se faltar e instala `requirements.txt`
2. Copia `.env.example` → `.env` se ainda não existir
3. Gera `SECRET_KEY` (86 chars) e `ENCRYPTION_KEY` (Fernet, 44 chars) se faltarem
4. Restringe permissão do `.env` ao usuário atual (Windows ACL)
5. Roda smoke test: valida config, faz roundtrip Fernet, importa todos os routers
6. Roda `pytest` curto
7. Sobe `uvicorn` em `http://localhost:8000`

### Re-rodar depois (uso normal)

```powershell
# Só sobe o servidor (chaves já existem)
.\scripts\setup_secrets.ps1 -StartServer

# Ou em outra porta
.\scripts\setup_secrets.ps1 -StartServer -Port 9000
```

### Trocar as chaves (rotação)

⚠️ **Atenção:** rotacionar `SECRET_KEY` invalida todos os JWTs (usuários
relogam). Rotacionar `ENCRYPTION_KEY` exige re-criptografar todos os
campos persistidos no banco — só faça com migration dedicada.

```powershell
.\scripts\setup_secrets.ps1 -Force
```

### Apenas validar sem subir nada

```powershell
.\scripts\setup_secrets.ps1 -SmokeTest
```

### Em ambientes onde PowerShell bloqueia scripts

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_secrets.ps1 -SmokeTest -StartServer
```

## `cleanup_legacy.ps1`

Remove artefatos legados de fases anteriores (backups `*.backup.fase*`,
dumps `_01_*.txt`, bancos `.db` antigos, scripts setup_fase*.ps1 etc.).
Idempotente — pode rodar quantas vezes quiser.

```powershell
.\scripts\cleanup_legacy.ps1
```

---

## Saída esperada do smoke test

```
=== Verificando ambiente ===
  [OK] Backend: C:\Souza\Flutter\JANUS_AI\janus\backend
  [OK] venv: C:\Souza\Flutter\JANUS_AI\janus\backend\.venv

=== Verificando .env ===
  [OK] .env já existe

=== Gerando/validando chaves ===
  [OK] SECRET_KEY gerada (len: 86)
  [OK] ENCRYPTION_KEY gerada (len: 44)
  [OK] .env atualizado
  [OK] Permissões do .env: somente o usuário atual

=== Smoke test (validação + crypto roundtrip) ===
JUNO_ENV: development
SECRET_KEY length: 86 (esperado >= 32)
ENCRYPTION_KEY length: 44 (esperado = 44)
DATABASE_URL configurada: False
CORS origins: ['http://localhost:3000', 'http://localhost:9050']
Crypto Fernet roundtrip: OK
Rotas registradas: 53+
  [OK] Smoke test passou
```
