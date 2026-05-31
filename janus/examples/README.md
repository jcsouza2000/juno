# Examples — Dados de demonstração

Esta pasta contém dados de exemplo usados para demos e testes.

- `data/romi_products.csv`, `data/fachini_products.csv` — produtos de demo (clientes-exemplo).
- `templates/` — templates CSV em branco que o usuário pode baixar para preencher e importar via upload no app:
  - `products_template.csv`
  - `customers_template.csv`
  - `sales_orders_template.csv`
  - `production_orders_template.csv`

Estes arquivos **não devem ser usados em produção**. Eles existem apenas para
facilitar testes manuais e demonstração da feature de ERP importer
(`app/integrations/erp_importer.py`).
