"""Fetch + normalize OCR results for one document_id."""
from __future__ import annotations

import os
from typing import Any, Dict

import requests

from config import Config
from services.azure_ocr_service import get_metadata, get_results, normalize_to_form


def fetch_normalized_form(document_id: str) -> Dict[str, Any]:
    """Fetch OCR results for one document_id and return normalized form payload."""
    if Config.RESULTS_API_BASE_URL:
        base = Config.RESULTS_API_BASE_URL.rstrip("/")
        results_path = Config.RESULTS_API_RESULTS_PATH_TEMPLATE.format(document_id=document_id)
        metadata_path = Config.RESULTS_API_METADATA_PATH_TEMPLATE.format(document_id=document_id)
        headers = {"Content-Type": "application/json"}
        if Config.RESULTS_API_KEY:
            headers["Authorization"] = f"Bearer {Config.RESULTS_API_KEY}"

        results_resp = requests.get(
            f"{base}{results_path}",
            headers=headers,
            timeout=Config.RESULTS_API_TIMEOUT_SECONDS,
        )
        results_resp.raise_for_status()
        results = results_resp.json()
        if isinstance(results, dict) and "party_tables" not in results and isinstance(results.get("results"), dict):
            results = results["results"]

        metadata: Dict[str, Any] = {}
        try:
            metadata_resp = requests.get(
                f"{base}{metadata_path}",
                headers=headers,
                timeout=Config.RESULTS_API_TIMEOUT_SECONDS,
            )
            if metadata_resp.ok:
                metadata = metadata_resp.json() or {}
        except Exception:
            metadata = {}
    else:
        results = get_results(document_id, retries=3, retry_delay=1.0)
        if isinstance(results, dict) and "party_tables" not in results and isinstance(results.get("results"), dict):
            results = results["results"]
        metadata = get_metadata(document_id) if not results.get("summary_votes") else {}

    filename = (
        (metadata.get("filename") if isinstance(metadata, dict) else None)
        or (metadata.get("original_filename") if isinstance(metadata, dict) else None)
        or (results.get("filename") if isinstance(results, dict) else None)
        or f"{document_id}.pdf"
    )
    filename = os.path.basename(str(filename))

    return normalize_to_form(
        results=results,
        filename=filename,
        document_id=document_id,
        metadata=metadata if isinstance(metadata, dict) else None,
    )

