"""PII scrubber: redacts email/phone/SSN-like patterns before storage.

Free-text feedback is scrubbed BEFORE it reaches the audit log — the lesson
from the sibling repos, where unscrubbed correction text was stored.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL]"),
    # Phone: (555) 123-4567, +1 (555) 123-4567, 555.123.4567, 555-123-4567.
    # The (?<!\w) guard and the shape (3-3-4 digits) keep dates like
    # 2026-10-18 intact. Listed BEFORE any generic digit-run pattern.
    (re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
     "[PHONE]"),
    # SSN: strict 3-2-4 shape — does not match dates.
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Card: four groups of four (space or dash) or 13-16 contiguous digits.
    (re.compile(r"\b(?:\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}|\d{13,16})\b"), "[CARD]"),
    (re.compile(r"\b(?:acct|account)[\s#:]*\d{4,}\b", re.IGNORECASE), "[ACCOUNT]"),
]


def scrub(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, redaction_count)."""
    count = 0
    for pattern, placeholder in _PATTERNS:
        text, n = pattern.subn(placeholder, text)
        count += n
    return text, count
