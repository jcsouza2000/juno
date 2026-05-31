# Secrets para CI/CD - ProsperCode AI

## GitHub Secrets (Settings -> Secrets and variables -> Actions)

### Railway
| Nome | Valor | Descricao |
|------|-------|-----------|
| RAILWAY_TOKEN_STAGING | railway_... | Token de deploy para ambiente staging |
| RAILWAY_TOKEN_PROD | railway_... | Token de deploy para producao |
| RAILWAY_PROJECT_ID | proj_... | ID do projeto Railway |

### Fly.io
| Nome | Valor | Descricao |
|------|-------|-----------|
| FLY_API_TOKEN_STAGING | FlyV1_... | API token Fly.io staging |
| FLY_API_TOKEN_PROD | FlyV1_... | API token Fly.io producao |

### Aplicacao
| Nome | Valor | Descricao |
|------|-------|-----------|
| DATABASE_URL | postgresql://... | URL do PostgreSQL production |
| REDIS_URL | redis://... | URL do Redis |
| OPENAI_API_KEY | sk-proj-... | Chave OpenAI |
| LANGFUSE_SECRET_KEY | sk-lf-... | Langfuse secret |
| LANGFUSE_PUBLIC_KEY | pk-lf-... | Langfuse public |
| JWT_SECRET | ... | Segredo JWT |
| SLACK_WEBHOOK | https://hooks.slack.com/... | Webhook para notificacoes |

## Variaveis de Repository (Settings -> Variables -> Actions)
| Nome | Valor | Descricao |
|------|-------|-----------|
| DEPLOY_FLY | true ou false | Habilita deploy Fly.io como fallback |
| RAILWAY_PROJECT_ID | ... | ID para rollback automatico |