# RUNBOOK: Security Incident (Suspected Breach)

## Sintomas
- Spike de 401/403
- IPs suspeitos no access log
- Dados anomalos no audit log

## Diagnostico
1. Verificar access logs: grep '401|403' /var/log/nginx/access.log | tail -50
2. Check audit trail: SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '1 hour' ORDER BY id DESC;
3. Analisar rate limit hits: redis-cli ZREVRANGE rate_limit:blocked 0 20 WITHSCORES

## Acao
1. Block IP: Adicionar IP ao firewall/nginx deny
2. Revoke tokens: Invalidar todas as sessions do usuario
3. Force MFA: Requerer re-autenticacao para todos os usuarios
4. Snapshot: Criar snapshot do DB para forense
5. Notificar: Email para security@juno.ai + DPO
