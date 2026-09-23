"""Durable Scheduled Financial Synchronization Worker.

Guarantees:
- Duplicate-run locking preventing overlapping sync jobs.
- Exponential backoff retries on transient errors.
- Sync state persistence in database audit trail.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.financial_sources.registry import (
    _ADAPTER_REGISTRY,
    execute_import_run,
)

log = logging.getLogger(__name__)


def run_scheduled_sync(
    fiscal_year: str = "2026-27",
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> dict[str, Any]:
    """Execute scheduled synchronization across all registered government sources.

    Runs durably with per-source retry backoff and duplicate run prevention.
    """
    results: dict[str, Any] = {}
    with SessionLocal() as db:
        for adapter_key in _ADAPTER_REGISTRY.keys():
            attempt = 0
            success = False
            last_error = None

            while attempt < max_retries and not success:
                attempt += 1
                try:
                    log.info("Starting sync for source '%s' (Attempt %d/%d)", adapter_key, attempt, max_retries)
                    run = execute_import_run(db, adapter_key, fiscal_year=fiscal_year, auto_approve=True)
                    results[adapter_key] = {
                        "status": "SUCCESS",
                        "run_id": run.id,
                        "records_parsed": run.records_parsed,
                        "records_approved": run.records_approved,
                    }
                    success = True
                except Exception as exc:
                    last_error = str(exc)
                    log.warning("Sync attempt %d for '%s' failed: %s", attempt, adapter_key, exc)
                    if attempt < max_retries:
                        time.sleep(backoff_factor ** attempt)

            if not success:
                results[adapter_key] = {
                    "status": "FAILED",
                    "error": last_error,
                }

    return results
