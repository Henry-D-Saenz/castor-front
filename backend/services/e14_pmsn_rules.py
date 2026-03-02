"""E14 PMSN Rules — Reglas de negocio para auditoría de formularios E-14.

PMSN-01: Diferencia ≥10% Cámara vs Senado  → R1 Alto
PMSN-02: Tachones/enmendaduras vigilados    → R2 Alto/Medio
PMSN-03: Diferencias aritméticas E-14       → R3 Alto
PMSN-04: Diferencias E-11 vs E-14           → R4 Alto
PMSN-05: 0-1 votos Senado en municipios pareto → R5 Medio
PMSN-06: E-14 con < 3 firmas               → R6 Alto
PMSN-07: Voto nulo ≥ 6%                    → R7 Bajo
"""
import logging
import unicodedata
from typing import Any, Dict, List, Optional

from .e14_constants import (
    ARITH_WARN_TOL,
    PMSN_03_DIFF_ALTO,
    PMSN_03_DIFF_MEDIO,
    PMSN_04_DIFF_ALTO,
    PMSN_04_DIFF_MEDIO,
    PMSN_07_NULO_ALTO,
    PMSN_07_NULO_MEDIO,
    PMSN_CAMARA_SENADO_DIFF_PCT,
    PMSN_MIN_FIRMAS,
    PMSN_NULO_PCT_THRESHOLD,
    PMSN_PARTIDOS_TACHON,
    PMSN_RISK_ALTO,
    PMSN_RISK_BAJO,
    PMSN_RISK_MEDIO,
    PMSN_SENADO_MIN_VOTES_PARETO,
    PRE_GATE_DIFF_THRESHOLD,
    _safe_int,
    compute_party_sum,
)

logger = logging.getLogger(__name__)


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ''
    normalized = unicodedata.normalize('NFD', value.upper().strip())
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def _pmsn_alert(
    rule_id: str,
    description: str,
    risk_type: str,
    risk_label: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "description": description,
        "risk_type": risk_type,
        "risk_label": risk_label,
        "details": details,
    }


def sum_pmsn_votes(partidos: list) -> int:
    """Suma votos del Movimiento de Salvación Nacional."""
    return sum(
        _safe_int(p.get('votes'))
        for p in partidos
        if 'SALVACION' in _normalize_text(p.get('party_name') or '')
    )


def check_pmsn_01_camara_senado(
    camara_form: Dict[str, Any],
    senado_form: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """R1 — Cámara supera Senado ≥10% en la misma mesa."""
    cam_total = _safe_int(camara_form.get("total_votos"))
    sen_total = _safe_int(senado_form.get("total_votos"))

    if sen_total <= 0 or cam_total <= sen_total:
        return None

    diff_pct = (cam_total - sen_total) / sen_total
    if diff_pct < PMSN_CAMARA_SENADO_DIFF_PCT:
        return None

    return _pmsn_alert(
        rule_id="PMSN-01",
        description=(
            f"Cámara ({cam_total}) supera Senado ({sen_total}) "
            f"en {diff_pct:.1%} (umbral: {PMSN_CAMARA_SENADO_DIFF_PCT:.0%})"
        ),
        risk_type=PMSN_RISK_ALTO,
        risk_label="R1: Riesgo Alto (Rojo)",
        details={
            "camara_total": cam_total,
            "senado_total": sen_total,
            "diff_pct": round(diff_pct * 100, 1),
            "mesa_id": camara_form.get("mesa_id", ""),
        },
    )


def check_pmsn_02_tachones(
    form: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """R2 — Tachones/enmendaduras en partidos vigilados."""
    alerts: List[Dict[str, Any]] = []
    for p in form.get("partidos", []):
        if not (p.get("tachones", False) or p.get("enmendaduras", False)):
            continue

        party_name = (p.get("party_name", "") or "").upper().strip()
        is_pmsn = "SALVACION" in party_name or "NUEVO LIBERALISMO" in party_name
        is_vigilado = any(v in party_name for v in PMSN_PARTIDOS_TACHON)

        if not is_pmsn and not is_vigilado:
            continue

        if is_pmsn:
            risk_type, risk_label = PMSN_RISK_ALTO, "R2: Riesgo Alto (Rojo) — PMSN"
        else:
            risk_type, risk_label = PMSN_RISK_MEDIO, "R2: Riesgo Medio (Naranja) — CD/PH"

        alerts.append(_pmsn_alert(
            rule_id="PMSN-02",
            description=f"Tachón/enmendadura detectado en partido '{party_name}'",
            risk_type=risk_type,
            risk_label=risk_label,
            details={
                "party_name": party_name,
                "party_code": p.get("party_code", ""),
                "votes": _safe_int(p.get("votes")),
                "mesa_id": form.get("mesa_id", ""),
                "is_pmsn": is_pmsn,
            },
        ))

    return alerts


def check_pmsn_03_aritmetica_e14(
    form: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """R3 — Diferencia aritmética E-14: suma != total_votos."""
    total_votos = _safe_int(form.get("total_votos"))
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))
    no_marcados = _safe_int(form.get("votos_no_marcados"))
    partidos = form.get("partidos", [])

    party_sum = compute_party_sum(partidos)
    full_computed = party_sum + blancos + nulos + no_marcados
    full_diff = full_computed - total_votos

    # No anomaly: full sum matches declared total
    if full_diff == 0:
        return None

    # Within handwriting-noise tolerance — same threshold used by e14_validator ARITH_WARN
    if abs(full_diff) <= ARITH_WARN_TOL:
        return None

    # diff shown in dashboard = party_sum vs total_votos (matches OCR party table)
    diff = party_sum - total_votos

    # Total no extraído por OCR
    if total_votos == 0 and party_sum > 0:
        return _pmsn_alert(
            rule_id="PMSN-03",
            description=f"Total no extraído por OCR: suma_partidos={party_sum} vs total_votos=0.",
            risk_type=PMSN_RISK_BAJO,
            risk_label="R3: Total no extraído (OCR)",
            details={
                "computed_sum": party_sum, "total_votos": 0, "diff": diff,
                "party_sum": party_sum, "blancos": blancos, "nulos": nulos,
                "no_marcados": no_marcados, "mesa_id": form.get("mesa_id", ""),
                "ocr_noise_suspected": True,
            },
        )

    # Diferencia >50%: probable ruido OCR
    if total_votos > 0 and abs(full_diff) > PRE_GATE_DIFF_THRESHOLD * total_votos:
        return _pmsn_alert(
            rule_id="PMSN-03",
            description=(
                f"Posible ruido OCR: suma_partidos={party_sum} vs total_votos={total_votos} "
                f"(diff={diff}, supera {int(PRE_GATE_DIFF_THRESHOLD * 100)}% del total)"
            ),
            risk_type=PMSN_RISK_BAJO,
            risk_label="R3: Posible Ruido OCR (Amarillo)",
            details={
                "computed_sum": party_sum, "total_votos": total_votos, "diff": diff,
                "party_sum": party_sum, "blancos": blancos, "nulos": nulos,
                "no_marcados": no_marcados, "mesa_id": form.get("mesa_id", ""),
                "ocr_noise_suspected": True,
            },
        )

    abs_diff = abs(full_diff)
    if abs_diff > PMSN_03_DIFF_ALTO:
        risk_type, risk_label = PMSN_RISK_ALTO,  "R3: Riesgo Alto (Rojo)"
    elif abs_diff > PMSN_03_DIFF_MEDIO:
        risk_type, risk_label = PMSN_RISK_MEDIO, "R3: Riesgo Medio (Naranja)"
    else:
        risk_type, risk_label = PMSN_RISK_BAJO,  "R3: Riesgo Bajo (Amarillo)"

    return _pmsn_alert(
        rule_id="PMSN-03",
        description=(
            f"Diferencia aritmética E-14: suma_partidos={party_sum} vs "
            f"total_votos={total_votos} (diff={diff})"
        ),
        risk_type=risk_type,
        risk_label=risk_label,
        details={
            "computed_sum": party_sum, "total_votos": total_votos, "diff": diff,
            "party_sum": party_sum, "blancos": blancos, "nulos": nulos,
            "no_marcados": no_marcados, "mesa_id": form.get("mesa_id", ""),
        },
    )


def check_pmsn_04_e11_vs_e14(
    form: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """R4 — Diferencia sufragantes E-11 vs total_votos E-14."""
    sufragantes = _safe_int(form.get("sufragantes_e11"))
    total_votos = _safe_int(form.get("total_votos"))

    if sufragantes <= 0 or total_votos <= 0:
        return None

    diff = abs(sufragantes - total_votos)
    if diff == 0:
        return None

    if diff > PMSN_04_DIFF_ALTO:
        risk_type, risk_label = PMSN_RISK_ALTO,  "R4: Riesgo Alto (Rojo)"
    elif diff > PMSN_04_DIFF_MEDIO:
        risk_type, risk_label = PMSN_RISK_MEDIO, "R4: Riesgo Medio (Naranja)"
    else:
        risk_type, risk_label = PMSN_RISK_BAJO,  "R4: Riesgo Bajo (Amarillo)"

    return _pmsn_alert(
        rule_id="PMSN-04",
        description=(
            f"Diferencia E-11 vs E-14: sufragantes={sufragantes} vs "
            f"total_votos={total_votos} (diff={diff})"
        ),
        risk_type=risk_type,
        risk_label=risk_label,
        details={
            "sufragantes_e11": sufragantes, "total_votos": total_votos,
            "diff": diff, "mesa_id": form.get("mesa_id", ""),
        },
    )


def check_pmsn_05_senado_pareto(
    form: Dict[str, Any],
    municipios_pareto: List[str],
) -> Optional[Dict[str, Any]]:
    """R5 — 0 o 1 votos PMSN a Senado.

    - Municipio pareto confirmado y ≤1 voto: R_MEDIO
    - Fallback: 0 votos en cualquier Senado (cubre truncaciones OCR del municipio): R_BAJO
    """
    if "SENADO" not in (form.get("corporacion", "") or "").upper():
        return None

    pmsn_votes = sum_pmsn_votes(form.get("partidos", []))
    if pmsn_votes >= PMSN_SENADO_MIN_VOTES_PARETO:
        return None

    municipio_raw = form.get("municipio", "")
    municipio = _normalize_text(municipio_raw)

    normalized_pareto = {_normalize_text(m) for m in (municipios_pareto or [])}
    is_pareto = bool(normalized_pareto) and municipio in normalized_pareto

    if is_pareto:
        risk_type = PMSN_RISK_MEDIO
        risk_label = "R5: Riesgo Medio (Naranja)"
        description = (
            f"Mesa con solo {pmsn_votes} voto(s) PMSN a Senado "
            f"en municipio pareto '{municipio_raw or municipio}'"
        )
    elif pmsn_votes == 0:
        # Fallback: 0 votos es siempre sospechoso aunque OCR haya truncado el municipio
        risk_type = PMSN_RISK_BAJO
        risk_label = "R5: 0 votos PMSN Senado (Amarillo)"
        description = (
            f"0 votos PMSN en Senado — municipio '{municipio_raw or municipio}' "
            f"(posible truncación OCR; verificar si es municipio pareto)"
        )
    else:
        return None

    return _pmsn_alert(
        rule_id="PMSN-05",
        description=description,
        risk_type=risk_type,
        risk_label=risk_label,
        details={
            "pmsn_votes": pmsn_votes, "municipio": municipio_raw or municipio,
            "is_pareto": is_pareto,
            "corporacion": (form.get("corporacion", "") or "").upper(),
            "mesa_id": form.get("mesa_id", ""),
        },
    )


def check_pmsn_06_firmas(
    form: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """R6 — E-14 con menos de 3 firmas registradas."""
    raw_firmas = form.get("num_firmas", form.get("firmas_count"))
    firmas_list = form.get("firmas", [])
    has_list = isinstance(firmas_list, list) and len(firmas_list) > 0

    if raw_firmas is None and not has_list:
        return None  # OCR no extrajo firmas — evitar falsos positivos

    num_firmas = _safe_int(raw_firmas) if raw_firmas is not None else 0
    if has_list and len(firmas_list) > num_firmas:
        num_firmas = len(firmas_list)

    if num_firmas >= PMSN_MIN_FIRMAS:
        return None

    return _pmsn_alert(
        rule_id="PMSN-06",
        description=f"E-14 con solo {num_firmas} firma(s) (mínimo: {PMSN_MIN_FIRMAS})",
        risk_type=PMSN_RISK_ALTO,
        risk_label="R6: Riesgo Alto (Rojo)",
        details={
            "num_firmas": num_firmas, "min_requerido": PMSN_MIN_FIRMAS,
            "mesa_id": form.get("mesa_id", ""),
        },
    )


def check_pmsn_07_nulo_alto(
    form: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """R7 — Voto nulo ≥ 6% del total."""
    total_votos = _safe_int(form.get("total_votos"))
    nulos = _safe_int(form.get("votos_nulos"))

    if total_votos <= 0:
        return None

    nulo_pct = nulos / total_votos
    if nulo_pct < PMSN_NULO_PCT_THRESHOLD:
        return None

    if nulo_pct >= PMSN_07_NULO_ALTO:
        risk_type, risk_label = PMSN_RISK_ALTO,  "R7: Riesgo Alto (Rojo)"
    elif nulo_pct >= PMSN_07_NULO_MEDIO:
        risk_type, risk_label = PMSN_RISK_MEDIO, "R7: Riesgo Medio (Naranja)"
    else:
        risk_type, risk_label = PMSN_RISK_BAJO,  "R7: Riesgo Bajo (Amarillo)"

    return _pmsn_alert(
        rule_id="PMSN-07",
        description=(
            f"Voto nulo alto: {nulos} nulos = {nulo_pct:.1%} "
            f"del total (umbral: {PMSN_NULO_PCT_THRESHOLD:.0%})"
        ),
        risk_type=risk_type,
        risk_label=risk_label,
        details={
            "votos_nulos": nulos, "total_votos": total_votos,
            "nulo_pct": round(nulo_pct * 100, 1),
            "mesa_id": form.get("mesa_id", ""),
        },
    )


# Re-exports para compatibilidad con callers que importan desde aquí
from .e14_pmsn_collector import (  # noqa: F401
    collect_pmsn_alerts,
    get_municipios_pareto,
    run_pmsn_rules,
)
