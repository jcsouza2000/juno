"""
JUNO Chat Router — Endpoints para gerenciamento de conversas
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import check_company_access, get_current_active_user
from app.chat_service import ChatService, get_chat_service
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============================================================
# SCHEMAS
# ============================================================


class SessionCreate(BaseModel):
    company_id: int
    title: str | None = None


class SessionUpdate(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: int
    company_id: int
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str | None = None

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    session: SessionResponse
    messages: list[MessageResponse]


# ============================================================
# SESSÕES
# ============================================================


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Cria nova sessão de chat para uma empresa.
    """
    if not check_company_access(current_user, data.company_id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta empresa")
    session = chat_service.create_session(
        user_id=current_user.id, company_id=data.company_id, title=data.title
    )
    return {
        "id": session.id,
        "company_id": session.company_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "message_count": 0,
    }


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Lista todas as sessões do usuário logado.
    Opcionalmente filtra por empresa.
    """
    if company_id is not None and not check_company_access(current_user, company_id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta empresa")
    sessions = chat_service.list_sessions(user_id=current_user.id, company_id=company_id)

    result = []
    for s in sessions:
        msg_count = len(s.messages) if hasattr(s, "messages") else 0
        result.append(
            {
                "id": s.id,
                "company_id": s.company_id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": msg_count,
            }
        )

    return result


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Obtém uma sessão específica com todas as mensagens.
    """
    session = chat_service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    messages = chat_service.get_messages(session_id, current_user.id)

    return {
        "session": {
            "id": session.id,
            "company_id": session.company_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "message_count": len(messages),
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Atualiza título da sessão.
    """
    session = chat_service.update_session_title(session_id, current_user.id, data.title)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    return {
        "id": session.id,
        "company_id": session.company_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "message_count": len(session.messages) if hasattr(session, "messages") else 0,
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Remove sessão e todas as mensagens.
    """
    deleted = chat_service.delete_session(session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return None


# ============================================================
# MENSAGENS
# ============================================================


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    session_id: int,
    role: str,
    content: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Adiciona mensagem manualmente à sessão (para testes/debug).
    """
    session = chat_service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    message = chat_service.add_message(session_id, role, content)
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@router.get("/sessions/{session_id}/history", response_model=list[MessageResponse])
def get_history(
    session_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Obtém histórico de mensagens formatado para o LLM.
    """
    messages = chat_service.get_messages(session_id, current_user.id, limit=limit)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
