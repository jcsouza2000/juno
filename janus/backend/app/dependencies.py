from fastapi import Depends, HTTPException

from .auth import get_current_active_user
from .models import User


def require_company_access(
    company_id: int,
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role == "admin":
        return current_user

    user_company_ids = [c.id for c in current_user.companies]
    if company_id not in user_company_ids:
        raise HTTPException(status_code=403, detail="Voce nao tem acesso a esta empresa")
    return current_user
