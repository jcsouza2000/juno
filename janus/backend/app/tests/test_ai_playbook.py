"""
Eval/consistencia do playbook da IA (Fase 4).

Garante que o playbook carrega e que TODA ferramenta referenciada existe de
fato no Coordinator — evita que o prompt oriente o modelo a chamar uma tool
inexistente.
"""

from __future__ import annotations

from app.ai_coordinator import TOOLS
from app.ai_playbook import build_prompt_fragment, load_playbook

_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}  # type: ignore[index]


def test_playbook_carrega_com_intents():
    pb = load_playbook()
    assert pb["intents"], "playbook deveria ter intents"
    # Cada intent precisa de id, perguntas e tools.
    for intent in pb["intents"]:
        assert intent.get("perguntas")
        assert intent.get("tools")


def test_todas_as_tools_do_playbook_existem():
    pb = load_playbook()
    referenced = {tool for intent in pb["intents"] for tool in intent["tools"]}
    desconhecidas = referenced - _TOOL_NAMES
    assert not desconhecidas, f"playbook referencia tools inexistentes: {desconhecidas}"


def test_novas_tools_estao_cobertas():
    pb = load_playbook()
    referenced = {tool for intent in pb["intents"] for tool in intent["tools"]}
    assert "get_customer_concentration" in referenced
    assert "get_product_abc" in referenced


def test_fragmento_de_prompt_nao_vazio_e_cita_tools():
    frag = build_prompt_fragment()
    assert "playbook" in frag.lower()
    assert "get_customer_concentration" in frag
    assert "get_product_abc" in frag
