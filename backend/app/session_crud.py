from datetime import datetime, timedelta

import secrets
from sqlalchemy.orm import Session

from .models import SessionToken


SESSION_TTL_MINUTES = 30


def create_session(db: Session, user_id: int) -> SessionToken:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(
        minutes=SESSION_TTL_MINUTES
    )

    session = SessionToken(
        id=token,
        user_id=user_id,
        expires_at=expires_at,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def get_session(
    db: Session,
    token: str,
) -> SessionToken | None:
    session = (
        db.query(SessionToken)
        .filter(SessionToken.id == token)
        .first()
    )

    if not session:
        return None

    if session.expires_at < datetime.utcnow():
        db.delete(session)
        db.commit()
        return None

    return session


def delete_session(db: Session, token: str) -> bool:
    session = (
        db.query(SessionToken)
        .filter(SessionToken.id == token)
        .first()
    )

    if not session:
        return False

    db.delete(session)
    db.commit()
    return True