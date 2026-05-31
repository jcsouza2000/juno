import json

from sqlalchemy.orm import Session

from . import models


def log_event(
    db: Session,
    company_id: int,
    entity_type: str,
    event_type: str,
    entity_id: int | None = None,
    old_state: dict | None = None,
    new_state: dict | None = None,
    user_id: str | None = None,
) -> None:
    db.add(
        models.EventLog(
            company_id=company_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            old_state=(
                json.dumps(old_state, ensure_ascii=False, default=str)
                if old_state is not None
                else None
            ),
            new_state=(
                json.dumps(new_state, ensure_ascii=False, default=str)
                if new_state is not None
                else None
            ),
            user_id=int(user_id) if isinstance(user_id, str) and user_id.isdigit() else None,
        )
    )
