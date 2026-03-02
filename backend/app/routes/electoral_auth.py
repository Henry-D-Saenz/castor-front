"""Electoral access authentication routes for solo-front."""
from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, redirect, render_template, request, session, url_for

from config import Config
from services.electoral_access import (
    normalize_code,
    _SESSION_KEY,
)

logger = logging.getLogger(__name__)

electoral_auth_bp = Blueprint("electoral_auth", __name__)


def _normalize_cedula(raw: str) -> str:
    """Keep only digits to normalize Colombian ID input."""
    return re.sub(r"[^0-9]", "", (raw or "").strip())


def _load_front_only_users() -> list[dict]:
    """Parse ELECTORAL_ACCESS_USERS JSON env into normalized user records."""
    raw = Config.ELECTORAL_ACCESS_USERS or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        logger.error("Invalid ELECTORAL_ACCESS_USERS JSON")
        return []
    if not isinstance(data, list):
        return []

    users = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cedula = _normalize_cedula(str(item.get("cedula", "")))
        code = normalize_code(str(item.get("code", "")))
        if not cedula or not code:
            continue
        users.append({
            "cedula": cedula,
            "code": code,
            "name": str(item.get("name") or f"Usuario {cedula[-4:]}"),
            "email": str(item.get("email") or f"{cedula}@local"),
        })
    return users


@electoral_auth_bp.route("/electoral/login", methods=["GET", "POST"])
def login():
    """Electoral access login via 16-char code."""
    if _SESSION_KEY in session:
        return redirect(url_for("web.campaign_team_dashboard"))

    error = None
    if request.method == "POST":
        raw_code = request.form.get("code", "")
        raw_cedula = request.form.get("cedula", "")
        normalized_cedula = _normalize_cedula(raw_cedula)
        normalized_input = normalize_code(raw_code)

        users = _load_front_only_users()
        if not users:
            error = "Configuración inválida: no hay usuarios de acceso definidos."
            return render_template("login_electoral.html", error=error)

        match = next(
            (
                u for u in users
                if u["cedula"] == normalized_cedula and u["code"] == normalized_input
            ),
            None,
        )
        if match:
            session.permanent = True
            session[_SESSION_KEY] = {
                "id": match["cedula"],
                "cedula": match["cedula"],
                "name": match["name"],
                "email": match["email"],
            }
            return redirect(url_for("web.campaign_team_dashboard"))
        error = "Código inválido o inactivo. Verifica e intenta de nuevo."
        return render_template("login_electoral.html", error=error)

    return render_template("login_electoral.html", error=error)


@electoral_auth_bp.route("/electoral/logout")
def logout():
    """Destroy electoral session and redirect to login."""
    session.pop(_SESSION_KEY, None)
    return redirect(url_for("electoral_auth.login"))
