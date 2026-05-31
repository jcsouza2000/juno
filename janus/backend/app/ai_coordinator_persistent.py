"""
JUNO AI Coordinator — Chat Persistente Wrapper
Este arquivo estende o ai_coordinator.py original adicionando:
- Salvamento automático de conversas no PostgreSQL
- Recuperação de histórico por session_id
- Resumo de contexto para limites de tokens

USO: Substituir ou importar no ai_coordinator.py original
"""

from typing import Any

from sqlalchemy.orm import Session

from app.audit_logger import AuditLogger
from app.chat_service import ChatService


class PersistentCoordinator:
    """
    Wrapper que adiciona persistência ao AI Coordinator existente.

    Como usar no endpoint /ai/coordinator:

    1. Receber session_id do frontend (opcional, null = nova sessão)
    2. Criar/continuar sessão via ChatService
    3. Recuperar histórico do banco
    4. Chamar Coordinator original com histórico + pergunta nova
    5. Salvar resposta no banco
    """

    def __init__(self, db: Session, base_coordinator=None):
        self.db = db
        self.chat = ChatService(db)
        self.audit = AuditLogger(db)
        self.base_coordinator = base_coordinator  # Instância do coordinator original

    def process_question(
        self,
        user_id: int,
        company_id: int,
        question: str,
        session_id: int | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """
        Processa pergunta com histórico persistente.

        Retorna:
        {
            "session_id": int,
            "response": str,
            "tools_used": list,
            "history_length": int
        }
        """
        # 1. Criar ou continuar sessão
        session = self.chat.create_or_continue_session(
            user_id=user_id, company_id=company_id, session_id=session_id
        )

        # 2. Recuperar histórico formatado para LLM
        history = self.chat.get_messages_as_history(session.id, user_id, max_messages=15)

        # 3. Adicionar pergunta atual ao histórico
        history.append({"role": "user", "content": question})

        # 4. TODO: Chamar coordinator original com history completo
        # response = self.base_coordinator.run(question, history)

        # Placeholder para demonstração (substituir pela chamada real)
        response = self._mock_coordinator_call(question, company_id, history)
        tools_used = ["get_company_overview"]  # Extrair do coordinator real

        # 5. Salvar turno no banco
        self.chat.save_conversation_turn(
            session_id=session.id,
            user_question=question,
            assistant_response=response,
            tools_used=tools_used,
        )

        # 6. Auditoria
        self.audit.log_ai_query(company_id, user_id, question, response, session.id)

        # 7. Atualizar título se for primeira mensagem
        if len(history) <= 2 and session.title.startswith("Consulta"):
            new_title = question[:50] + "..." if len(question) > 50 else question
            self.chat.update_session_title(session.id, user_id, new_title)

        return {
            "session_id": session.id,
            "response": response,
            "tools_used": tools_used,
            "history_length": len(history) + 1,
        }

    def _mock_coordinator_call(self, question: str, company_id: int, history: list) -> str:
        """
        MOCK — Substituir pela chamada real ao ai_coordinator.py
        """
        return f"[MOCK] Resposta para: '{question}' (Empresa {company_id}). Histórico: {len(history)} mensagens."

    def get_session_history(self, session_id: int, user_id: int) -> list[dict]:
        """Recupera histórico completo de uma sessão."""
        return self.chat.get_messages_as_history(session_id, user_id)

    def summarize_old_context(self, session_id: int, user_id: int) -> str:
        """
        Gera resumo do contexto quando histórico fica muito longo.
        Chamado automaticamente quando >20 mensagens.
        """
        return self.chat.get_context_summary(session_id, user_id)


# ============================================================
# FUNÇÃO DE CONVENIÊNCIA PARA ENDPOINTS
# ============================================================


def get_persistent_coordinator(db: Session):
    """Factory para injeção de dependência."""
    return PersistentCoordinator(db)
