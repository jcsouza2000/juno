# JUNO Backup & Restore Runbook

Runbook simples para preparar o terreno de confianca sem contratar ferramenta externa neste momento.

## Objetivo

Garantir que o banco PostgreSQL do JUNO possa ser salvo e restaurado de forma repetivel.

## Politica inicial

- RPO alvo inicial: 24 horas.
- RTO alvo inicial: 4 horas.
- Retencao local inicial: 30 dias.
- Backup antes de migrations de producao: obrigatorio.

## Backup manual

No PowerShell, com `POSTGRES_PASSWORD` definido:

```powershell
$env:POSTGRES_PASSWORD="senha-do-postgres"
.\scripts\backup\backup_database.ps1 -ContainerName "juno-postgres" -RetentionDays 30
```

O script gera `juno_backup_YYYYMMDD_HHMMSS.zip` em `scripts\backups` por padrao.

## Restore manual

Use somente em ambiente controlado. O restore apaga o banco atual.

```powershell
$env:POSTGRES_PASSWORD="senha-do-postgres"
.\scripts\backup\restore_database.ps1 -BackupFile ".\scripts\backups\juno_backup_YYYYMMDD_HHMMSS.zip" -ContainerName "juno-postgres"
```

Digite `RESTAURAR` quando o script pedir confirmacao.

## Teste de restore

Antes de cliente pago, execute um teste de restore em ambiente separado:

1. Gere um backup.
2. Suba um banco limpo de teste.
3. Restaure o backup.
4. Rode `/api/v1/health/ready`.
5. Faça login e abra `/trust`, `/romi` e `/audit`.
6. Registre tempo total de recuperacao.

## Evolucao futura

Quando houver cliente com dados reais:

- mover backups para storage externo criptografado;
- automatizar agendamento;
- testar restore mensalmente;
- criar alerta de backup ausente;
- documentar responsavel e janela de recuperacao.
