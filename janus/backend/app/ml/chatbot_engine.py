"""
JUNO Chatbot Engine
Assistente virtual com NLP para consultas e comandos em linguagem natural
"""

import json
import logging
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

# Tentar importar transformers (fallback para regex se não disponível)
try:
    from transformers import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer, util

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from app.core.datetime_utils import utcnow_naive
from app.models import (
    ChatbotConversation,
    MLAnomaly,
    MLModel,
    MLPrediction,
    MLRecommendation,
    Product,
    SalesOrder,
)

logger = logging.getLogger(__name__)


class ChatbotEngine:
    """
    Engine de processamento de linguagem natural para o JUNO.

    Funcionalidades:
    - Classificação de intenções
    - Extração de entidades
    - Respostas contextuais
    - Consulta a dados operacionais
    """

    # Intenções suportadas
    INTENTS = {
        "sales_forecast": ["previsão de vendas", "forecast", "projeção", "vendas futuras"],
        "inventory_status": ["estoque", "inventário", "stock", "produtos em falta"],
        "anomaly_alert": ["anomalia", "alerta", "problema", "fora do normal"],
        "recommendation": ["recomendação", "sugestão", "o que fazer", "melhorar"],
        "product_info": ["produto", "item", "sku", "código"],
        "customer_info": ["cliente", "parceiro", "customer"],
        "order_status": ["pedido", "ordem", "venda", "nf"],
        "financial_summary": ["financeiro", "receita", "lucro", "faturamento"],
        "help": ["ajuda", "help", "como usar", "tutorial"],
        "greeting": ["olá", "oi", "hello", "bom dia", "boa tarde"],
    }

    def __init__(self, db: Session):
        self.db = db
        self.intent_classifier = None
        self.sentence_encoder = None
        self.conversation_context: dict[str, Any] = {}

        if TRANSFORMERS_AVAILABLE:
            try:
                self.intent_classifier = pipeline(
                    "zero-shot-classification",
                    model="facebook/bart-large-mnli",
                    device=-1,  # CPU
                )
                logger.info("[CHATBOT] Classificador de intenções carregado")
            except Exception as e:
                logger.warning(f"[CHATBOT] Não foi possível carregar transformers: {e}")

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_encoder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("[CHATBOT] Encoder de sentenças carregado")
            except Exception as e:
                logger.warning(f"[CHATBOT] Não foi possível carregar sentence-transformers: {e}")

    def process_message(self, company_id: int, user_id: int, session_id: str, message: str) -> dict:
        """
        Processa uma mensagem do usuário e retorna resposta.

        Args:
            company_id: ID da empresa
            user_id: ID do usuário
            session_id: ID da sessão de conversa
            message: Mensagem do usuário

        Returns:
            Dict com resposta, intenção, confiança e ações sugeridas
        """
        # Salvar mensagem do usuário
        user_msg = ChatbotConversation(
            company_id=company_id,
            user_id=user_id,
            session_id=session_id,
            message=message,
            is_user_message=True,
        )
        self.db.add(user_msg)
        self.db.commit()

        # Classificar intenção
        intent, confidence = self._classify_intent(message)

        # Extrair entidades
        entities = self._extract_entities(message)

        # Gerar resposta baseada na intenção
        response_data = self._generate_response(
            company_id=company_id, intent=intent, entities=entities, message=message
        )

        # Salvar resposta do bot
        bot_msg = ChatbotConversation(
            company_id=company_id,
            user_id=user_id,
            session_id=session_id,
            message=message,
            response=response_data["text"],
            intent=intent,
            confidence=confidence,
            context=json.dumps({"entities": entities, "actions": response_data.get("actions", [])}),
            is_user_message=False,
        )
        self.db.add(bot_msg)
        self.db.commit()

        return {
            "text": response_data["text"],
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "actions": response_data.get("actions", []),
            "session_id": session_id,
        }

    def _classify_intent(self, message: str) -> tuple[str, float]:
        """Classifica a intenção da mensagem."""
        message_lower = message.lower()

        # Método 1: Transformers (zero-shot)
        if self.intent_classifier:
            try:
                candidate_labels = list(self.INTENTS.keys())
                result = self.intent_classifier(message, candidate_labels, multi_label=False)
                return result["labels"][0], result["scores"][0]
            except Exception as e:
                logger.warning(f"[CHATBOT] Erro no classifier: {e}")

        # Método 2: Similaridade de embeddings
        if self.sentence_encoder:
            try:
                message_embedding = self.sentence_encoder.encode(message_lower)
                best_intent = "unknown"
                best_score = -1.0

                for intent, examples in self.INTENTS.items():
                    examples_embedding = self.sentence_encoder.encode(examples)
                    similarities = util.cos_sim(message_embedding, examples_embedding)
                    max_sim = float(similarities.max())

                    if max_sim > best_score:
                        best_score = max_sim
                        best_intent = intent

                if best_score > 0.5:
                    return best_intent, best_score
            except Exception as e:
                logger.warning(f"[CHATBOT] Erro no encoder: {e}")

        # Método 3: Fallback por palavras-chave
        for intent, keywords in self.INTENTS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return intent, 0.7

        return "unknown", 0.0

    def _extract_entities(self, message: str) -> dict:
        """Extrai entidades da mensagem (datas, números, produtos, etc)."""
        entities: dict[str, list[Any]] = {
            "dates": [],
            "numbers": [],
            "products": [],
            "time_periods": [],
        }

        # Extrair datas (padrões comuns)
        date_patterns = [
            r"(\d{2}/\d{2}/\d{4})",
            r"(\d{2}-\d{2}-\d{4})",
            r"(hoje|amanhã|ontem|esta semana|este mês|próximo mês)",
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, message.lower())
            entities["dates"].extend(matches)

        # Extrair números
        number_patterns = [r"(\d+)\s*(unidades|peças|itens)", r"(\d+\.?\d*)\s*(reais|r\$|%)"]
        for pattern in number_patterns:
            matches = re.findall(pattern, message.lower())
            entities["numbers"].extend([m[0] for m in matches])

        # Extrair períodos
        period_patterns = [
            r"(últimos?\s+\d+\s+(dias|semanas|meses|anos))",
            r"(próximos?\s+\d+\s+(dias|semanas|meses|anos))",
        ]
        for pattern in period_patterns:
            matches = re.findall(pattern, message.lower())
            entities["time_periods"].extend([m[0] for m in matches])

        return entities

    def _generate_response(
        self, company_id: int, intent: str, entities: dict, message: str
    ) -> dict:
        """Gera resposta baseada na intenção."""

        if intent == "greeting":
            return {
                "text": "Olá! Sou o assistente JUNO. Como posso ajudar você hoje? Você pode me perguntar sobre previsões de vendas, estoque, anomalias ou recomendações.",
                "actions": [],
            }

        elif intent == "sales_forecast":
            return self._handle_sales_forecast(company_id, entities)

        elif intent == "inventory_status":
            return self._handle_inventory_status(company_id, entities)

        elif intent == "anomaly_alert":
            return self._handle_anomaly_alert(company_id)

        elif intent == "recommendation":
            return self._handle_recommendation(company_id)

        elif intent == "product_info":
            return self._handle_product_info(company_id, entities, message)

        elif intent == "financial_summary":
            return self._handle_financial_summary(company_id, entities)

        elif intent == "help":
            return {
                "text": """Posso ajudar você com:

📈 **Previsões**: "Qual a previsão de vendas para o próximo mês?"
📦 **Estoque**: "Quais produtos estão em falta?"
⚠️ **Anomalias**: "Mostre alertas recentes"
💡 **Recomendações**: "O que você recomenda para aumentar vendas?"
📊 **Resumos**: "Faturamento deste mês"

Como posso ajudar?""",
                "actions": [
                    {"type": "button", "label": "Ver Previsões", "action": "navigate_forecast"},
                    {"type": "button", "label": "Ver Anomalias", "action": "navigate_anomalies"},
                ],
            }

        else:
            return {
                "text": "Não entendi completamente. Posso ajudar com previsões de vendas, status de estoque, alertas de anomalias ou recomendações. O que você gostaria de saber?",
                "actions": [
                    {"type": "suggestion", "label": "Previsão de vendas"},
                    {"type": "suggestion", "label": "Status do estoque"},
                    {"type": "suggestion", "label": "Ver anomalias"},
                ],
            }

    def _handle_sales_forecast(self, company_id: int, entities: dict) -> dict:
        """Gera resposta de previsão de vendas."""
        # Buscar predições mais recentes
        predictions = (
            self.db.query(MLPrediction)
            .join(MLModel)
            .filter(
                MLModel.company_id == company_id,
                MLModel.model_type == "sales_forecast",
                MLPrediction.prediction_date >= utcnow_naive(),
            )
            .order_by(MLPrediction.prediction_date)
            .limit(7)
            .all()
        )

        if predictions:
            total_forecast = sum(p.predicted_value for p in predictions)
            text = "📈 **Previsão de Vendas (Próximos 7 dias)**\n\n"
            for p in predictions:
                date_str = p.prediction_date.strftime("%d/%m")
                text += f"• {date_str}: R$ {p.predicted_value:,.2f}\n"
            text += f"\n**Total previsto: R$ {total_forecast:,.2f}**"

            if predictions[0].confidence_lower:
                text += f"\n\nIntervalo de confiança: R$ {predictions[0].confidence_lower:,.2f} - R$ {predictions[0].confidence_upper:,.2f}"
        else:
            text = "Não há previsões de vendas disponíveis no momento. Deseja que eu gere uma nova previsão?"

        return {
            "text": text,
            "actions": [
                {"type": "button", "label": "Gerar Nova Previsão", "action": "generate_forecast"},
                {"type": "button", "label": "Ver Gráfico", "action": "show_forecast_chart"},
            ],
        }

    def _handle_inventory_status(self, company_id: int, entities: dict) -> dict:
        """Gera resposta de status de estoque."""
        # Buscar produtos com estoque baixo
        low_stock = (
            self.db.query(Product)
            .filter(Product.company_id == company_id, Product.stock_quantity < Product.min_stock)
            .limit(10)
            .all()
        )

        if low_stock:
            text = "⚠️ **Produtos com Estoque Baixo**\n\n"
            for p in low_stock:
                text += f"• {p.name}: {p.stock_quantity} un (mín: {p.min_stock})\n"
            text += f"\nTotal de produtos em alerta: {len(low_stock)}"
        else:
            text = "✅ **Estoque OK**\n\nTodos os produtos estão com níveis adequados."

        return {
            "text": text,
            "actions": [
                {
                    "type": "button",
                    "label": "Ver Todos os Produtos",
                    "action": "navigate_inventory",
                },
                {
                    "type": "button",
                    "label": "Gerar Ordem de Compra",
                    "action": "generate_purchase_order",
                },
            ],
        }

    def _handle_anomaly_alert(self, company_id: int) -> dict:
        """Gera resposta de anomalias."""
        anomalies = (
            self.db.query(MLAnomaly)
            .filter(MLAnomaly.company_id == company_id, MLAnomaly.is_acknowledged == False)
            .order_by(MLAnomaly.severity.desc(), MLAnomaly.detected_at.desc())
            .limit(5)
            .all()
        )

        if anomalies:
            text = "🚨 **Anomalias Detectadas (Não Reconhecidas)**\n\n"
            severity_emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

            for a in anomalies:
                emoji = severity_emojis.get(a.severity, "⚪")
                text += f"{emoji} **{a.anomaly_type}**\n"
                text += f"   {a.description or 'Sem descrição'}\n"
                text += f"   Valor: {a.metric_value} (esperado: {a.expected_range_min}-{a.expected_range_max})\n\n"
        else:
            text = "✅ **Sem Anomalias**\n\nNenhuma anomalia não reconhecida no momento."

        return {
            "text": text,
            "actions": [
                {"type": "button", "label": "Ver Todas", "action": "navigate_anomalies"},
                {"type": "button", "label": "Configurar Alertas", "action": "configure_alerts"},
            ],
        }

    def _handle_recommendation(self, company_id: int) -> dict:
        """Gera resposta de recomendações."""
        recommendations = (
            self.db.query(MLRecommendation)
            .filter(MLRecommendation.company_id == company_id, MLRecommendation.is_applied == False)
            .order_by(MLRecommendation.confidence_score.desc())
            .limit(5)
            .all()
        )

        if recommendations:
            text = "💡 **Recomendações Pendentes**\n\n"
            for r in recommendations:
                text += f"• **{r.title}**\n"
                text += f"  {r.description or ''}\n"
                if r.expected_impact:
                    text += f"  Impacto esperado: +{r.expected_impact:.1f}%\n"
                text += "\n"
        else:
            text = "Não há recomendações pendentes no momento."

        return {
            "text": text,
            "actions": [
                {"type": "button", "label": "Aplicar Todas", "action": "apply_recommendations"},
                {
                    "type": "button",
                    "label": "Ver Histórico",
                    "action": "view_recommendation_history",
                },
            ],
        }

    def _handle_product_info(self, company_id: int, entities: dict, message: str) -> dict:
        """Busca informações de produto."""
        # Tentar extrair nome/código do produto
        # Simplificado - em produção usar NER
        products = self.db.query(Product).filter(Product.company_id == company_id).limit(5).all()

        if products:
            text = "📦 **Produtos Encontrados**\n\n"
            for p in products:
                text += f"• **{p.name}**\n"
                text += f"  Estoque: {p.stock_quantity} | Preço: R$ {p.sale_price:.2f}\n\n"
        else:
            text = "Nenhum produto encontrado. Tente ser mais específico ou verificar o código."

        return {
            "text": text,
            "actions": [
                {"type": "button", "label": "Ver Detalhes", "action": "navigate_product_detail"}
            ],
        }

    def _handle_financial_summary(self, company_id: int, entities: dict) -> dict:
        """Gera resumo financeiro."""
        # Calcular métricas do mês atual
        today = utcnow_naive()
        start_of_month = today.replace(day=1)

        # Buscar vendas do mês
        sales = (
            self.db.query(func.sum(SalesOrder.total))
            .filter(SalesOrder.company_id == company_id, SalesOrder.order_date >= start_of_month)
            .scalar()
            or 0
        )

        # Buscar vendas do mês anterior
        prev_month = (start_of_month - timedelta(days=1)).replace(day=1)
        prev_sales = (
            self.db.query(func.sum(SalesOrder.total))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.order_date >= prev_month,
                SalesOrder.order_date < start_of_month,
            )
            .scalar()
            or 0
        )

        variation = ((sales - prev_sales) / prev_sales * 100) if prev_sales > 0 else 0

        text = f"""💰 **Resumo Financeiro — {today.strftime('%B/%Y')}**

📈 **Faturamento**: R$ {sales:,.2f}
📊 **Mês Anterior**: R$ {prev_sales:,.2f}
{'📉' if variation < 0 else '📈'} **Variação**: {variation:+.1f}%

_Dados atualizados em tempo real_
"""

        return {
            "text": text,
            "actions": [
                {
                    "type": "button",
                    "label": "Ver Relatório Completo",
                    "action": "navigate_financial_report",
                },
                {"type": "button", "label": "Exportar PDF", "action": "export_pdf"},
            ],
        }

    def get_conversation_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """Retorna histórico de conversa."""
        messages = (
            self.db.query(ChatbotConversation)
            .filter(ChatbotConversation.session_id == session_id)
            .order_by(ChatbotConversation.created_at)
            .limit(limit)
            .all()
        )

        return [
            {
                "is_user": m.is_user_message,
                "message": m.message,
                "response": m.response,
                "intent": m.intent,
                "confidence": m.confidence,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
