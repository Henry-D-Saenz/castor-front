"""E14 Corrections — Auto-correction strategies for E-14 OCR errors."""
from typing import Any, Dict, List, Optional, Tuple

from .e14_constants import LEVELING_TOLERANCE, _safe_int, compute_full_sum, compute_party_sum

# Common OCR digit confusion pairs (handwritten)
OCR_DIGIT_PAIRS: List[Tuple[int, int]] = [
    (1, 7), (0, 6), (0, 8), (3, 8), (5, 6), (4, 9),
]
_KNOWN_SWAPS: set = set()
for a, b in OCR_DIGIT_PAIRS:
    _KNOWN_SWAPS.add((a, b))
    _KNOWN_SWAPS.add((b, a))


def _decompose_digits(value: int) -> List[int]:
    """Decompose a non-negative integer into its digits."""
    if value == 0:
        return [0]
    digits = []
    while value > 0:
        digits.append(value % 10)
        value //= 10
    digits.reverse()
    return digits


def _compose_digits(digits: List[int]) -> int:
    """Recompose digits into an integer."""
    result = 0
    for d in digits:
        result = result * 10 + d
    return result


def _try_digit_swaps(
    value: int, target_diff: int,
) -> List[Dict[str, Any]]:
    """Try single-digit swaps on value that would reduce the total diff."""
    digits = _decompose_digits(value)
    candidates = []
    for pos in range(len(digits)):
        original_digit = digits[pos]
        for new_digit in range(10):
            if new_digit == original_digit:
                continue
            new_digits = digits.copy()
            new_digits[pos] = new_digit
            new_value = _compose_digits(new_digits)
            change = value - new_value
            if change == target_diff:
                is_known = (original_digit, new_digit) in _KNOWN_SWAPS
                candidates.append({
                    "new_value": new_value,
                    "pos": pos,
                    "original_digit": original_digit,
                    "new_digit": new_digit,
                    "known_pair": is_known,
                    "confidence": 0.70 if is_known else 0.45,
                })
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates


def strategy_a_leveling(
    form: Dict[str, Any], diff: int,
) -> Optional[Dict[str, Any]]:
    """Strategy A: Override total_votos by leveling agreement."""
    suf = _safe_int(form.get("sufragantes_e11"))
    urn = _safe_int(form.get("votos_en_urna"))
    tv = _safe_int(form.get("total_votos"))

    if suf > 0 and urn > 0 and abs(suf - urn) <= LEVELING_TOLERANCE and abs(tv - suf) > LEVELING_TOLERANCE:
        partidos = form.get("partidos", [])
        blancos = _safe_int(form.get("votos_blancos"))
        nulos = _safe_int(form.get("votos_nulos"))
        no_marcados = _safe_int(form.get("votos_no_marcados"))
        computed = compute_full_sum(partidos, blancos, nulos, no_marcados)

        if abs(computed - suf) <= LEVELING_TOLERANCE:
            return {
                "field": "total_votos",
                "original": tv,
                "suggested": suf,
                "confidence": 0.85,
                "method": "LEVELING_OVERRIDE",
                "reasoning": (
                    f"sufragantes_e11={suf} == votos_en_urna={urn} "
                    f"and computed_sum={computed} matches; "
                    f"total_votos={tv} is outlier"
                ),
            }
    return None


def strategy_b_digit_swap(
    form: Dict[str, Any], diff: int,
) -> List[Dict[str, Any]]:
    """Strategy B: Single-digit swap on party votes to close the gap."""
    if abs(diff) > 50 or abs(diff) == 0:
        return []

    diagnoses = []
    partidos = form.get("partidos", [])

    for i, p in enumerate(partidos):
        votes = _safe_int(p.get("votes"))
        if votes == 0:
            continue
        candidates = _try_digit_swaps(votes, diff)
        for c in candidates:
            diagnoses.append({
                "field": f"partidos[{i}].votes",
                "party_name": p.get("party_name", ""),
                "original": votes,
                "suggested": c["new_value"],
                "confidence": c["confidence"],
                "method": "DIGIT_SWAP",
                "reasoning": (
                    f"Digit swap pos {c['pos']}: "
                    f"{c['original_digit']}->{c['new_digit']} "
                    f"({'known OCR pair' if c['known_pair'] else 'unknown pair'}), "
                    f"closes diff from {diff} to 0"
                ),
            })

    for field_name in ("votos_blancos", "votos_nulos", "votos_no_marcados"):
        value = _safe_int(form.get(field_name))
        if value == 0:
            continue
        candidates = _try_digit_swaps(value, diff)
        for c in candidates:
            diagnoses.append({
                "field": field_name,
                "original": value,
                "suggested": c["new_value"],
                "confidence": c["confidence"],
                "method": "DIGIT_SWAP",
                "reasoning": (
                    f"Digit swap pos {c['pos']}: "
                    f"{c['original_digit']}->{c['new_digit']} "
                    f"({'known OCR pair' if c['known_pair'] else 'unknown pair'}), "
                    f"closes diff from {diff} to 0"
                ),
            })

    diagnoses.sort(key=lambda d: d["confidence"], reverse=True)
    return diagnoses


def _party_to_page(party_idx: int, total_pages: int = 11) -> int:
    """Map party index to PDF page number (1-indexed)."""
    return 1 if party_idx == 0 else min(party_idx + 1, total_pages - 1)


def apply_best_correction(
    form: Dict[str, Any],
    checks: List[Dict[str, Any]],
    diagnoses: List[Dict[str, Any]],
    diff: int,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply best correction; returns (corrections, updated_checks) or (None, checks)."""
    # Lazy import: breaks circular dep with e14_validator
    from .e14_validator import _run_arithmetic

    best = diagnoses[0]
    if best["confidence"] < 0.70:
        return None, checks

    field = best["field"]
    new_val = best["suggested"]
    corrections: Dict[str, Any] = {}

    if field == "total_votos":
        form["total_votos"] = new_val
    elif field.startswith("partidos["):
        idx = int(field.split("[")[1].split("]")[0])
        form["partidos"][idx]["votes"] = new_val
    elif field in ("votos_blancos", "votos_nulos", "votos_no_marcados"):
        form[field] = new_val

    corrections[field] = new_val

    arith_recheck, _ = _run_arithmetic(form)
    if arith_recheck["passed"]:
        for i, c in enumerate(checks):
            if c["rule"] == "ARITH-01":
                checks[i] = arith_recheck
                break

    return corrections, checks


def identify_suspect_parties(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify parties most likely causing ARITH mismatch, ordered by suspicion."""
    partidos = form.get("partidos", [])
    total_votos = _safe_int(form.get("total_votos"))
    sufragantes = _safe_int(form.get("sufragantes_e11"))
    blancos = _safe_int(form.get("votos_blancos"))
    nulos = _safe_int(form.get("votos_nulos"))
    no_marcados = _safe_int(form.get("votos_no_marcados"))

    computed = compute_full_sum(partidos, blancos, nulos, no_marcados)
    diff = computed - total_votos

    if diff == 0:
        return []

    suspects: List[Dict[str, Any]] = []
    abs_diff = abs(diff)

    for i, p in enumerate(partidos):
        votes = p.get("votes", 0)
        if votes == 0:
            continue

        residual_diff = diff - votes
        abs_residual = abs(residual_diff)

        if abs_diff > 0:
            score = max(0.0, 1.0 - (abs_residual / abs_diff))
        else:
            score = 0.0

        if sufragantes > 0 and votes > 0.4 * sufragantes:
            score = min(1.0, score + 0.3)

        if score < 0.1:
            continue

        pct_explained = round(score * 100, 1)
        reason = (
            f"Votes={votes} explains {pct_explained}% of ARITH diff={diff}"
        )

        suspects.append({
            "party_idx": i,
            "party_name": p.get("party_name", ""),
            "votes": votes,
            "page_number": _party_to_page(i),
            "suspicion_score": round(score, 3),
            "reason": reason,
        })

    suspects.sort(key=lambda s: s["suspicion_score"], reverse=True)
    return suspects


def validate_batch(
    forms: List[Dict[str, Any]],
    auto_correct: bool = False,
) -> Dict[str, Any]:
    """Validate a batch of forms and return summary statistics."""
    # Lazy import: breaks circular dep with e14_validator
    from .e14_validator import validate_form

    party_agg: Dict[str, Dict[str, Any]] = {}
    for f in forms:
        for p in f.get("partidos", []):
            name = p.get("party_name", "")
            if name not in party_agg:
                party_agg[name] = {"total": 0, "count": 0}
            party_agg[name]["total"] += p.get("votes", 0)
            party_agg[name]["count"] += 1

    corpus_stats = {
        name: {"avg": agg["total"] / max(agg["count"], 1)}
        for name, agg in party_agg.items()
    }

    valid_count = 0
    auto_corrected_count = 0
    manual_required_count = 0
    results: List[Dict[str, Any]] = []

    for f in forms:
        validation = validate_form(
            f, auto_correct=auto_correct, corpus_stats=corpus_stats,
        )
        form_id = f.get("id", f.get("extraction_id", ""))

        if validation["is_valid"]:
            valid_count += 1
        if validation["auto_corrected"]:
            auto_corrected_count += 1
        if validation["needs_human_review"]:
            manual_required_count += 1

        results.append({
            "form_id": form_id,
            "mesa_id": f.get("mesa_id", ""),
            "filename": f.get("filename", ""),
            "validation": validation,
        })

    return {
        "total": len(forms),
        "valid": valid_count,
        "auto_corrected": auto_corrected_count,
        "manual_required": manual_required_count,
        "invalid_uncorrectable": (
            len(forms) - valid_count - auto_corrected_count
        ),
        "results": results,
    }


