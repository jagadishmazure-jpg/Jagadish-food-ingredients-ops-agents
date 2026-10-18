"""Feedback capture: thumbs/corrections, PII-scrubbed before storage."""

from __future__ import annotations

from .audit import AuditLog
from .pii import scrub


class FeedbackError(Exception):
    pass


class FeedbackStore:
    def __init__(self, audit: AuditLog | None = None) -> None:
        self.items: list[dict] = []
        self.audit = audit or AuditLog()

    def record(self, kind: str, text: str, session_id: str = "") -> dict:
        if kind not in ("thumbs_up", "thumbs_down", "correction"):
            raise FeedbackError(f"unknown feedback kind {kind!r}")
        if not text or not text.strip():
            raise FeedbackError("feedback text must not be empty")
        clean, n_redacted = scrub(text)
        item = {"kind": kind, "text": clean, "redactions": n_redacted,
                "session_id": session_id}
        self.items.append(item)
        self.audit.record("feedback", kind, clean[:120])
        return item
