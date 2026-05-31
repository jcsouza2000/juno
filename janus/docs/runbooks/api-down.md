# RUNBOOK: API Indisponivel (503/502)

## Sintomas
- Health check falhando
- Latencia alta (> 2s)
- Erro 503/502 em cascata

## Diagnostico Rapido (5 min)
1. Verificar status dos containers: docker ps | grep juno
2. Checar logs do backend: docker logs --tail 100 juno_api
3. Verificar conectividade DB: docker exec juno_api python -c 'from app.core.database import engine; engine.connect()'
4. Check CPU/Memoria: docker stats --no-stream

## Acao Imediata
1. Restart graceful: docker-compose restart api
2. Scale up workers: docker-compose up -d --scale api=3
3. Circuit breaker: Ativar modo degradado no nginx
4. Rollback: docker-compose pull api:previous && docker-compose up -d

## Escalonamento
- > 10 min sem resolucao: Page SRE on-call
- > 30 min: Ativar war room
