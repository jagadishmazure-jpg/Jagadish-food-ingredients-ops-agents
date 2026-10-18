"""T1-T4 escalation tiers plus confirmation gates.

Formula approvals and label-claim sign-offs are always confirmation-gated:
a named approver must confirm, and a timed-out gate denies by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

TIERS = {
    "T1": "routine: answer directly from records",
    "T2": "needs R&D review: ambiguous intent or missing parameter",
    "T3": "needs QA review: failing trials, micro issues, claim risk",
    "T4": "human decision required: formula approval, label-claim sign-off",
}


def classify_tier(question: str, intent: str | None = None) -> str:
    q = question.lower()
    if any(w in q for w in ("approve", "sign-off", "signoff", "release formula")):
        return "T4"
    if any(w in q for w in ("micro", "failed", "reject", "recall")):
        return "T3"
    if intent is None:
        return "T2"
    return "T1"


@dataclass
class ConfirmationGate:
    action: str
    approver: Callable[[str], bool] | None = None
    timeout_seconds: int = 300

    def request(self, detail: str = "") -> dict:
        """Ask for confirmation. Timeout or decline -> denied (fail closed)."""
        if self.approver is None:
            return {"action": self.action, "approved": False,
                    "reason": "no approver wired; gate denies by default"}
        try:
            ok = bool(self.approver(detail))
        except Exception:
            ok = False
        return {"action": self.action, "approved": ok,
                "reason": "approved by named approver" if ok else "denied"}


# Actions that always require confirmation.
GATED_ACTIONS = {"approve_formula", "sign_off_claim"}


def gate_for(action: str, approver=None) -> ConfirmationGate:
    if action not in GATED_ACTIONS:
        raise ValueError(f"{action!r} is not a gated action")
    return ConfirmationGate(action=action, approver=approver)
