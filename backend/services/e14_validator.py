"""
E14 Validator — Post-processing validation and auto-correction engine.

Exploits 5 internal redundancies of the E-14 form to detect, diagnose,
and auto-correct OCR errors without re-calling the Vision API.

Validation levels:
  1. Hard constraints (non-negative, max bounds)
  2. Arithmetic reconciliation (sum == total)
  3. Three-way leveling (sufragantes vs urna vs total)
  4. Statistical plausibility (requires corpus)

Correction strategies (in e14_corrections.py):
  A. Override by leveling (confidence 0.85)
  B. Digit-swap OCR correction (confidence 0.45-0.70)
  C. Flag for manual review (confidence 0.0)
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .e14_constants import (
    ARITH_DELTA_CRITICAL,
    ARITH_DELTA_HIGH,
    ARITH_DELTA_MEDIUM,
    ARITH_TOLERANCE,
    ARITH_WARN_TOL,
    CONFIDENCE_PENALTIES,
    LEVELING_TOLERANCE,
    MAX_VOTES_PER_MESA,
    PRE_GATE_DIFF_THRESHOLD,
    REPEATED_CONSTANT_THRESHOLD,
    _safe_int,
    compute_full_sum,
    compute_party_sum,
)

logger = logging.getLogger(__name__)


def _pre_validation_gate(form: Dict[str, Any]) -> Dict[str, Any]:
    """PRE-01: Header Sanity Gate.

    Runs BEFORE any correction. If the header is broken, blocks ALL
    targeted fixes and auto-corrections — the form is classified as
    OCR_EXTRACTION_FAILURE, not an arithmetic error.
    """
    blockers: List[str] = []
    tv = _safe_int(form.get("total_votos"))
    suf = form.get("sufragantes_e11")
    urn = form.get("votos_en_urna")
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))
    no_marcados = _safe_int(form.get("votos_no_marcados"))

    suf_val = _safe_int(suf)
    urn_val = _safe_int(urn)

    # G-01 / A4: No anchor or header suspect
    # A4 is the specific sub-case: both anchors are 0 but total > 0
    # (typical of misread/shifted header — not just "missing")
    if suf is None and urn is None:
        blockers.append("G-01: sufragantes_e11=null AND votos_en_urna=null (no anchor)")
    elif suf_val == 0 and urn_val == 0:
        if tv > 0:
            blockers.append(
                f"A4: HEADER_SUSPECT — total_votos={tv} but "
                f"sufragantes_e11=0 AND votos_en_urna=0 "
                f"(header misread or shifted field)"
            )
        else:
            blockers.append(
                "G-01: sufragantes_e11=0 AND votos_en_urna=0 (no anchor)"
            )

    # G-02: total_votos > MAX_VOTES_PER_MESA
    if tv > MAX_VOTES_PER_MESA:
        blockers.append(
            f"G-02: total_votos={tv} > {MAX_VOTES_PER_MESA} "
            f"(probable code contamination)"
        )

    # G-03: blancos or nulos > total_votos
    if tv > 0 and (blancos > tv or nulos > tv):
        blockers.append(f"G-03: blancos={blancos} o nulos={nulos} > total={tv}")

    # G-04: |ARITH diff| > 50% of total_votos → extraction failure
    partidos = form.get("partidos", [])
    computed = compute_full_sum(partidos, blancos, nulos, no_marcados)
    if tv > 0 and abs(computed - tv) > PRE_GATE_DIFF_THRESHOLD * tv:
        blockers.append(
            f"G-04: |diff|={abs(computed - tv)} > 50% of total={tv} "
            f"(extraction failure, not arithmetic error)"
        )

    # G-05: total_votos exceeds both anchors by >10%
    anchor = max(suf_val, urn_val)
    if anchor > 0 and tv > anchor * 1.10:
        blockers.append(
            f"G-05: total_votos={tv} > max(suf={suf_val}, urn={urn_val})*1.10="
            f"{round(anchor * 1.10)} (header mismatch)"
        )

    passed = len(blockers) == 0
    # Refine category: A4 is HEADER_SUSPECT (not generic extraction failure)
    if passed:
        category = "OK"
    elif any(b.startswith("A4:") for b in blockers):
        category = "HEADER_SUSPECT"
    else:
        category = "OCR_EXTRACTION_FAILURE"
    return {
        "passed": passed,
        "blockers": blockers,
        "category": category,
    }


def _run_hard_constraints(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Level 1: Hard constraint checks."""
    checks = []
    partidos = form.get("partidos", [])
    total_votos = _safe_int(form.get("total_votos"))
    sufragantes = _safe_int(form.get("sufragantes_e11"))
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))
    no_marcados = _safe_int(form.get("votos_no_marcados"))

    # HC-01: All votes >= 0
    all_non_neg = all(_safe_int(p.get("votes")) >= 0 for p in partidos)
    all_non_neg = all_non_neg and blancos >= 0 and nulos >= 0 and no_marcados >= 0
    checks.append({"rule": "HC-01", "desc": "all_votes_non_negative",
                    "passed": all_non_neg})

    # HC-02: No party > total_votos
    max_party = max((_safe_int(p.get("votes")) for p in partidos), default=0)
    hc02 = total_votos == 0 or max_party <= total_votos
    checks.append({"rule": "HC-02", "desc": "no_party_exceeds_total",
                    "passed": hc02, "max_party": max_party})

    # HC-03: total_votos <= sufragantes_e11 (if both > 0)
    hc03 = True
    if total_votos > 0 and sufragantes > 0:
        hc03 = total_votos <= sufragantes + LEVELING_TOLERANCE
    checks.append({"rule": "HC-03", "desc": "total_leq_sufragantes",
                    "passed": hc03})

    # HC-04: blancos + nulos + no_marcados <= total_votos
    special_sum = blancos + nulos + no_marcados
    hc04 = total_votos == 0 or special_sum <= total_votos
    checks.append({"rule": "HC-04", "desc": "special_votes_leq_total",
                    "passed": hc04, "special_sum": special_sum})

    # HC-05: total_votos <= MAX_VOTES_PER_MESA
    hc05 = total_votos <= MAX_VOTES_PER_MESA
    checks.append({"rule": "HC-05", "desc": "total_within_mesa_limit",
                    "passed": hc05})

    # HC-06: No duplicate party_codes
    codes = [p.get("party_code", "") for p in partidos if p.get("party_code")]
    unique_codes = set(codes)
    hc06 = len(codes) == len(unique_codes)
    dup_codes = [c for c in unique_codes if codes.count(c) > 1] if not hc06 else []
    checks.append({"rule": "HC-06", "desc": "no_duplicate_parties",
                    "passed": hc06, "duplicate_codes": dup_codes})

    # HC-07: total_votos <= votos_en_urna (if both > 0)
    votos_urna = _safe_int(form.get("votos_en_urna"))
    hc07 = True
    if total_votos > 0 and votos_urna > 0:
        hc07 = total_votos <= votos_urna + LEVELING_TOLERANCE
    checks.append({"rule": "HC-07", "desc": "total_leq_urna",
                    "passed": hc07, "total_votos": total_votos,
                    "votos_en_urna": votos_urna})

    # TOT-STRICT: total_votos > max(suf, urna) + LEVELING_TOLERANCE
    votos_urna_ts = _safe_int(form.get("votos_en_urna"))
    anchor = max(sufragantes, votos_urna_ts)
    if anchor > 0 and total_votos > anchor + LEVELING_TOLERANCE:
        checks.append({
            "rule": "TOT-STRICT", "desc": "total_exceeds_anchor_plus_tolerance",
            "passed": False, "total_votos": total_votos, "anchor": anchor,
            "excess": total_votos - anchor, "suggests_reread": True,
        })

    # OUTLIER-01: Flag parties with > 40% of sufragantes (diagnostic)
    if sufragantes > 0:
        for p in partidos:
            votes = _safe_int(p.get("votes"))
            if votes > 0.4 * sufragantes:
                checks.append({
                    "rule": "OUTLIER-01",
                    "desc": "party_dominance_suspicious",
                    "passed": True,
                    "party": p.get("party_name", ""),
                    "votes": votes,
                    "pct_of_suf": round(votes / sufragantes * 100, 1),
                })

    return checks


def _run_arithmetic(form: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Level 2: Arithmetic reconciliation."""
    partidos = form.get("partidos", [])
    total_votos = _safe_int(form.get("total_votos"))
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))
    no_marcados = _safe_int(form.get("votos_no_marcados"))

    computed = compute_full_sum(partidos, blancos, nulos, no_marcados)
    diff = computed - total_votos
    abs_diff = abs(diff)

    if abs_diff == 0:
        status = "PASS"
    elif abs_diff <= ARITH_WARN_TOL:
        status = "WARN"
    else:
        status = "FAIL"

    passed = (status == "PASS")
    check = {
        "rule": "ARITH-01", "desc": "sum_equals_total",
        "passed": passed, "status": status,
        "computed_total": computed,
        "reported_total": total_votos, "diff": diff,
    }
    return check, diff


def _run_leveling(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Level 3: Three-way leveling (sufragantes vs urna vs total)."""
    checks = []
    suf = _safe_int(form.get("sufragantes_e11"))
    urn = _safe_int(form.get("votos_en_urna"))
    tv = _safe_int(form.get("total_votos"))

    if suf > 0 and urn > 0 and tv > 0:
        matches = []
        if abs(suf - urn) <= LEVELING_TOLERANCE:
            matches.append("suf_urn")
        if abs(suf - tv) <= LEVELING_TOLERANCE:
            matches.append("suf_tv")
        if abs(urn - tv) <= LEVELING_TOLERANCE:
            matches.append("urn_tv")

        passed = len(matches) >= 2
        checks.append({
            "rule": "NIV-01", "desc": "three_way_leveling",
            "passed": passed, "sufragantes": suf, "urna": urn,
            "total_votos": tv, "agreements": matches,
        })
    return checks


def run_statistical(
    form: Dict[str, Any], corpus_stats: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Level 4: Statistical plausibility (requires corpus averages)."""
    checks: List[Dict[str, Any]] = []
    total_votos = _safe_int(form.get("total_votos"))
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))

    if total_votos > 0:
        blancos_pct = blancos / total_votos * 100
        nulos_pct = nulos / total_votos * 100
        checks.append({
            "rule": "STAT-02", "desc": "blancos_in_range",
            "passed": 0 <= blancos_pct <= 25,
            "blancos_pct": round(blancos_pct, 1),
        })
        checks.append({
            "rule": "STAT-03", "desc": "nulos_in_range",
            "passed": 0 <= nulos_pct <= 10,
            "nulos_pct": round(nulos_pct, 1),
        })

    if corpus_stats:
        partidos = form.get("partidos", [])
        for p in partidos:
            name = p.get("party_name", "")
            votes = p.get("votes", 0)
            avg = corpus_stats.get(name, {}).get("avg", 0)
            if avg > 0 and votes > 3 * avg:
                checks.append({
                    "rule": "STAT-01", "desc": "party_vote_outlier",
                    "passed": False, "party": name,
                    "votes": votes, "corpus_avg": round(avg, 1),
                })

    # STAT-04: repeated constant — same vote value in ≥3 parties
    partidos = form.get("partidos", [])
    if len(partidos) >= 3:
        vote_counts: Dict[int, int] = defaultdict(int)
        for p in partidos:
            v = _safe_int(p.get("votes"))
            if v > 0:
                vote_counts[v] += 1
        for val, count in vote_counts.items():
            if count >= REPEATED_CONSTANT_THRESHOLD:
                checks.append({
                    "rule": "STAT-04", "desc": "repeated_constant_suspicious",
                    "passed": False,
                    "repeated_value": val, "occurrences": count,
                    "pct_of_parties": round(count / len(partidos) * 100, 1),
                })

    return checks


def compute_validation_confidence(
    checks: List[Dict[str, Any]], form: Dict[str, Any],
) -> float:
    """Compute a penalty-based validation confidence score.

    Base: 0.95. Penalties applied per check failure. Clamped [0.0, 0.95].
    """
    score = 0.95
    for c in checks:
        rule = c.get("rule", "")
        if rule == "HC-03" and not c["passed"]:
            score += CONFIDENCE_PENALTIES["HC-03_FAIL"]
        elif rule == "NIV-01" and not c["passed"]:
            score += CONFIDENCE_PENALTIES["NIV-01_FAIL"]
        elif rule == "ARITH-01":
            if c.get("status") == "FAIL":
                score += CONFIDENCE_PENALTIES["ARITH_FAIL"]
            elif c.get("status") == "WARN":
                score += CONFIDENCE_PENALTIES["ARITH_WARN"]

    ocr_conf = form.get("confidence", 0.95)
    if ocr_conf < 0.7:
        score += CONFIDENCE_PENALTIES["OCR_LOW_CONF"]

    null_count = sum(
        1 for f in ("sufragantes_e11", "votos_en_urna", "votos_no_marcados")
        if form.get(f) is None
    )
    if null_count > 0:
        score += CONFIDENCE_PENALTIES["CRITICAL_NULL"]

    return max(0.0, min(0.95, round(score, 4)))


def validate_form(
    form: Dict[str, Any],
    auto_correct: bool = False,
    corpus_stats: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Validate a single E-14 form and optionally auto-correct."""
    # Lazy import: breaks circular dep with e14_corrections
    from .e14_corrections import (
        apply_best_correction, strategy_a_leveling, strategy_b_digit_swap,
    )

    checks: List[Dict[str, Any]] = []
    diagnoses: List[Dict[str, Any]] = []

    pre_gate = _pre_validation_gate(form)
    checks.extend(_run_hard_constraints(form))

    arith_check, diff = _run_arithmetic(form)
    checks.append(arith_check)

    checks.extend(_run_leveling(form))
    checks.extend(run_statistical(form, corpus_stats))

    is_valid = all(c["passed"] for c in checks)

    corrections_applied: Dict[str, Any] = {}
    needs_human_review = False
    review_priority = "NONE"

    if not pre_gate["passed"]:
        needs_human_review = True
        review_priority = "CRITICAL"
        is_valid = False
        auto_correct = False

    # Handle ARITH WARN: not escalated to HITL
    arith_status = arith_check.get("status", "PASS")
    if arith_status == "WARN" and review_priority == "NONE":
        review_priority = "LOW"

    # Handle TOT-STRICT in auto_correct mode
    tot_strict = next(
        (c for c in checks if c.get("rule") == "TOT-STRICT" and not c["passed"]),
        None,
    )
    if tot_strict and auto_correct:
        form["total_votos"] = None
        corrections_applied["total_votos"] = None
        needs_human_review = True
        if review_priority not in ("CRITICAL",):
            review_priority = "HIGH"
        diagnoses.append({
            "field": "total_votos", "original": tot_strict["total_votos"],
            "suggested": None, "confidence": 0.0,
            "method": "TOT_STRICT_NULLIFY",
            "reasoning": (
                f"total_votos={tot_strict['total_votos']} exceeds anchor="
                f"{tot_strict['anchor']} by {tot_strict['excess']}; "
                "nullified for label-anchored re-read of page 11"
            ),
        })
    elif tot_strict and not auto_correct:
        diagnoses.append({
            "field": "total_votos", "original": tot_strict["total_votos"],
            "suggested": "re-read page 11",
            "confidence": 0.0, "method": "TOT_STRICT_DIAGNOSTIC",
            "reasoning": (
                f"total_votos={tot_strict['total_votos']} exceeds anchor="
                f"{tot_strict['anchor']} by {tot_strict['excess']}; "
                "suggest label-anchored re-read of page 11"
            ),
        })

    if not is_valid and diff != 0 and not tot_strict:
        leveling_fix = strategy_a_leveling(form, diff)
        if leveling_fix:
            diagnoses.append(leveling_fix)

        swap_fixes = strategy_b_digit_swap(form, diff)
        diagnoses.extend(swap_fixes)

        if auto_correct and diagnoses:
            applied, new_checks = apply_best_correction(
                form, checks, diagnoses, diff,
            )
            if applied:
                corrections_applied.update(applied)
                checks = new_checks
                is_valid = all(c["passed"] for c in checks)

        # Strategy C: Flag for manual review (don't downgrade gate CRITICAL)
        if not corrections_applied:
            needs_human_review = True
            if review_priority != "CRITICAL":
                if abs(diff) > ARITH_DELTA_CRITICAL:
                    review_priority = "CRITICAL"
                elif abs(diff) > ARITH_DELTA_HIGH:
                    review_priority = "HIGH"
                elif abs(diff) > ARITH_DELTA_MEDIUM:
                    review_priority = "MEDIUM"
                else:
                    review_priority = "LOW"

            # HITL-01: emit actionable review alert when arithmetic can't auto-correct
            checks.append({
                "rule": "HITL-01",
                "desc": "human_review_required",
                "passed": False,
                "reason": "arithmetic_mismatch",
                "diff": diff,
                "review_priority": review_priority,
                "message": (
                    f"Revisión humana requerida: diferencia aritmética de {diff:+d} votos "
                    f"no pudo corregirse automáticamente. "
                    f"Prioridad: {review_priority}."
                ),
            })

    hc_failures = [c for c in checks if not c["passed"] and c["rule"].startswith("HC")]
    if hc_failures:
        needs_human_review = True
        if review_priority == "NONE":
            review_priority = "MEDIUM"

    null_fields = []
    for field_name in ("sufragantes_e11", "votos_en_urna", "votos_no_marcados"):
        if form.get(field_name) is None:
            null_fields.append(f"FIELD_NOT_EXTRACTED: {field_name}")

    validation_confidence = compute_validation_confidence(checks, form)

    return {
        "is_valid": is_valid,
        "checks": checks,
        "diagnoses": diagnoses,
        "auto_corrected": bool(corrections_applied),
        "corrections_applied": corrections_applied,
        "needs_human_review": needs_human_review or bool(null_fields),
        "review_priority": review_priority,
        "validation_confidence": validation_confidence,
        "pre_validation_gate": pre_gate,
        "null_fields": null_fields,
    }


