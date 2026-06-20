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
    # ── Impacto/severidade (compartilhado) ──────────────────────────────────
    "impact.high": {"pt": "Alto", "en": "High", "es": "Alto"},
    "impact.medium": {"pt": "Médio", "en": "Medium", "es": "Medio"},
    "impact.low": {"pt": "Baixo", "en": "Low", "es": "Bajo"},
    # ── Insights (generate_insights) ────────────────────────────────────────
    "insight.margin.message": {
        "pt": "Produto {name} está com margem negativa (R$ {margin})",
        "en": "Product {name} has a negative margin (R$ {margin})",
        "es": "El producto {name} tiene margen negativo (R$ {margin})",
    },
    "insight.margin.action": {
        "pt": "Revisar precificação ou reduzir custos de produção imediatamente.",
        "en": "Review pricing or reduce production costs immediately.",
        "es": "Revisar precios o reducir costos de producción de inmediato.",
    },
    "insight.delay.message": {
        "pt": "{count} ordens de produção estão com entrega atrasada",
        "en": "{count} production orders are delayed",
        "es": "{count} órdenes de producción están con entrega atrasada",
    },
    "insight.delay.action": {
        "pt": "Revisar capacidade produtiva e logística de entrega.",
        "en": "Review production capacity and delivery logistics.",
        "es": "Revisar capacidad productiva y logística de entrega.",
    },
    "insight.cost.message": {
        "pt": "{count} ordens excederam o custo planejado em mais de 10%",
        "en": "{count} orders exceeded the planned cost by more than 10%",
        "es": "{count} órdenes excedieron el costo planificado en más del 10%",
    },
    "insight.cost.action": {
        "pt": "Auditar desperdícios na linha de produção e variação de preço de insumos.",
        "en": "Audit waste on the production line and input price variation.",
        "es": "Auditar desperdicios en la línea de producción y variación de precios de insumos.",
    },
    # ── Recomendacoes do Score (score_v2._generate_recommendations) ──────────
    # O emoji prefixo fica fora da traducao (o PDF usa para escolher o estilo).
    "score.critical": {
        "pt": "{name}: Situação crítica ({score}/100). Ação imediata necessária.",
        "en": "{name}: Critical situation ({score}/100). Immediate action required.",
        "es": "{name}: Situación crítica ({score}/100). Acción inmediata necesaria.",
    },
    "score.attention": {
        "pt": "{name}: Atenção necessária ({score}/100). Revisar processos.",
        "en": "{name}: Attention required ({score}/100). Review processes.",
        "es": "{name}: Atención necesaria ({score}/100). Revisar procesos.",
    },
    "score.regular": {
        "pt": "{name}: Regular ({score}/100). Oportunidade de melhoria.",
        "en": "{name}: Fair ({score}/100). Room for improvement.",
        "es": "{name}: Regular ({score}/100). Oportunidad de mejora.",
    },
    "score.healthy": {
        "pt": "Todos os indicadores estão saudáveis. Manter monitoramento.",
        "en": "All indicators are healthy. Keep monitoring.",
        "es": "Todos los indicadores están saludables. Mantener el monitoreo.",
    },
}

# Traducao dos nomes de componente do Score (vem do score_v2 em PT). Lookup
# pela chave PT, que e a forma canonica usada no resto do codigo.
_COMPONENTS: dict[str, dict[str, str]] = {
    "Margem": {"pt": "Margem", "en": "Margin", "es": "Margen"},
    "Liquidez": {"pt": "Liquidez", "en": "Liquidity", "es": "Liquidez"},
    "Endividamento": {"pt": "Endividamento", "en": "Leverage", "es": "Endeudamiento"},
    "Produção": {"pt": "Produção", "en": "Production", "es": "Producción"},
    "Qualidade de Dados": {
        "pt": "Qualidade de Dados",
        "en": "Data Quality",
        "es": "Calidad de Datos",
    },
    "Sazonalidade": {"pt": "Sazonalidade", "en": "Seasonality", "es": "Estacionalidad"},
    "Concentração de Clientes": {
        "pt": "Concentração de Clientes",
        "en": "Customer Concentration",
        "es": "Concentración de Clientes",
    },
}


def tr_component(name: str, locale: str | None = None) -> str:
    """Traduz um nome de componente do Score (entrada em PT) para o locale."""
    loc = normalize_locale(locale)
    entry = _COMPONENTS.get(name)
    if entry is None:
        return name
    return entry.get(loc) or entry.get(DEFAULT) or name


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


def normalize_locale(locale: str | None) -> str:
    """Reduz um codigo de idioma (ex: 'en-US', 'PT') a um suportado; default PT."""
    if not locale:
        return DEFAULT
    primary = locale.strip().lower().split("-")[0]
    return primary if primary in SUPPORTED else DEFAULT


def tr(key: str, locale: str | None = None, **variables: object) -> str:
    """Traduz uma chave com locale DIRETO (nao header) e interpolacao {var}.

    Usada por geradores de conteudo (insights, score, audit) que recebem o
    idioma da UI via query param. Chave/locale invalidos caem em PT; chave
    inexistente retorna a propria chave (fail-safe).
    """
    loc = normalize_locale(locale)
    entry = _MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(loc) or entry.get(DEFAULT) or key
    if variables:
        try:
            return text.format(**variables)
        except (KeyError, IndexError, ValueError):
            return text
    return text
