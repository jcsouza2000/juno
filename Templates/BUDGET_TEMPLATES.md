# Templates de Orçamento e Budget (Fase C)

## Arquivos

| Arquivo | Uso |
|---------|-----|
| `Templates/Demonstrações Financeiras_Templates.xlsx` | Workbook canônico do piloto — colunas **Orçamento** e **Budget** após 2025 (DRE e EBITDA) |
| `janus/frontend/public/templates/template_demonstracoes_orcamento.xlsx` | Upload de metas orçamentárias (PT), periodo `2025-ORC` |
| `janus/frontend/public/templates/template_demonstracoes_budget.xlsx` | Upload de metas budget (EN), periodo `2025-BUD` |
| `Templates/Demonstrações Financeiras_Templates.xlsx.bak` | Backup antes da inserção das colunas |

## Metas anuais 2025 (R$ milhões)

| Indicador | Realizado | Orçamento/Budget |
|-----------|-----------|------------------|
| Receita Líquida | 20.697,51 | 21.350,00 |
| EBITDA Ajustado | 7.848,12 | 8.050,00 |
| Lucro Líquido | 1.678,21 | 1.720,00 |

Variação realizado vs orçamento: ~**−3,1%** na receita (empresa abaixo da meta).

## Regenerar

```powershell
cd C:\Souza\juno
janus\backend\.venv\Scripts\python.exe scripts\build_budget_templates.py
```

## UI

- **Demonstrações** → links para template realizado, Orçamento e Budget
- **KPIs Executivos** → aba **Cenários** lê coluna Orçamento do workbook canônico
