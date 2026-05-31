# RUNBOOK: Database Performance Degradation

## Sintomas
- Query timeout > 5s
- Connection pool exhaustion
- Deadlock errors

## Diagnostico
1. Verificar locks ativos: SELECT * FROM pg_locks WHERE NOT granted;
2. Queries lentas: SELECT query, query_start, state FROM pg_stat_activity WHERE state = 'active' ORDER BY query_start;
3. Tamanho das tabelas: SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size DESC;

## Acao
1. Kill queries bloqueadas: SELECT pg_terminate_backend(pid)
2. Vacuum analyze: docker exec juno_db psql -U postgres -c 'VACUUM ANALYZE;'
3. Aumentar pool: Editar SQLALCHEMY_POOL_SIZE no .env
4. Read replica: Redirecionar reads para replica (se configurado)
