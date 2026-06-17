"""
AI Coordinator — JUNO Industrial Diagnostic
Agente local via qwen3:8b (Ollama) com tool calling sobre os dados reais.
"""

import json
import logging
import re
from typing import cast

import ollama
from sqlalchemy.orm import Session

from . import ai_playbook, analytics, dashboards, data_quality, insights
from . import demo as demo_module
from . import financials as fin_module
from .score_v2 import get_score_calculator

logger = logging.getLogger(__name__)

# Ontology integration (Sem7) — carregamento preguicoso para nao quebrar startup
# se a feature flag ONTOLOGY_ENABLED estiver false.
_ONTOLOGY_TOOLS_CACHE: list | None = None
_ONTOLOGY_PROMPT_CACHE: str | None = None


def _get_ontology_extensions():
    """Retorna (extra_tools, extra_prompt_fragment). Cacheado por processo."""
    global _ONTOLOGY_TOOLS_CACHE, _ONTOLOGY_PROMPT_CACHE
    if _ONTOLOGY_TOOLS_CACHE is not None:
        return _ONTOLOGY_TOOLS_CACHE, _ONTOLOGY_PROMPT_CACHE or ""

    try:
        from .ontology import ai_tools as _ai_tools
        from .ontology.registry import registry as _reg

        if not _reg.loaded or not _reg.list_object_types():
            _ONTOLOGY_TOOLS_CACHE = []
            _ONTOLOGY_PROMPT_CACHE = ""
            return [], ""
        _ONTOLOGY_TOOLS_CACHE = _ai_tools.build_tools_from_registry(_reg)
        _ONTOLOGY_PROMPT_CACHE = _ai_tools.build_system_prompt_fragment(_reg)
        logger.info(
            "coordinator: %d tools auto-geradas + system prompt enriquecido",
            len(_ONTOLOGY_TOOLS_CACHE),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("coordinator: ontology nao disponivel (%s) — usando so tools legadas", e)
        _ONTOLOGY_TOOLS_CACHE = []
        _ONTOLOGY_PROMPT_CACHE = ""

    return _ONTOLOGY_TOOLS_CACHE, _ONTOLOGY_PROMPT_CACHE or ""


MODEL = "qwen3:8b"

SYSTEM_PROMPT = """Você é o Coordinator do JUNO, sistema de diagnóstico operacional.
Você tem acesso a ferramentas que consultam dados reais da empresa do usuário.

Empresa do usuário:
- Você sempre opera sobre os dados da empresa do PRÓPRIO usuário autenticado.
  O sistema resolve automaticamente a empresa correta no servidor — você NÃO
  escolhe nem informa IDs de empresa. A organização é agnóstica de setor (pode
  ser indústria, serviço, comércio, agroindústria ou bens de capital); não
  assuma o setor — infira a natureza pelo que aparece nos dados.

Dados disponíveis: KPIs operacionais (ERP), demonstrações financeiras (DRE, Balanço, DFC) quando carregadas.

Regras:
1. Use SEMPRE as ferramentas para buscar dados reais antes de responder. Nunca invente números.
2. Foque em impacto financeiro — cite valores em R$ sempre que possível.
3. Destaque problemas críticos com clareza e urgência.
4. Seja objetivo: o usuário é executivo, sem tempo para rodeios.
5. Responda sempre em português do Brasil.
6. Nunca tente acessar dados de outra empresa/base; você só enxerga a empresa do usuário.
7. Para valuation, projeção DRE/DFC ou Enterprise Value, use SEMPRE run_valuation_scenario
   (nunca calcule projeções manualmente). Apresente o resultado com base nos números retornados pela ferramenta."""

# Fase 2 — idioma da RESPOSTA ao usuario. Os dados/tools permanecem em PT; a
# diretiva abaixo (quando nao vazia) sobrescreve a regra 5 e manda o modelo
# responder no idioma escolhido na UI. PT e o padrao (sem diretiva extra).
LANG_INSTRUCTION = {
    "pt": "",
    "en": (
        "IMPORTANT — OUTPUT LANGUAGE: Write your entire reply to the user in English (US). "
        "The tools, their names and their JSON results stay in Portuguese — translate the "
        "meaning into English. Keep monetary values in R$ (Brazilian Real)."
    ),
    "es": (
        "IMPORTANTE — IDIOMA DE SALIDA: Escribe toda tu respuesta al usuario en español. "
        "Las herramientas, sus nombres y sus resultados JSON permanecen en portugués — traduce "
        "el significado al español. Mantén los valores monetarios en R$ (real brasileño)."
    ),
}


def build_system_prompt(lang: str | None = None) -> str:
    """SYSTEM_PROMPT base + diretiva de idioma de saida (Fase 2 — trilingue).

    lang aceita 'pt' | 'en' | 'es' (case-insensitive). Valor invalido ou None
    cai em PT, sem diretiva extra.
    """
    instruction = LANG_INSTRUCTION.get((lang or "pt").lower(), "")
    if instruction:
        return SYSTEM_PROMPT + "\n\n" + instruction
    return SYSTEM_PROMPT


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_company_overview",
            "description": "KPIs executivos: receita líquida, Score JUNO, ordens atrasadas e produtos com margem negativa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_margin_analysis",
            "description": "Margem real por produto (receita vs custo padrão). Identifica produtos vendidos abaixo do custo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_production_delays",
            "description": "Ordens de produção com atraso (data real posterior à data planejada).",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_insights",
            "description": "Insights automáticos gerados pelo JUNO: riscos de margem, atrasos críticos e desvios de custo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_data_quality",
            "description": "Data Trust Score (0-100) e problemas detectados nos dados. Use antes de apresentações ao conselho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_full_diagnostic",
            "description": "Diagnóstico completo em uma chamada: KPIs, margens, atrasos, insights e data trust score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_statements",
            "description": "Demonstrações financeiras: DRE (receita, lucro bruto, EBITDA, lucro líquido e margens), Balanço (liquidez corrente, endividamento) e DFC (fluxo operacional/investimento/financiamento). Use quando o usuário perguntar sobre margens financeiras, resultado do exercício, balanço patrimonial, liquidez ou fluxo de caixa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_concentration",
            "description": (
                "Concentração de receita por cliente (curva ABC) e risco de dependência "
                "comercial. Use para perguntas sobre maiores clientes, carteira concentrada, "
                "quanto o maior cliente representa ou risco de perder um cliente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_abc",
            "description": (
                "Curva ABC de produtos por receita líquida (classes A/B/C). Use para "
                "perguntas sobre mix de produtos, quais produtos concentram a receita, "
                "priorização de portfólio ou itens classe A."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    }
                },
                "required": ["company_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_valuation_scenario",
            "description": (
                "Motor auditável de valuation: projeta DRE e DFC por N anos a partir dos dados reais, "
                "calcula FCF descontado e Enterprise Value. Use para projeções, DCF, WACC, "
                "crescimento de receita/custos ou diagnóstico com valuation futuro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "1=Minha Empresa (padrão), 2=base secundária (compat)",
                    },
                    "anos": {
                        "type": "integer",
                        "description": "Horizonte em anos (inclui ano base). Padrão: 5.",
                    },
                    "crescimento_receita_pct": {
                        "type": "number",
                        "description": "Crescimento anual da receita em % (ex.: 10 = 10% a.a.). Padrão: 10.",
                    },
                    "crescimento_custos_fixos_pct": {
                        "type": "number",
                        "description": "Crescimento anual dos custos operacionais em % (ex.: 5 = 5% a.a.). Padrão: 5.",
                    },
                    "taxa_desconto_pct": {
                        "type": "number",
                        "description": "Taxa de desconto (WACC) em % a.a. (ex.: 10 = 10% a.a.). Padrão: 10.",
                    },
                },
                "required": ["company_id"],
            },
        },
    },
]

TOOL_LABELS: dict[str, str] = {
    "get_company_overview": "Consultando KPIs executivos...",
    "get_margin_analysis": "Analisando margens por produto...",
    "get_production_delays": "Verificando atrasos de produção...",
    "get_insights": "Gerando insights operacionais...",
    "validate_data_quality": "Validando qualidade dos dados...",
    "get_full_diagnostic": "Executando diagnóstico completo...",
    "get_financial_statements": "Consultando demonstrações financeiras...",
    "get_customer_concentration": "Analisando concentração de clientes...",
    "get_product_abc": "Calculando curva ABC de produtos...",
    "run_valuation_scenario": "Calculando valuation e projeções...",
}


def _resolve_company_id(user, args: dict) -> int:
    """
    Resolve o company_id AUTORITATIVO para as tools legadas.

    SEGURANCA (C1): o tenant NUNCA vem do que o modelo escolheu em `args`.
    Ele e derivado do usuario autenticado. O `company_id` sugerido pelo modelo
    so' e' aceito se o usuario realmente tiver acesso aquele tenant; caso
    contrario, cai para o tenant primario do usuario.

    Fallback (somente quando nao ha usuario, ex.: dev/None): usa args ou 1.
    """
    if user is None:
        return int(args.get("company_id", 1))

    # company_ids permitidos para este usuario
    allowed: list[int] = []
    try:
        from .ontology.permissions import UserContext

        if isinstance(user, UserContext):
            allowed = list(user.company_ids or [])
        else:
            from .auth import get_user_company_ids

            allowed = get_user_company_ids(user)
    except Exception:  # noqa: BLE001
        allowed = []

    requested = args.get("company_id")
    if requested is not None:
        try:
            requested = int(requested)
        except (TypeError, ValueError):
            requested = None

    if not allowed:
        # Nao foi possivel determinar as empresas do usuario. Isso ocorre no
        # streaming SSE (sessao do DB desanexada dentro do gerador). O endpoint
        # do coordinator JA validou o company_id contra as empresas reais do
        # usuario antes do stream, entao confiamos no valor recebido em args.
        if requested is not None:
            return requested
        raise PermissionError("Usuario sem empresa vinculada")

    if requested is not None and requested in allowed:
        return requested
    # Modelo pediu tenant fora do escopo (ou nao pediu): usa o primario.
    return allowed[0]


def _run_tool(name: str, args: dict, db: Session, user=None) -> str:
    """
    Despacha uma tool. Estrategia:
      1. Se nome bate com padrao ontology (search_*, get_*_by_id, list_*, propose_*),
         usa ai_tools.dispatch_tool_call (passa user UserContext).
      2. Senao, cai no path legado (7 tools hardcoded).
    """
    # 1) Ontology tools
    if name.startswith(("search_", "get_", "list_", "propose_")) and not name.endswith(
        "_company_overview"
    ):
        # Excecao: get_company_overview e' tool LEGADA — nao tentar dispatch
        try:
            from .ontology import ai_tools as _ai_tools
            from .ontology.permissions import UserContext
            from .ontology.registry import registry as _reg

            if isinstance(user, UserContext):
                user_ctx = user
            elif user is not None:
                user_ctx = UserContext.from_user_with_grants(user, db)
            else:
                user_ctx = UserContext(role="admin", markings_granted=["*"])
            result = _ai_tools.dispatch_tool_call(
                name,
                args,
                user=user_ctx,
                db=db,
                registry=_reg,
            )
            return json.dumps(result, default=str, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            # Cai para o path legado se a tool nao for reconhecida
            logger.debug("dispatch ontology falhou para %s (%s), tentando legado", name, e)

    # 2) Tools legadas
    # SEGURANCA (C1): tenant vem do usuario autenticado, nunca do modelo.
    try:
        cid = _resolve_company_id(user, args)
    except PermissionError as exc:
        return json.dumps({"error": str(exc)})
    try:
        if name == "get_company_overview":
            ceo = dashboards.get_ceo_kpis(db, cid)
            score = get_score_calculator(db).calculate_full_score(cid, persist=False).overall_score
            margins = dashboards.get_cfo_margin_by_product(db, cid)
            delays = dashboards.get_coo_delayed_orders(db, cid)
            neg = [m for m in margins if m["margem"] < 0]
            return json.dumps(
                {
                    "receita_liquida": ceo["receita_liquida"],
                    "score_juno": score,
                    "produtos_margem_negativa": len(neg),
                    "ordens_atrasadas": len(delays),
                }
            )

        if name == "get_margin_analysis":
            return json.dumps(dashboards.get_cfo_margin_by_product(db, cid))

        if name == "get_production_delays":
            return json.dumps(dashboards.get_coo_delayed_orders(db, cid), default=str)

        if name == "get_insights":
            op = insights.generate_insights(cid, db)
            dq = data_quality.generate_data_quality_insights(cid, db)
            return json.dumps(op + dq)

        if name == "validate_data_quality":
            return json.dumps(data_quality.get_full_validation_report(cid, db), default=str)

        if name == "get_full_diagnostic":
            return json.dumps(demo_module.get_demo_summary(cid, db), default=str)

        if name == "get_financial_statements":
            return json.dumps(fin_module.get_financial_summary(cid, db), default=str)

        if name == "get_customer_concentration":
            return json.dumps(
                analytics.get_customer_concentration(db, cid), default=str, ensure_ascii=False
            )

        if name == "get_product_abc":
            return json.dumps(analytics.get_product_abc(db, cid), default=str, ensure_ascii=False)

        if name == "run_valuation_scenario":
            from .valuation_scenario import run_valuation_scenario

            anos = int(args.get("anos", 5))
            rev = float(args.get("crescimento_receita_pct", 10)) / 100.0
            custos = float(args.get("crescimento_custos_fixos_pct", 5)) / 100.0
            wacc = float(args.get("taxa_desconto_pct", 10)) / 100.0
            result = run_valuation_scenario(
                cid,
                db,
                anos=anos,
                crescimento_receita=rev,
                crescimento_custos_fixos=custos,
                taxa_desconto=wacc,
            )
            return json.dumps(result, default=str, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"error": str(exc)})

    return json.dumps({"error": f"tool desconhecida: {name}"})


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def coordinate(
    question: str,
    db: Session,
    history: list | None = None,
    user=None,
    company_id: int | None = None,
    lang: str | None = None,
):
    """
    Generator — produz strings JSON (dados SSE):
      {"type": "tool_call",        "tool": str, "label": str}
      {"type": "proposed_action",  "action": str, "target_id": int, "preview": dict, ...}
      {"type": "text",             "content": str}
      {"type": "error",            "message": str}

    Args:
        question: pergunta em PT-BR
        db: SQLAlchemy session
        history: historico [{role, content}, ...]
        user: opcional. UserContext ou app.models.User; usado para tools da ontology
              (TenantScoped, markings). Se None, assume admin global (use so' em dev).
    """
    extra_tools, extra_prompt = _get_ontology_extensions()
    # Idioma da resposta (Fase 2): PT por padrao; en/es viram diretiva no prompt.
    full_system_prompt = build_system_prompt(lang)
    # Playbook (Fase 4): orienta a escolha de ferramentas por tipo de pergunta.
    playbook_fragment = ai_playbook.build_prompt_fragment()
    if playbook_fragment:
        full_system_prompt = full_system_prompt + "\n\n" + playbook_fragment
    if extra_prompt:
        full_system_prompt = full_system_prompt + "\n\n" + extra_prompt
    full_tools = list(TOOLS) + list(extra_tools)

    messages: list[dict] = [{"role": "system", "content": full_system_prompt}]
    if history:
        messages.extend(history)
    # /no_think disables qwen3's extended thinking block — cuts latency from ~60s to ~10s per call
    messages.append({"role": "user", "content": f"{question} /no_think"})

    for _ in range(6):
        # ── Tool-call probe: small budget, fast decision ──────────────────
        try:
            probe = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=full_tools,
                options={"temperature": 0.1, "num_predict": 150},
            )
        except Exception as exc:
            msg = str(exc)
            if "Failed to connect to Ollama" in msg or "Connection refused" in msg.lower():
                msg = (
                    "Ollama nao esta acessivel. Inicie o Ollama Desktop ou execute "
                    "'ollama serve' no terminal. Modelo necessario: qwen3:8b."
                )
            yield json.dumps({"type": "error", "message": msg})
            return

        probe_msg = cast(dict, probe.get("message", {}))

        if probe_msg.get("tool_calls"):
            # Execute tools, loop back for next round
            messages.append(probe_msg)
            for tc in probe_msg.get("tool_calls", []):
                name = tc["function"]["name"]
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                # Label: legado tem fixo, auto-geradas usam nome bonito
                label = TOOL_LABELS.get(name)
                if label is None:
                    if name.startswith("propose_"):
                        label = f"Propondo {name[len('propose_'):]}..."
                    elif name.startswith("search_"):
                        label = f"Buscando {name[len('search_'):]}..."
                    elif name.startswith("get_") and name.endswith("_by_id"):
                        label = f"Consultando {name[len('get_'):-len('_by_id')]}..."
                    elif name.startswith("list_"):
                        label = f"Listando {name[len('list_'):]}..."
                    else:
                        label = f"Executando {name}..."

                yield json.dumps({"type": "tool_call", "tool": name, "label": label})

                # Tenant da UI e' autoritativo: sobrescreve o que o modelo chutou.
                # Ainda validado contra permissoes em _resolve_company_id.
                if company_id is not None:
                    args["company_id"] = company_id
                result = _run_tool(name, args, db, user=user)
                messages.append({"role": "tool", "content": result})

                if name == "run_valuation_scenario":
                    try:
                        parsed = json.loads(result)
                        if isinstance(parsed, dict) and parsed.get("kind") == "valuation_scenario":
                            yield json.dumps({"type": "valuation_result", "data": parsed})
                    except (json.JSONDecodeError, AttributeError):
                        pass

                # Se a tool foi propose_*, emite tambem evento dedicado pro frontend
                # mostrar card de confirmacao em vez de so' texto.
                if name.startswith("propose_"):
                    try:
                        parsed = json.loads(result)
                        if isinstance(parsed, dict) and parsed.get("kind") == "proposed_action":
                            yield json.dumps(
                                {
                                    "type": "proposed_action",
                                    "action": parsed.get("action"),
                                    "target_id": parsed.get("target_id"),
                                    "inputs": parsed.get("inputs", {}),
                                    "preview": parsed.get("preview"),
                                    "next_step": parsed.get("next_step"),
                                }
                            )
                    except (json.JSONDecodeError, AttributeError):
                        pass
            continue

        # ── No more tools — generate final answer with full budget ────────
        # Reforco anti-"resposta vazia": qwen3 as vezes gasta todo o budget em
        # <think>...</think> e o _strip_thinking zera o texto. O nudge /no_think
        # pede resposta direta; o fallback abaixo garante que algo util e' emitido.
        messages.append(
            {
                "role": "user",
                "content": (
                    "/no_think Responda agora, de forma objetiva e em portugues, "
                    "usando os dados das ferramentas. Nao mostre raciocinio."
                ),
            }
        )
        try:
            final = ollama.chat(
                model=MODEL,
                messages=messages,
                options={"temperature": 0.1, "num_predict": 900},
            )
        except Exception as exc:
            msg = str(exc)
            if "Failed to connect to Ollama" in msg or "Connection refused" in msg.lower():
                msg = (
                    "Ollama nao esta acessivel. Inicie o Ollama Desktop ou execute "
                    "'ollama serve' no terminal. Modelo necessario: qwen3:8b."
                )
            yield json.dumps({"type": "error", "message": msg})
            return

        raw = final.get("message", {}).get("content", "")
        content = _strip_thinking(raw)
        if not content.strip():
            # Tudo veio como raciocinio (<think>...): usa o texto apos o ultimo
            # </think>; se ainda vazio, cai para o bruto sem as tags de think.
            tail = raw.split("</think>")[-1].strip()
            content = tail or re.sub(r"</?think>", "", raw).strip()
        buf = ""
        for char in content:
            buf += char
            if len(buf) >= 40 or char in ".!?\n":
                yield json.dumps({"type": "text", "content": buf})
                buf = ""
        if buf:
            yield json.dumps({"type": "text", "content": buf})
        return

    yield json.dumps({"type": "error", "message": "Limite de iterações atingido."})
