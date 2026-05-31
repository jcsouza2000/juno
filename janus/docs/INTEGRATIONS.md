# JUNO AI - Integracoes & APIs Externas

## Arquitetura de Integracoes

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Webhooks  â”‚  â”‚     ERP     â”‚  â”‚     CRM     â”‚
â”‚   Engine    â”‚  â”‚ Connectors  â”‚  â”‚  Connectors â”‚
â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜
       â”‚                â”‚                â”‚
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                        â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚   JUNO API        â”‚
              â”‚   (FastAPI)       â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                        â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚                â”‚                â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”
â”‚   Payments  â”‚  â”‚  Messaging  â”‚  â”‚     ETL     â”‚
â”‚  Gateway    â”‚  â”‚   Queue     â”‚  â”‚  Pipeline   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## Webhooks Engine

- Assinatura HMAC-SHA256 em todos os webhooks
- Retry automatico com backoff exponencial
- Dashboard de entregas no Flutter

## ERP Connectors

| ERP | Protocolo | Autenticacao |
|-----|-----------|--------------|
| SAP | OData REST | Basic Auth + CSRF |
| TOTVS | REST API | OAuth2 |
| Odoo | XML-RPC | Login/Password |

## CRM Connectors

| CRM | Protocolo | Autenticacao |
|-----|-----------|--------------|
| Salesforce | REST API | OAuth2 Password |
| HubSpot | REST API | Bearer Token |

## Payment Gateways

| Gateway | Recursos |
|---------|----------|
| Stripe | Subscriptions, PaymentIntent, Invoices |
| Pagar.me | Orders, Subscriptions, Boleto, PIX |

## API Publica

- OpenAPI 3.0 spec em `/v1/public/docs/openapi.json`
- OAuth2 com client credentials
- Rate limit por tier: Free(60/min), Basic(300/min), Pro(1000/min), Enterprise(5000/min)

## Message Queue

| Provider | Use Case |
|----------|----------|
| RabbitMQ | Eventos internos, webhooks outbound |
| Kafka | Event streaming, analytics, audit |

## ETL Pipeline

- Import: CSV, Excel (XLSX)
- Export: CSV, Excel (XLSX)
- Transformers: uppercase, trim, parse_dates
- Validators: required_fields, email_format
- Agendamento via cron expressions

## Variaveis de Ambiente

Ver `.env.example` para todas as variaveis necessarias.
