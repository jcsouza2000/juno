"""
i18n leve para mensagens de API (Fase 2 — trilingue).

Negocia o idioma a partir do header HTTP Accept-Language e traduz mensagens
de erro/genericas para pt/en/es. PT e o padrao/fallback.

Uso:
    from app.core.i18n import translate
    translate("internal_error", request.headers.get("accept-language"))
"""

from __future__ import annotations

SUPPORTED = ("pt", "en", "es")
DEFAULT = "pt"

# Catalogo de mensagens. Adicione chaves conforme novos endpoints traduzirem
# suas respostas. Toda chave DEVE existir nos 3 idiomas.
_MESSAGES: dict[str, dict[str, str]] = {
    "internal_error": {
        "pt": "Erro interno do servidor",
        "en": "Internal server error",
        "es": "Error interno del servidor",
    },
    "rate_limited": {
        "pt": "Muitas requisicoes. Tente novamente em instantes.",
        "en": "Too many requests. Please try again shortly.",
        "es": "Demasiadas solicitudes. Intente nuevamente en instantes.",
    },
}


def negotiate_locale(accept_language: str | None) -> str:
    """Resolve o melhor idioma suportado a partir do header Accept-Language.

    Aceita formatos como "en-US,en;q=0.9,pt;q=0.8". Ordena por q-value e
    retorna o primeiro idioma suportado; cai em PT se nada casar.
    """
    if not accept_language:
        return DEFAULT

    ranked: list[tuple[float, str]] = []
    for part in accept_language.split(","):
        token = part.strip()
        if not token:
            continue
        lang, _, params = token.partition(";")
        primary = lang.strip().lower().split("-")[0]
        if primary not in SUPPORTED:
            continue
        q = 1.0
        if params.strip().startswith("q="):
            try:
                q = float(params.strip()[2:])
            except ValueError:
                q = 1.0
        ranked.append((q, primary))

    if not ranked:
        return DEFAULT
    # q-value desc; em empate preserva a ordem de chegada (estavel).
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def translate(key: str, accept_language: str | None = None) -> str:
    """Traduz uma chave do catalogo para o idioma negociado.

    Chave inexistente retorna a propria chave (fail-safe, nunca quebra).
    """
    locale = negotiate_locale(accept_language)
    entry = _MESSAGES.get(key)
    if entry is None:
        return key
    return entry.get(locale) or entry.get(DEFAULT) or key
