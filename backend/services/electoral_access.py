"""
Electoral access service — 16-char alphanumeric codes for campaign-team dashboard.
"""
from __future__ import annotations

import secrets
import string
from functools import wraps
from typing import Callable, Optional

MAX_ELECTORAL_USERS = 5
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 16


def generate_code() -> str:
    """Generate a 16-char alphanumeric uppercase code using secrets."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def format_code(raw: str) -> str:
    """Format raw 16-char code as XXXX-XXXX-XXXX-XXXX."""
    raw = raw.upper().replace("-", "")
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"


def normalize_code(code: str) -> str:
    """Strip dashes and uppercase — canonical form for DB lookup."""
    return code.upper().replace("-", "").strip()


def assign_code(user_id: str, db_session) -> str:
    """
    Assign or regenerate an electoral access code for a user.

    Raises ValueError if the 5-user limit would be exceeded.
    Returns the formatted code (XXXX-XXXX-XXXX-XXXX).
    """
    from models.database import User

    user: Optional[User] = db_session.query(User).filter_by(id=user_id).first()
    if user is None:
        raise ValueError(f"User {user_id} not found")

    # Count active electoral users excluding this user
    active_count = (
        db_session.query(User)
        .filter(
            User.electoral_access_active == True,  # noqa: E712
            User.id != user_id,
        )
        .count()
    )
    if active_count >= MAX_ELECTORAL_USERS and not user.electoral_access_active:
        raise ValueError("Límite de 5 usuarios electorales alcanzado")

    new_code = generate_code()
    user.electoral_access_code = new_code
    user.electoral_access_active = True
    # Caller is responsible for committing (use session_scope)
    db_session.flush()
    return format_code(new_code)


def validate_code(code: str, db_session, client_ip: Optional[str] = None) -> Optional[object]:
    """
    Look up an active electoral user by code.

    If the user has electoral_access_ip set, the provided client_ip must match.
    Returns the User ORM object or None.
    """
    from models.database import User

    raw = normalize_code(code)
    user = (
        db_session.query(User)
        .filter(
            User.electoral_access_code == raw,
            User.electoral_access_active == True,  # noqa: E712
        )
        .first()
    )
    if user is None:
        return None
    if user.electoral_access_ip:
        # IP already locked — must match
        if user.electoral_access_ip != (client_ip or ""):
            return None
    elif client_ip:
        # First login — lock the IP automatically
        user.electoral_access_ip = client_ip
        db_session.flush()
    return user


def set_allowed_ip(user_id: str, ip: Optional[str], db_session) -> None:
    """
    Set or clear the IP restriction for a user's electoral access.
    Pass ip=None to remove the restriction.
    """
    from models.database import User

    user: Optional[User] = db_session.query(User).filter_by(id=user_id).first()
    if user is None:
        raise ValueError(f"User {user_id} not found")
    user.electoral_access_ip = ip or None
    db_session.flush()


def revoke_code(user_id: str, db_session) -> None:
    """Deactivate electoral access for a user."""
    from models.database import User

    user: Optional[User] = db_session.query(User).filter_by(id=user_id).first()
    if user is None:
        raise ValueError(f"User {user_id} not found")
    user.electoral_access_active = False
    db_session.flush()


_SESSION_KEY = "electoral_user"


def require_electoral_access(f: Callable) -> Callable:
    """Flask route decorator: redirects to electoral login if session is missing."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import session, redirect, url_for
        if _SESSION_KEY not in session:
            return redirect(url_for("electoral_auth.login"))
        return f(*args, **kwargs)
    return decorated


def list_electoral_users(db_session) -> list[dict]:
    """List up to 5 users with active electoral access (code is masked)."""
    from models.database import User

    users = (
        db_session.query(User)
        .filter(User.electoral_access_active == True)  # noqa: E712
        .limit(MAX_ELECTORAL_USERS)
        .all()
    )
    result = []
    for u in users:
        masked = "****-****-****-****"
        if u.electoral_access_code and len(u.electoral_access_code) == 16:
            masked = f"{u.electoral_access_code[0:4]}-****-****-****"
        result.append(
            {
                "id": u.id,
                "email": u.email,
                "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                "code_masked": masked,
                "active": u.electoral_access_active,
                "allowed_ip": u.electoral_access_ip,
            }
        )
    return result
