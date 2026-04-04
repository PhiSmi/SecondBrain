"""Event publisher for the n7 Event Hub.

Fire-and-forget: publishes events in a background thread so it never
blocks the ingestion pipeline or query handlers.

Requires EVENT_HUB_URL and EVENT_HUB_TOKEN environment variables.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_URL = os.getenv("EVENT_HUB_URL", "").rstrip("/")
_TOKEN = os.getenv("EVENT_HUB_TOKEN", "")
_TIMEOUT = 5


def _post_event(body: dict[str, Any]) -> None:
    if not _URL:
        logger.debug("EVENT_HUB_URL not set — event not published")
        return
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    try:
        r = httpx.post(_URL, json=body, headers=headers, timeout=_TIMEOUT)
        if r.status_code in (200, 201):
            data = r.json()
            if data.get("deduplicated"):
                logger.debug("Event deduplicated: %s", body.get("event_type"))
            else:
                logger.info("Event published: %s → %s", body.get("event_type"), data.get("routed_to", []))
        else:
            logger.warning("Event hub returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("Event publish failed (non-blocking): %s", exc)


def publish_event(
    event_type: str,
    severity: str,
    payload: dict[str, Any] | None = None,
    dedup_key: str | None = None,
) -> None:
    """Publish an event from SecondBrain to the Event Hub (fire-and-forget)."""
    body: dict[str, Any] = {
        "source": "secondbrain",
        "event_type": event_type,
        "severity": severity,
    }
    if payload:
        body["payload"] = payload
    if dedup_key:
        body["dedup_key"] = dedup_key

    thread = threading.Thread(target=_post_event, args=(body,), daemon=True)
    thread.start()
