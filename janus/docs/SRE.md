# JUNO AI - Observabilidade & SRE

## Stack de Observabilidade

| Componente | Funcao | Porta |
|------------|--------|-------|
| Jaeger | Distributed Tracing | 16686 |
| Loki | Log Aggregation | 3100 |
| Promtail | Log Collection | 9080 |
| Alertmanager | Alert Routing | 9093 |
| Grafana | Visualization | 3000 |
| Sentry | Error Tracking | SDK |

## SLOs Definidos

1. **API Availability**: 99.9% uptime (30d window)
2. **P99 Latency**: < 500ms (7d window)
3. **Error Rate**: < 0.1% (7d window)
4. **DB Connection Pool**: < 80% utilization (1d window)

## Error Budget

- Budget total = 100% - SLO target
- Burn rate = budget consumido / tempo decorrido
- Alertar quando burn rate > 1x (exaurir em 30 dias)
- Page quando burn rate > 2x (exaurir em 15 dias)

## Runbooks

Consulte `/docs/runbooks/` para procedimentos de:
- API indisponivel
- Degradacao de DB
- Incidente de seguranca

## Chaos Engineering

Execute testes de resiliencia:
```bash
./scripts/chaos.sh api     # Kill pods
./scripts/chaos.sh db      # Carga extrema
./scripts/chaos.sh network # Particao de rede
```

## Alertas

### Severidades
- **Critical**: Page imediato (PagerDuty)
- **Warning**: Slack #sre-alerts
- **Info**: Email digest

### Rotas
- `api-*` alerts -> SRE team
- `db-*` alerts -> DBA team
- `security-*` alerts -> Security team
