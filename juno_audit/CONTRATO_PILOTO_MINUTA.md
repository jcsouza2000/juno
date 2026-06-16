# MINUTA — TERMO DE PROJETO PILOTO JUNO_AI (1 página)
**Documento de trabalho para revisão por advogado. Não constitui aconselhamento jurídico.**

---

**CONTRATADA:** [JUNO_AI / razão social], CNPJ [—] ("JUNO")
**CONTRATANTE:** [Empresa Piloto], CNPJ [—] ("CLIENTE")
**Objeto:** Projeto piloto de diagnóstico operacional com IA governada — módulos **Score Industrial + KPIs Executivos** — sobre dados do ERP do CLIENTE ([Sankhya/TOTVS/Senior]), em modalidade [cloud/on-premise], **sem movimentação de dados para fora do ambiente acordado**.

**1. Prazo e fases.** 90 (noventa) dias a partir da liberação de acesso ao ERP. Mês 1: integração (somente leitura) e validação de dados. Mês 2: operação assistida com reuniões quinzenais de 30 min. Mês 3: operação autônoma do painel e relatório executivo final.

**2. Preço.** Taxa única de implantação de R$ [1.500–3.000]. Sem mensalidade durante o piloto. Conversão pós-piloto pré-acordada: mensalidade de R$ [—] com **desconto vitalício de 20% (condição de cliente pioneiro)**, exercível em até 30 dias do término.

**3. Critérios de sucesso (aferidos no relatório final).** (a) Score Industrial calculado com ≥ 95% dos dados do ERP reconciliados; (b) ao menos 2 insights classificados pelo gestor como novos/acionáveis; (c) painel consultado ≥ 1×/semana pelo decisor no Mês 3.

**4. Contrapartidas do CLIENTE.** (a) Ponto focal com até 2h/semana de disponibilidade; (b) acesso de leitura ao ERP no escopo acordado; (c) autorização de **estudo de caso publicável** com nome da empresa e métricas (texto sujeito a aprovação prévia do CLIENTE) e depoimento do decisor, condicionados ao atingimento dos critérios da cláusula 3.

**5. Matriz Risco × Autonomia (regra de operação da IA).**

| Classe | Exemplos no piloto | Autonomia do agente | Registro |
|---|---|---|---|
| **BAIXO** | Leitura de dados do ERP; cálculo de Score e KPIs; geração de relatórios | Executa e registra | Trilha de auditoria |
| **MODERADO** | Alertas e notificações a usuários; reclassificação de indicadores | Executa, registra e **notifica** o ponto focal | Trilha + notificação |
| **ALTO** | Qualquer recomendação de decisão com impacto financeiro estimado > R$ [50.000]; qualquer escrita no ERP | **Apenas recomenda**; execução exige **aprovação humana registrada** (HITL) | Trilha + aprovação assinada |
| **VEDADO** | Escrita no ERP fora de escopo; pagamentos; dados pessoais fora da base legal LGPD | Bloqueado por configuração | Tentativas registradas |

**6. Trilha de auditoria.** Toda análise, recomendação e aprovação humana é registrada em trilha criptográfica encadeada (hash SHA-256), com fechamentos periódicos verificáveis de forma independente pelo CLIENTE mediante ferramenta fornecida pela JUNO. A trilha é a referência para apuração de qualquer divergência entre as partes.

**7. Responsabilidade.** (a) A JUNO responde por falhas de análise dos seus agentes nos limites da Matriz da cláusula 5; (b) o CLIENTE responde pela qualidade e veracidade dos dados de origem do ERP e pelas decisões humanas tomadas, inclusive as contrárias às recomendações; (c) a responsabilidade total da JUNO fica **limitada ao valor pago pelo CLIENTE no piloto**, excluídos lucros cessantes e danos indiretos, ressalvados dolo ou violação de confidencialidade/LGPD.

**8. LGPD e confidencialidade.** As partes atuam em conformidade com a Lei 13.709/2018. A JUNO trata dados na condição de operadora, exclusivamente para as finalidades deste Termo, com eliminação ou devolução ao término, salvo hashes da trilha de auditoria (que não contêm dados pessoais). Sigilo recíproco sobre informações não públicas por 5 anos.

**9. Encerramento.** Qualquer parte pode encerrar com aviso de 15 dias. Encerrado o piloto sem conversão, a JUNO revoga acessos em até 5 dias úteis e entrega ao CLIENTE o export final da sua trilha.

**Local/data:** _____________________  
**JUNO:** _____________________ **CLIENTE:** _____________________

---
*Campos entre colchetes a preencher. Recomenda-se revisão jurídica antes da assinatura, em especial cláusulas 5, 7 e 8.*
