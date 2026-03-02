"""
E14 PMSN Collector — Batch runner and aggregator for PMSN rules.

Separated from e14_pmsn_rules.py to keep each file under 400 lines.
Provides run_pmsn_rules, collect_pmsn_alerts, and get_municipios_pareto.
"""
import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config
from services.e14_json_store import E14JsonStore, get_e14_json_store

from .e14_pmsn_rules import (
    _normalize_text,
    sum_pmsn_votes,
    check_pmsn_01_camara_senado,
    check_pmsn_02_tachones,
    check_pmsn_03_aritmetica_e14,
    check_pmsn_04_e11_vs_e14,
    check_pmsn_05_senado_pareto,
    check_pmsn_06_firmas,
    check_pmsn_07_nulo_alto,
)

logger = logging.getLogger(__name__)

_PARETO_CACHE: List[str] = []
_PARETO_MTIME: float = 0.0

_RISK_DOWNGRADE = {'R_ALTO': 'R_MEDIO', 'R_MEDIO': 'R_BAJO', 'R_BAJO': 'R_BAJO'}
_RELEVANCE_FILTER_RULES = {'PMSN-03', 'PMSN-04', 'PMSN-06', 'PMSN-07'}


def _mesa_id(form: Dict[str, Any]) -> str:
    return form.get("mesa_id") or form.get("header", {}).get("mesa_id") or ''



def get_municipios_pareto() -> List[str]:
    """Load and cache the pareto municipality list for PMSN-05."""
    global _PARETO_CACHE, _PARETO_MTIME
    pareto_file = getattr(Config, "PMSN_PARETO_FILE", None)
    if not pareto_file:
        return []

    try:
        mtime = os.path.getmtime(pareto_file)
    except OSError:
        logger.warning("PMSN pareto file missing: %s", pareto_file)
        _PARETO_CACHE = []
        _PARETO_MTIME = 0
        return []

    if _PARETO_CACHE and _PARETO_MTIME == mtime:
        return _PARETO_CACHE

    try:
        with open(pareto_file, 'r', encoding='utf-8') as stream:
            data = json.load(stream)
        normalized = [
            _normalize_text(entry.get("municipio"))
            for entry in data
            if entry.get("municipio")
        ]
        _PARETO_CACHE = normalized
        _PARETO_MTIME = mtime
        return normalized
    except Exception as exc:
        logger.warning("Failed to load PMSN pareto list (%s): %s", pareto_file, exc)
        _PARETO_CACHE = []
        _PARETO_MTIME = 0
        return []


def run_pmsn_rules(
    form: Dict[str, Any],
    senado_form: Optional[Dict[str, Any]] = None,
    municipios_pareto: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Run all PMSN rules on a single form.

    Args:
        form: E-14 form data (can be Cámara or Senado).
        senado_form: Matching Senado form for the same mesa (for PMSN-01).
        municipios_pareto: List of pareto municipality names (for PMSN-05).

    Returns:
        List of PMSN alerts triggered.
    """
    alerts: List[Dict[str, Any]] = []

    if senado_form is not None:
        alert = check_pmsn_01_camara_senado(form, senado_form)
        if alert:
            alerts.append(alert)

    alerts.extend(check_pmsn_02_tachones(form))

    alert = check_pmsn_03_aritmetica_e14(form)
    if alert:
        alerts.append(alert)

    alert = check_pmsn_04_e11_vs_e14(form)
    if alert:
        alerts.append(alert)

    if municipios_pareto:
        alert = check_pmsn_05_senado_pareto(form, municipios_pareto)
        if alert:
            alerts.append(alert)

    alert = check_pmsn_06_firmas(form)
    if alert:
        alerts.append(alert)

    alert = check_pmsn_07_nulo_alto(form)
    if alert:
        alerts.append(alert)

    return alerts


def collect_pmsn_alerts(store: Optional[E14JsonStore] = None) -> Dict[str, Any]:
    """Run PMSN rules across the E-14 store and return alerts plus roll-ups."""
    if store is None:
        store = get_e14_json_store()

    store._ensure_loaded()
    forms = list(getattr(store, "_forms", []))

    senado_lookup: Dict[str, Dict[str, Any]] = {}
    for form in forms:
        corp = _normalize_text(form.get("corporacion"))
        if "SENADO" in corp:
            mid = _mesa_id(form)
            if mid in senado_lookup:
                logger.warning(
                    "collect_pmsn_alerts: duplicate Senado mesa_id=%s — "
                    "second form (%s) overwrites first (%s)",
                    mid,
                    form.get("filename", "?"),
                    senado_lookup[mid].get("filename", "?"),
                )
            senado_lookup[mid] = form

    pareto_municipios = get_municipios_pareto()

    pmsn_votes_lookup = {
        _mesa_id(f): sum_pmsn_votes(f.get('partidos', []))
        for f in forms
    }

    alerts: List[Dict[str, Any]] = []
    rule_counts = Counter()
    risk_counts = Counter()

    for form in forms:
        corp = _normalize_text(form.get("corporacion"))
        mesa_id = _mesa_id(form)
        senado_form = senado_lookup.get(mesa_id) if "CAMARA" in corp else None
        matched = run_pmsn_rules(form, senado_form, pareto_municipios)
        if not matched:
            continue

        pmsn_v = pmsn_votes_lookup.get(mesa_id, 0)
        pmsn_relevant = pmsn_v > 0

        for alert in matched:
            risk_type = alert['risk_type']
            if not pmsn_relevant and alert['rule_id'] in _RELEVANCE_FILTER_RULES:
                risk_type = _RISK_DOWNGRADE[risk_type]

            rule_counts[alert["rule_id"]] += 1
            risk_counts[risk_type] += 1
            alerts.append({
                **alert,
                "risk_type": risk_type,
                "pmsn_votes": pmsn_v,
                "pmsn_relevant": pmsn_relevant,
                "departamento": form.get("departamento") or form.get("header", {}).get("departamento", ""),
                "municipio": form.get("municipio") or form.get("header", {}).get("municipio", ""),
                "corporacion": form.get("corporacion", ""),
                "filename": form.get("filename", ""),
                "form_id": form.get("id"),
                "mesa_id": mesa_id,
                "zona_cod": form.get("zona_cod") or form.get("header", {}).get("zona_cod", ""),
                "puesto_cod": form.get("puesto_cod") or form.get("header", {}).get("puesto_cod", ""),
                "puesto_nombre": form.get("puesto_nombre") or form.get("lugar") or "",
                "mesa_num": form.get("mesa_num") or form.get("header", {}).get("mesa_num", ""),
                "processed_at": form.get("processed_at"),
                "total_votos": form.get("total_votos", 0),
            })

    _risk_priority = {'R_ALTO': 3, 'R_MEDIO': 2, 'R_BAJO': 1}
    alert_risk_map: Dict[str, str] = {}
    for a in alerts:
        mid = a["mesa_id"]
        incoming = a.get("risk_type", "R_BAJO")
        if _risk_priority.get(incoming, 0) > _risk_priority.get(alert_risk_map.get(mid, ''), 0):
            alert_risk_map[mid] = incoming

    forms_pmsn = []
    for f in forms:
        pmsn_v = sum_pmsn_votes(f.get('partidos', []))
        total_v = f.get('total_votos', 0)
        mid = _mesa_id(f)
        forms_pmsn.append({
            'form_id': f.get('id'),
            'mesa_id': mid,
            'departamento': f.get('departamento', ''),
            'municipio': f.get('municipio', ''),
            'zona_cod': f.get('zona_cod', ''),
            'puesto_cod': f.get('puesto_cod', ''),
            'mesa_num': f.get('mesa_num', ''),
            'pmsn_votes': pmsn_v,
            'total_votos': total_v,
            'has_alert': mid in alert_risk_map,
            'risk_level': alert_risk_map.get(mid, ''),
        })

    total_forms = len(forms)
    total_pmsn_votes = sum(fp['pmsn_votes'] for fp in forms_pmsn)

    def _percent(count: int) -> float:
        return round((count / total_forms) * 100, 1) if total_forms else 0.0

    return {
        "total_forms": total_forms,
        "alerts_count": len(alerts),
        "total_pmsn_votes": total_pmsn_votes,
        "timestamp": datetime.utcnow().isoformat(),
        "rule_counts": dict(rule_counts),
        "rule_percentages": {rule: _percent(count) for rule, count in rule_counts.items()},
        "risk_counts": dict(risk_counts),
        "risk_percentages": {risk: _percent(count) for risk, count in risk_counts.items()},
        "alerts": alerts,
        "forms_pmsn": forms_pmsn,
    }
