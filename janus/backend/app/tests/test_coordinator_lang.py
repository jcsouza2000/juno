"""
Testes da diretiva de idioma do Coordinator (Fase 2 — IA trilingue).

Garante que build_system_prompt injeta a instrucao de idioma correta sem
quebrar o prompt base em PT.
"""

from __future__ import annotations

from app.ai_coordinator import SYSTEM_PROMPT, build_system_prompt


def test_pt_e_padrao_sem_diretiva_extra():
    assert build_system_prompt("pt") == SYSTEM_PROMPT
    assert build_system_prompt(None) == SYSTEM_PROMPT
    # idioma desconhecido cai em PT (sem diretiva)
    assert build_system_prompt("fr") == SYSTEM_PROMPT


def test_en_injeta_diretiva_de_ingles():
    prompt = build_system_prompt("en")
    assert prompt.startswith(SYSTEM_PROMPT)
    assert "OUTPUT LANGUAGE" in prompt
    assert "English" in prompt


def test_es_injeta_diretiva_de_espanhol():
    prompt = build_system_prompt("es")
    assert prompt.startswith(SYSTEM_PROMPT)
    assert "IDIOMA DE SALIDA" in prompt
    assert "español" in prompt


def test_case_insensitive():
    assert build_system_prompt("EN") == build_system_prompt("en")
    assert build_system_prompt("Es") == build_system_prompt("es")
