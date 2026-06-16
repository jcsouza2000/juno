# Baseline de Segurança de Dependências (pip-audit)

Triagem das vulnerabilidades reportadas por `pip-audit -r requirements.txt`.
Atualize a cada rodada; remova o `|| true` do step `pip-audit` no CI quando o
baseline restante estiver aceito/zerado.

## Decisão de triagem (2026-06)

### ✅ Corrigidas e validadas (bumps minor/patch, suíte 267 verde)

| Pacote | De | Para | CVEs cobertas |
|---|---|---|---|
| python-jose[cryptography] | 3.3.0 | 3.4.0 | PYSEC-2024-232/233 (JWT/JWE) |
| PyJWT | 2.8.0 | 2.13.0 | PYSEC-2026-120/175..179 (JWT) |
| PyNaCl | 1.5.0 | 1.6.2 | CVE-2025-69277 (assinatura Ed25519 do ledger) |
| cryptography | 42.0.8 | 44.0.1 | CVE-2024-12797, GHSA-h4gh-qq45-vh27 (parcial — ver diferidas) |
| bleach | 6.1.0 | 6.4.0 | GHSA-gj48-438w-jh9v, GHSA-8rfp-98v4-mmr6 |
| asteval | 1.0.5 | 1.0.6 | CVE-2025-24359 |
| python-dotenv | 1.0.1 | 1.2.2 | CVE-2026-28684 |

Validação: `jose` faz round-trip de JWT, `juno_audit` (assinatura) verde com
PyNaCl 1.6.2, e a suíte (267) passa com todos os bumps.

### ⏸️ Diferidas — exigem upgrade coordenado (risco de quebra / acopladas ao FastAPI)

| Pacote | Atual | Fix | Por que diferir |
|---|---|---|---|
| starlette | 0.38.6 (transitive de fastapi==0.115.0) | ≥0.40 / 1.x | Fix pleno exige FastAPI mais novo; starlette 1.x quebra o range do FastAPI 0.115. |
| python-multipart | 0.0.17 (transitive) | 0.0.31 | Acoplado ao FastAPI; subir junto com o upgrade do FastAPI. |
| cryptography | 44.0.1 | 46.x/48.x | Salto de major; revalidar com python-jose e o stack de TLS antes. |
| pyasn1 | 0.4.8 (transitive) | 0.6.3 | Transitive (jose/rsa); validar cadeia de assinatura. |
| PyJWT (PYSEC-2025-183) | 2.13.0 | — | Sem versão de correção publicada; monitorar. |

**Plano:** uma janela dedicada de "upgrade de plataforma" (FastAPI + Starlette +
python-multipart + cryptography major), com a suíte + smoke E2E como gate.

## Como reproduzir
```bash
cd janus/backend
pip install pip-audit
pip-audit -r requirements.txt --desc on
```
