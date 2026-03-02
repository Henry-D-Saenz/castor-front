"""
E14 Analytics — heavy aggregation queries extracted from E14JsonStore.

These methods operate on the store's form list and are called as
mix-in style functions receiving `self` (the store instance).
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .e14_constants import (
    ANOMALY_HIGH_RISK_THRESHOLD,
    ANOMALY_NEEDS_REVIEW_DEFAULT,
    ARITH_WARN_TOL,
    OCR_HIGH_RISK_THRESHOLD,
    OCR_MEDIUM_RISK_THRESHOLD,
    classify_ocr_risk,
    compute_full_sum,
    compute_party_sum,
    _safe_int,
)


def get_party_totals(
    store,
    limit: int = 30,
    departamento: Optional[str] = None,
    corporacion: Optional[str] = None,
) -> List[Dict]:
    """Party aggregates matching /api/e14-data/party-totals response."""
    store._ensure_loaded()
    filtered = store._filter_forms(
        corporacion=corporacion, departamento=departamento
    )
    agg: Dict[str, Dict] = defaultdict(
        lambda: {
            "votes": 0, "forms": set(), "conf_sum": 0.0, "conf_count": 0,
            "reviewable_votes": 0, "reviewable_forms": set(),
            "votes_high_risk": 0, "votes_medium_risk": 0, "votes_low_risk": 0,
        }
    )
    anomaly_ids: set = set()
    for f in filtered:
        party_sum = compute_party_sum(f["partidos"])
        total_votos = f.get("total_votos", 0)
        full_sum = compute_full_sum(
            f["partidos"], f.get("votos_blancos", 0),
            f.get("votos_nulos", 0), f.get("votos_no_marcados", 0),
        )
        has_arith = (
            full_sum > 0 and total_votos > 0
            and abs(full_sum - total_votos) > ARITH_WARN_TOL
        )
        if has_arith or f.get("ocr_confidence", 1.0) < OCR_MEDIUM_RISK_THRESHOLD:
            anomaly_ids.add(f["id"])

    for f in filtered:
        is_reviewable = f["id"] in anomaly_ids
        form_conf = f.get("ocr_confidence", 1.0)
        for p in f["partidos"]:
            name = p.get("party_name", "")
            a = agg[name]
            votes = p.get("votes", 0)
            a["votes"] += votes
            a["forms"].add(f["id"])
            a["conf_sum"] += p.get("confidence", 0)
            a["conf_count"] += 1
            if is_reviewable:
                a["reviewable_votes"] += votes
                a["reviewable_forms"].add(f["id"])
            # Classify votes by form-level OCR risk
            risk = classify_ocr_risk(form_conf)
            a[f"votes_{risk}_risk"] += votes

    ranked = sorted(agg.items(), key=lambda x: x[1]["votes"], reverse=True)[:limit]
    total_all = sum(a["votes"] for _, a in ranked)

    return [
        {
            "party_name": name,
            "total_votes": a["votes"],
            "mesas_count": len(a["forms"]),
            "avg_confidence": round(a["conf_sum"] / max(a["conf_count"], 1), 2),
            "percentage": round(a["votes"] / max(total_all, 1) * 100, 2),
            "reviewable_votes": a["reviewable_votes"],
            "reviewable_mesas": len(a["reviewable_forms"]),
            "votes_high_risk": a["votes_high_risk"],
            "votes_medium_risk": a["votes_medium_risk"],
            "votes_low_risk": a["votes_low_risk"],
        }
        for name, a in ranked
    ]


def get_anomalies(store, threshold: float = ANOMALY_NEEDS_REVIEW_DEFAULT) -> Dict[str, Any]:
    """Classify forms by OCR quality, extraction failures, and arithmetic."""
    store._ensure_loaded()
    high_risk: list = []
    needs_review: list = []
    arithmetic_errors: list = []
    extraction_failures: list = []
    ocr_mapping_errors: list = []
    healthy: list = []

    for f in store._forms:
        conf = f["ocr_confidence"]
        party_sum = compute_party_sum(f["partidos"])
        total = _safe_int(f.get("total_votos"))
        blancos = _safe_int(f.get("votos_blancos"))
        nulos = _safe_int(f.get("votos_nulos"))
        no_marcados = _safe_int(f.get("votos_no_marcados"))
        full_sum = compute_full_sum(f["partidos"], blancos, nulos, no_marcados)
        has_arith_error = (
            full_sum > 0 and total > 0
            and abs(full_sum - total) > ARITH_WARN_TOL
        )

        # Check pre-validation gate from validation data
        v = f.get("validation", {})
        pre_gate = v.get("pre_validation_gate", {})
        is_extraction_failure = not pre_gate.get("passed", True)

        entry = {
            "id": f["id"], "mesa_id": f["mesa_id"],
            "filename": f["filename"],
            "departamento": f["departamento"],
            "municipio": f["municipio"],
            "corporacion": f["corporacion"],
            "zona_cod": f["zona_cod"],
            "puesto_cod": f["puesto_cod"],
            "mesa_num": f["mesa_num"],
            "ocr_confidence": conf,
            "total_votos": total,
            "votos_blancos": blancos,
            "votos_nulos": nulos,
            "party_sum": party_sum,
            "full_sum": full_sum,
            "warnings": f["warnings"],
        }

        # Check STAT-04: repeated constant OCR pattern
        has_repeated_constant = any(
            c.get("rule") == "STAT-04" and not c.get("passed")
            for c in v.get("checks", [])
        )

        if is_extraction_failure:
            entry["issue"] = "extraction_failure"
            entry["gate_blockers"] = pre_gate.get("blockers", [])
            extraction_failures.append(entry)
        elif has_repeated_constant:
            entry["issue"] = "ocr_mapping_error"
            stat04 = next(
                (c for c in v.get("checks", [])
                 if c.get("rule") == "STAT-04" and not c.get("passed")),
                {},
            )
            entry["repeated_value"] = stat04.get("repeated_value")
            entry["occurrences"] = stat04.get("occurrences")
            ocr_mapping_errors.append(entry)
        elif has_arith_error:
            entry["issue"] = "arithmetic_error"
            arithmetic_errors.append(entry)
        elif conf < ANOMALY_HIGH_RISK_THRESHOLD:
            entry["issue"] = "high_risk"
            high_risk.append(entry)
        elif conf < threshold:
            entry["issue"] = "needs_review"
            needs_review.append(entry)
        else:
            healthy.append(entry)

    # Classify auto-correctable forms using validation data
    auto_correctable = []
    for f in store._forms:
        v = f.get("validation", {})
        diagnoses = v.get("diagnoses", [])
        if diagnoses and not v.get("auto_corrected", False):
            best = diagnoses[0]
            if not isinstance(best, dict):
                continue
            auto_correctable.append({
                "id": f["id"],
                "mesa_id": f["mesa_id"],
                "filename": f["filename"],
                "departamento": f["departamento"],
                "municipio": f["municipio"],
                "best_fix": {
                    "field": best.get("field", ""),
                    "original": best.get("original"),
                    "suggested": best.get("suggested"),
                    "confidence": best.get("confidence", 0),
                    "method": best.get("method", ""),
                },
            })

    return {
        "high_risk_count": len(high_risk),
        "needs_review_count": len(needs_review),
        "arithmetic_errors_count": len(arithmetic_errors),
        "extraction_failures_count": len(extraction_failures),
        "ocr_mapping_errors_count": len(ocr_mapping_errors),
        "healthy_count": len(healthy),
        "auto_correctable_count": len(auto_correctable),
        "total": len(store._forms),
        "threshold": threshold,
        "high_risk": high_risk,
        "needs_review": needs_review,
        "arithmetic_errors": arithmetic_errors,
        "extraction_failures": extraction_failures,
        "ocr_mapping_errors": ocr_mapping_errors,
        "auto_correctable": auto_correctable,
    }


def get_confidence_distribution(store, bins: int = 10) -> List[Dict]:
    """Histogram of OCR confidence values."""
    store._ensure_loaded()
    step = 1.0 / bins
    histogram = []
    for i in range(bins):
        lo = round(i * step, 2)
        hi = round((i + 1) * step, 2)
        count = sum(1 for f in store._forms if lo <= f["ocr_confidence"] < hi)
        if i == bins - 1:
            count += sum(1 for f in store._forms if f["ocr_confidence"] == 1.0)
        histogram.append({"range_start": lo, "range_end": hi, "count": count})
    return histogram


def get_votes_by_municipality(
    store, departamento: Optional[str] = None
) -> List[Dict]:
    """Votes grouped by municipality with top parties."""
    store._ensure_loaded()
    filtered = store._filter_forms(departamento=departamento)

    groups: Dict[str, Dict] = {}
    for f in filtered:
        key = f"{f['departamento']}|{f['municipio']}"
        if key not in groups:
            groups[key] = {
                "departamento": f["departamento"],
                "municipio": f["municipio"],
                "total_votos": 0, "votos_blancos": 0,
                "votos_nulos": 0, "total_mesas": 0,
                "parties": defaultdict(int),
            }
        g = groups[key]
        g["total_votos"] += f["total_votos"]
        g["votos_blancos"] += f["votos_blancos"] or 0
        g["votos_nulos"] += f["votos_nulos"] or 0
        g["total_mesas"] += 1
        for p in f["partidos"]:
            g["parties"][p.get("party_name", "")] += p.get("votes", 0)

    result = []
    for g in groups.values():
        top = sorted(g["parties"].items(), key=lambda x: x[1], reverse=True)[:5]
        result.append({
            "departamento": g["departamento"],
            "municipio": g["municipio"],
            "total_votos": g["total_votos"],
            "votos_blancos": g["votos_blancos"],
            "votos_nulos": g["votos_nulos"],
            "total_mesas": g["total_mesas"],
            "top_parties": [{"party_name": n, "votes": v} for n, v in top],
        })
    return sorted(result, key=lambda x: x["total_votos"], reverse=True)


def get_summary_by_dept(store) -> List[Dict]:
    """Summary by dept+corp matching /api/e14-data/summary/by-dept."""
    store._ensure_loaded()
    groups: Dict[tuple, Dict] = defaultdict(
        lambda: {"count": 0, "votos": 0, "conf_sum": 0.0}
    )
    for f in store._forms:
        key = (f["departamento"], f["corporacion"])
        g = groups[key]
        g["count"] += 1
        g["votos"] += f["total_votos"]
        g["conf_sum"] += f["ocr_confidence"]

    result = [
        {
            "departamento": k[0], "corporacion": k[1],
            "total_mesas": g["count"], "ocr_completed": g["count"],
            "ocr_pending": 0, "total_votos": g["votos"],
            "avg_confidence": round(g["conf_sum"] / max(g["count"], 1), 2),
        }
        for k, g in groups.items()
    ]
    return sorted(result, key=lambda x: x["total_mesas"], reverse=True)


def get_zero_vote_alerts(store) -> Dict[str, Any]:
    """Detect parties with 0 votes in forms where they appear.

    Cross-references against global averages to flag suspicious cases:
    a party that normally gets votes but has 0 in a specific mesa
    is more suspicious than a tiny party that never gets votes.
    """
    store._ensure_loaded()

    # Step 1: compute global avg votes per party across all forms
    party_global: Dict[str, Dict] = defaultdict(
        lambda: {"total_votes": 0, "appearances": 0}
    )
    for f in store._forms:
        for p in f["partidos"]:
            name = p.get("party_name", "")
            party_global[name]["total_votes"] += p.get("votes", 0)
            party_global[name]["appearances"] += 1

    # Step 2: find zero-vote entries
    alerts: list = []
    for f in store._forms:
        for p in f["partidos"]:
            if p.get("votes", 0) != 0:
                continue
            name = p.get("party_name", "")
            g = party_global.get(name, {})
            appearances = g.get("appearances", 1)
            avg_votes = g.get("total_votes", 0) / max(appearances, 1)

            severity = "info"
            if avg_votes >= 10:
                severity = "high"
            elif avg_votes >= 3:
                severity = "medium"

            alerts.append({
                "form_id": f["id"],
                "mesa_id": f["mesa_id"],
                "filename": f["filename"],
                "departamento": f["departamento"],
                "municipio": f["municipio"],
                "puesto_cod": f["puesto_cod"],
                "mesa_num": f["mesa_num"],
                "party_name": name,
                "party_code": p.get("party_code", ""),
                "avg_votes_other_mesas": round(avg_votes, 1),
                "appearances": appearances,
                "severity": severity,
            })

    # Sort: high severity first, then by avg_votes descending
    severity_order = {"high": 0, "medium": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order[a["severity"]], -a["avg_votes_other_mesas"]))

    high = [a for a in alerts if a["severity"] == "high"]
    medium = [a for a in alerts if a["severity"] == "medium"]
    info = [a for a in alerts if a["severity"] == "info"]

    return {
        "total_alerts": len(alerts),
        "high_count": len(high),
        "medium_count": len(medium),
        "info_count": len(info),
        "alerts": alerts,
    }
