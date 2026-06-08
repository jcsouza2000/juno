"""Testes do i18n de mensagens de API (negociacao Accept-Language)."""

from __future__ import annotations

from app.core.i18n import negotiate_locale, translate


def test_negotiate_default_pt_quando_ausente():
    assert negotiate_locale(None) == "pt"
    assert negotiate_locale("") == "pt"


def test_negotiate_idioma_simples():
    assert negotiate_locale("en") == "en"
    assert negotiate_locale("es") == "es"
    assert negotiate_locale("pt-BR") == "pt"


def test_negotiate_respeita_qvalue():
    # en com q maior que pt -> en
    assert negotiate_locale("pt;q=0.5, en;q=0.9") == "en"
    # primeiro suportado quando sem q explicito
    assert negotiate_locale("fr, es, en") == "es"


def test_negotiate_ignora_nao_suportado():
    assert negotiate_locale("fr-FR, de;q=0.8") == "pt"


def test_translate_mensagens():
    assert translate("internal_error", "en") == "Internal server error"
    assert translate("internal_error", "es") == "Error interno del servidor"
    assert translate("internal_error", None) == "Erro interno do servidor"
    assert translate("rate_limited", "en").startswith("Too many")


def test_translate_chave_desconhecida_retorna_a_chave():
    assert translate("nao_existe", "en") == "nao_existe"
