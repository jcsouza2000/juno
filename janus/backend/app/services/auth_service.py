"""
AuthService — autenticação isolada do FastAPI.

Mantém a lógica de autenticação testável sem precisar subir o app.
A função `authenticate_user` em `app/auth.py` foi mantida por compatibilidade
e agora delega para esta classe.
"""

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.models import User

logger = get_logger(__name__)


class AuthService:
    """Operações de autenticação centralizadas."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def authenticate(self, email: str, password: str) -> User | None:
        """
        Verifica credenciais. Retorna o User se válido, None caso contrário.

        Por que não levantar exceção aqui? Porque diferentes camadas podem
        querer reagir de forma diferente (router HTTP devolve 401, CLI
        imprime mensagem, etc.). Service permanece neutro.
        """
        # Import tardio para evitar import circular com app.auth (que
        # também importa daqui em uma refatoração futura).
        from app.auth import verify_password

        user = self.get_user_by_email(email)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
