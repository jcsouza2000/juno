# JUNO FASE 8 — API de Seguranca e Compliance

## Endpoints

### RBAC (Roles & Permissions)
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET    | /api/v1/security/roles | Listar papeis |
| POST   | /api/v1/security/roles | Criar papel |
| POST   | /api/v1/security/roles/assign | Atribuir papel |
| DELETE | /api/v1/security/roles/assign/{user_id}/{role_id} | Revogar papel |
| GET    | /api/v1/security/users/{id}/permissions | Permissoes do usuario |
| GET    | /api/v1/security/permissions/available | Listar permissoes |

### Auditoria
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST   | /api/v1/security/audit/query | Consultar logs |
| GET    | /api/v1/security/audit/resource/{type}/{id} | Data lineage |
| GET    | /api/v1/security/audit/statistics | Estatisticas |

### LGPD/GDPR
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST   | /api/v1/security/dsr | Criar requisicao |
| GET    | /api/v1/security/dsr | Listar requisicoes |
| POST   | /api/v1/security/dsr/{id}/process | Processar |
| POST   | /api/v1/security/consent | Registrar consentimento |
| GET    | /api/v1/security/consent/{email} | Verificar consentimento |
| POST   | /api/v1/security/consent/{id}/withdraw | Revogar |
| GET    | /api/v1/security/compliance/report | Relatorio compliance |

### Configuracoes
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET    | /api/v1/security/settings | Obter configuracoes |
| PUT    | /api/v1/security/settings | Atualizar |
| GET    | /api/v1/security/login-attempts | Tentativas de login |
| GET    | /api/v1/security/login-attempts/stats | Estatisticas |

## Permissoes Disponiveis

| Codigo | Recurso | Acao |
|--------|---------|------|
| product.read | Produtos | Leitura |
| product.write | Produtos | Escrita |
| product.delete | Produtos | Exclusao |
| customer.read | Clientes | Leitura |
| order.read | Pedidos | Leitura |
| order.write | Pedidos | Escrita |
| report.read | Relatorios | Leitura |
| report.export | Relatorios | Exportacao |
| ml_model.read | Modelos ML | Leitura |
| ml.predict | Predicoes | Execucao |
| erp.read | ERP | Leitura |
| erp.sync | ERP | Sincronizacao |
| user.read | Usuarios | Leitura |
| role.manage | Papeis | Gestao |
| audit.read | Auditoria | Leitura |
| dsr.manage | DSR | Gestao |
| admin.full | Admin | Total |

## Papeis do Sistema

| Papel | Permissoes |
|-------|-----------|
| Administrador | Todas |
| Gerente | Produtos, Clientes, Pedidos, Relatorios, ERP |
| Analista | Leitura + Relatorios + ML |
| Operador | Produtos, Clientes, Pedidos |
| Visualizador | Apenas leitura |
