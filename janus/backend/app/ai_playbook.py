"""
Loader do playbook da IA Operacional (Fase 4).

Le `ai_playbook.yaml` (perguntas executivas -> tools -> formato) e produz um
fragmento de prompt conciso para enriquecer o SYSTEM_PROMPT do Coordinator.
Isso "treina" a IA a escolher a ferramenta certa sem fine-tuning do modelo.

O conteudo e cacheado por processo. Se o arquivo faltar ou for invalido, o
fragmento volta vazio (o Coordinator segue funcionando com as tools nuas).
"""

from __future__ import annotations

import os
from functools import lru_cache

import yaml

from .core.logger import get_logger

logger = get_logger(__name__)

_PLAYBOOK_PATH = os.path.join(os.path.dirname(__file__), "ai_playbook.yaml")


@lru_cache(maxsize=1)
def load_playbook() -> dict:
    """Carrega e valida minimamente o playbook YAML. Cacheado."""
    try:
        with open(_PLAYBOOK_PATH, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.warning("playbook: %s nao encontrado — seguindo sem playbook", _PLAYBOOK_PATH)
        return {"version": 0, "intents": []}
    except yaml.YAMLError as exc:
        logger.error("playbook: YAML invalido (%s) — ignorando", exc)
        return {"version": 0, "intents": []}

    intents = data.get("intents")
    if not isinstance(intents, list):
        logger.error("playbook: 'intents' ausente ou invalido — ignorando")
        return {"version": 0, "intents": []}

    valid = []
    for intent in intents:
        if not isinstance(intent, dict):
            continue
        if not intent.get("tools") or not intent.get("perguntas"):
            logger.warning("playbook: intent ignorado (sem tools/perguntas): %r", intent.get("id"))
            continue
        valid.append(intent)

    return {"version": data.get("version", 1), "intents": valid}


@lru_cache(maxsize=1)
def build_prompt_fragment() -> str:
    """Monta o trecho do system prompt a partir do playbook (cacheado)."""
    playbook = load_playbook()
    intents = playbook.get("intents", [])
    if not intents:
        return ""

    lines = [
        "GUIA DE PERGUNTAS (playbook) — escolha a ferramenta correta e responda no formato indicado:",
    ]
    for intent in intents:
        perguntas = intent.get("perguntas", [])
        exemplos = "; ".join(str(p) for p in perguntas[:3])
        tools = ", ".join(str(t) for t in intent.get("tools", []))
        resposta = str(intent.get("resposta", "")).strip()
        lines.append(f'- "{exemplos}" → {tools}. {resposta}')

    return "\n".join(lines)
