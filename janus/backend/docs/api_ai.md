# JUNO FASE 6 — API de Inteligência Artificial

## Endpoints

### Modelos de ML

GET    /api/v1/ai/models?company_id=1&model_type=demand_forecast
POST   /api/v1/ai/models                    # Criar modelo
POST   /api/v1/ai/models/auto-ml            # Auto-ML
GET    /api/v1/ai/models/{model_id}         # Detalhes
DELETE /api/v1/ai/models/{model_id}         # Remover
plain
Copy

### Predições
POST   /api/v1/ai/predict                   # Gerar predição
GET    /api/v1/ai/predictions               # Listar predições
plain
Copy

### Anomalias
GET    /api/v1/ai/anomalies?severity=high&acknowledged=false
POST   /api/v1/ai/anomalies/{id}/acknowledge
plain
Copy

### Chatbot
POST   /api/v1/ai/chat                      # Enviar mensagem
GET    /api/v1/ai/chat/history/{session_id}
plain
Copy

### Recomendações
GET    /api/v1/ai/recommendations
POST   /api/v1/ai/recommendations/{id}/apply
plain
Copy

### Dashboard
GET    /api/v1/ai/dashboard                 # Resumo consolidado
plain
Copy

## Algoritmos Suportados

| Algoritmo | Tipo | Uso |
|-----------|------|-----|
| prophet | Séries Temporais | Previsão de demanda/vendas |
| random_forest | Regressão | Predição com múltiplas features |
| isolation_forest | Anomalia | Detecção de outliers |
| arima | Séries Temporais | Forecast clássico |

## Intenções do Chatbot

- `sales_forecast` — Previsão de vendas
- `inventory_status` — Status de estoque
- `anomaly_alert` — Alertas de anomalias
- `recommendation` — Recomendações
- `product_info` — Informações de produto
- `customer_info` — Informações de cliente
- `order_status` — Status de pedidos
- `financial_summary` — Resumo financeiro
