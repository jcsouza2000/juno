"""
Eval offline do Coordinator (sem Ollama) — Fase 4/Item 5.

Nao avalia o roteamento do LLM (exigiria o modelo), mas trava garantias
DETERMINISTICAS que reduzem o risco de a IA "inventar numero" ou ficar sem
guidance:

  1. Cobertura de capabilities: TODA tool do Coordinator tem >=1 intent no
     playbook (uma tool nova sem guidance falha o eval).
  2. Qualidade de cada intent: id unico, >=1 pergunta, >=1 tool, resposta nao
     vazia (instrucao de formato).
  3. Perguntas-golden: um conjunto curado de perguntas executivas — cada uma
     tem sobreposicao de palavras-chave com os exemplos de algum intent
     (proxy de cobertura; pega lacunas no playbook).
"""

from __future__ import annotations

import re

from app.ai_coordinator import TOOLS
from app.ai_playbook import load_playbook

_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}  # type: ignore[index]

# Perguntas executivas representativas -> ao menos um intent deve cobri-las.
GOLDEN_QUESTIONS = [
    "como está a saúde da minha empresa",
    "quais produtos estão dando prejuízo",
    "quem são meus maiores clientes",
    "quais produtos concentram a receita",
    "tenho ordens de produção atrasadas",
    "os dados estão confiáveis para o conselho",
    "como estão minhas margens e o resultado",
    "quanto vale a empresa",
    "faça um diagnóstico completo",
    "quais os principais riscos do negócio",
]

_STOPWORDS = {
    "a",
    "o",
    "os",
    "as",
    "de",
    "da",
    "do",
    "e",
    "minha",
    "meu",
    "para",
    "como",
    "esta",
    "está",
    "sao",
    "são",
    "quais",
    "quem",
    "um",
    "uma",
    "no",
    "na",
    "the",
    "com",
    "que",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zà-ú]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def test_cobertura_total_de_capabilities():
    """Toda tool do Coordinator precisa de pelo menos um intent no playbook."""
    pb = load_playbook()
    referenced = {tool for intent in pb["intents"] for tool in intent["tools"]}
    sem_guidance = _TOOL_NAMES - referenced
    assert not sem_guidance, f"tools sem guidance no playbook: {sem_guidance}"


def test_qualidade_dos_intents():
    pb = load_playbook()
    ids_vistos: set[str] = set()
    for intent in pb["intents"]:
        iid = intent.get("id")
        assert iid, "intent sem id"
        assert iid not in ids_vistos, f"intent duplicado: {iid}"
        ids_vistos.add(iid)
        assert intent.get("perguntas"), f"{iid}: sem perguntas"
        assert intent.get("tools"), f"{iid}: sem tools"
        assert str(intent.get("resposta", "")).strip(), f"{iid}: sem formato de resposta"


def test_perguntas_golden_tem_cobertura():
    pb = load_playbook()
    # Vocabulario de todas as perguntas-exemplo do playbook.
    intent_token_sets = [_tokens(" ".join(intent.get("perguntas", []))) for intent in pb["intents"]]
    nao_cobertas = []
    for q in GOLDEN_QUESTIONS:
        qt = _tokens(q)
        # cobertura = ao menos 1 intent compartilha >=1 palavra-chave relevante
        if not any(qt & its for its in intent_token_sets):
            nao_cobertas.append(q)
    assert not nao_cobertas, f"perguntas-golden sem cobertura no playbook: {nao_cobertas}"
