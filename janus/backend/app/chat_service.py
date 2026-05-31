"""
JUNO Chat Service — CRUD de sessões e mensagens
Integra com AI Coordinator para histórico persistente
"""

from datetime import datetime

from fastapi import Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.audit_logger import AuditLogger
from app.core.datetime_utils import utcnow_naive
from app.database import get_db
from app.models import ChatMessage, ChatSession


class ChatService:
    """Serviço de gerenciamento de conversas persistentes."""

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditLogger(db)

    # ============================================================
    # SESSÕES
    # ============================================================

    def create_session(
        self, user_id: int, company_id: int, title: str | None = None
    ) -> ChatSession:
        """Cria nova sessão de chat."""
        session = ChatSession(
            user_id=user_id,
            company_id=company_id,
            title=title or "Nova conversa",
            created_at=utcnow_naive(),
            updated_at=utcnow_naive(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int, user_id: int) -> ChatSession | None:
        """Obtém sessão se pertencer ao usuário."""
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

    def list_sessions(
        self, user_id: int, company_id: int | None = None, limit: int = 50
    ) -> list[ChatSession]:
        """Lista sessões do usuário, opcionalmente filtradas por empresa."""
        query = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)
        if company_id:
            query = query.filter(ChatSession.company_id == company_id)
        return query.order_by(desc(ChatSession.updated_at)).limit(limit).all()

    def update_session_title(self, session_id: int, user_id: int, title: str) -> ChatSession | None:
        """Atualiza título da sessão."""
        session = self.get_session(session_id, user_id)
        if session:
            session.title = title
            session.updated_at = utcnow_naive()
            self.db.commit()
            self.db.refresh(session)
        return session

    def delete_session(self, session_id: int, user_id: int) -> bool:
        """Remove sessão e todas as mensagens (cascade)."""
        session = self.get_session(session_id, user_id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False

    # ============================================================
    # MENSAGENS
    # ============================================================

    def add_message(
        self, session_id: int, role: str, content: str, tool_calls: str | None = None
    ) -> ChatMessage:
        """Adiciona mensagem à sessão."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            created_at=utcnow_naive(),
        )
        self.db.add(message)

        # Atualizar timestamp da sessão
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = utcnow_naive()

        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(self, session_id: int, user_id: int, limit: int = 100) -> list[ChatMessage]:
        """Obtém mensagens de uma sessão (verificando propriedade)."""
        # Verificar se sessão pertence ao usuário
        session = self.get_session(session_id, user_id)
        if not session:
            return []

        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .limit(limit)
            .all()
        )

    def get_messages_as_history(
        self, session_id: int, user_id: int, max_messages: int = 20
    ) -> list[dict]:
        """
        Retorna mensagens no formato de histórico para o LLM.
        Limita a N mensagens recentes para não estourar contexto.
        """
        messages = self.get_messages(session_id, user_id, limit=max_messages)

        history = []
        for msg in messages:
            entry = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            history.append(entry)

        return history

    # ============================================================
    # INTEGRAÇÃO COM AI COORDINATOR
    # ============================================================

    def create_or_continue_session(
        self, user_id: int, company_id: int, session_id: int | None = None, title: str | None = None
    ) -> ChatSession:
        """
        Cria nova sessão ou continua existente.
        Usado pelo endpoint /ai/coordinator.
        """
        if session_id:
            session = self.get_session(session_id, user_id)
            if session and session.company_id == company_id:
                return session

        # Criar nova sessão com título inteligente
        auto_title = (
            title or f"Consulta Empresa {company_id} — {datetime.now().strftime('%d/%m %H:%M')}"
        )
        return self.create_session(user_id, company_id, auto_title)

    def save_conversation_turn(
        self,
        session_id: int,
        user_question: str,
        assistant_response: str,
        tools_used: list[str] | None = None,
    ):
        """Salva um turno completo de conversa (pergunta + resposta)."""
        # Mensagem do usuário
        self.add_message(session_id, "user", user_question)

        # Mensagem do assistente
        tool_calls_json = None
        if tools_used:
            import json

            tool_calls_json = json.dumps({"tools_executed": tools_used})

        self.add_message(session_id, "assistant", assistant_response, tool_calls_json)

    def get_context_summary(self, session_id: int, user_id: int) -> str:
        """
        Gera resumo do contexto para quando histórico ficar muito longo.
        Usado para manter contexto dentro do limite de tokens do LLM.
        """
        messages = self.get_messages(session_id, user_id, limit=50)
        if len(messages) < 10:
            return ""  # Não precisa resumir ainda

        # Restante resumido
        older = messages[:-5]

        summary_parts = []
        for msg in older:
            if msg.role == "user":
                summary_parts.append(f"Usuário perguntou sobre: {msg.content[:100]}...")
            elif msg.role == "assistant":
                summary_parts.append(f"IA respondeu: {msg.content[:100]}...")

        summary = "Resumo da conversa anterior:\n" + "\n".join(summary_parts)
        return summary


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    """Factory para injeção de dependência."""
    return ChatService(db)
