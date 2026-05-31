# JUNO FASE 7 — API de Relatórios & BI

## Endpoints

### Templates
GET    /api/v1/reports/templates                    # Listar templates
POST   /api/v1/reports/templates/{key}/create       # Criar do template
plain
Copy

### Relatórios
POST   /api/v1/reports/definitions                  # Criar relatório
GET    /api/v1/reports/definitions                  # Listar relatórios
GET    /api/v1/reports/definitions/{id}             # Detalhes
PUT    /api/v1/reports/definitions/{id}             # Atualizar
DELETE /api/v1/reports/definitions/{id}             # Remover
POST   /api/v1/reports/definitions/{id}/execute     # Executar
POST   /api/v1/reports/definitions/{id}/export      # Exportar (PDF/Excel/CSV)
plain
Copy

### Dashboards
POST   /api/v1/reports/dashboards                   # Criar dashboard
GET    /api/v1/reports/dashboards                   # Listar
GET    /api/v1/reports/dashboards/{id}              # Renderizar com dados
PUT    /api/v1/reports/dashboards/{id}              # Atualizar
DELETE /api/v1/reports/dashboards/{id}              # Remover
plain
Copy

### Execuções
GET    /api/v1/reports/executions                   # Histórico
plain
Copy

### Entidades
GET    /api/v1/reports/entities                     # Entidades disponíveis
plain
Copy

## Formatos de Exportação

| Formato | MIME Type | Extensão |
|---------|-----------|----------|
| PDF | application/pdf | .pdf |
| Excel | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | .xlsx |
| CSV | text/csv | .csv |
| JSON | application/json | .json |

## Tipos de Widgets de Dashboard

| Tipo | Descrição |
|------|-----------|
| table | Tabela de dados com ordenação |
| chart | Gráfico (bar, line, pie, area) |
| kpi | Indicador chave com tendência |
| pivot | Tabela dinâmica |
