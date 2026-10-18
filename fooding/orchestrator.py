"""ReAct orchestrator: classify, fan out across tools, audit every turn.

Multi-intent questions fan out to several tools in one turn (e.g. trial
pass rates + substitution options). Gated actions (formula approval,
label-claim sign-off) are blocked until a ConfirmationGate approves.
"""

from __future__ import annotations

import sqlite3

from . import pricesignal, sop_rag, substitute, text2sql, trials
from .audit import AuditLog
from .escalation import GATED_ACTIONS, classify_tier, gate_for


class Orchestrator:
    def __init__(self, conn: sqlite3.Connection,
                 price_feed=None, audit: AuditLog | None = None) -> None:
        self.conn = conn
        self.price_feed = price_feed or pricesignal.FakePriceFeed()
        self.audit = audit or AuditLog()

    def ask(self, question: str, approver=None) -> dict:
        tier = classify_tier(question)
        self.audit.record("orchestrator", "question",
                          f"[{tier}] {question[:120]}")
        # Gated actions never run on a bare question.
        for action in GATED_ACTIONS:
            if action.replace("_", " ") in question.lower():
                gate = gate_for(action, approver)
                decision = gate.request(question)
                self.audit.record("orchestrator", f"gate:{action}",
                                  str(decision["approved"]))
                return {"tier": "T4", "gated_action": action,
                        "decision": decision, "tools": []}

        tools: list[dict] = []
        # 1) structured data via text-to-SQL
        try:
            sql_answer = text2sql.answer(self.conn, question)
            tools.append({"tool": "text2sql", "result": sql_answer})
            intent = sql_answer["intent"]
        except text2sql.EscalationNeeded as e:
            tools.append({"tool": "text2sql", "escalated": str(e)})
            intent = None

        # 2) substitution engine for swap questions
        if any(w in question.lower() for w in ("substitut", "swap", "replace")):
            m = _parse_sub_request(question)
            if m:
                original, claim = m
                opts = substitute.rank_substitutes(self.conn, original, claim)
                tools.append({"tool": "substitute", "result": opts})

        # 3) trial tracker for trial questions
        if "trial" in question.lower():
            try:
                import re
                fid = re.search(r"\bF-[A-Z]+-\d+\b", question)
                if fid:
                    tools.append({"tool": "trials",
                                  "result": trials.trial_summary(
                                      self.conn, fid.group(0))})
            except trials.TrialError as e:
                tools.append({"tool": "trials", "escalated": str(e)})

        # 4) price signal for cost questions
        if "price" in question.lower():
            try:
                import re
                m = re.search(r"price of ([a-z ]+)", question.lower())
                if m:
                    tools.append({"tool": "price",
                                  "result": self.price_feed.price(
                                      m.group(1).strip())})
            except pricesignal.SignalGap as e:
                tools.append({"tool": "price", "gap": str(e)})

        # 5) SOP citations for how/policy questions
        if any(w in question.lower() for w in ("how", "policy", "sop", "process", "claim")):
            hits = sop_rag.retrieve(question)
            tools.append({"tool": "sop_rag",
                          "result": hits if hits else "not-found"})

        self.audit.record("orchestrator", "tools",
                          ",".join(t["tool"] for t in tools))
        return {"tier": tier, "intent": intent, "tools": tools}


def _parse_sub_request(question: str):
    import re
    m = re.search(r"substitut\w*\s+(?:for\s+)?([a-z ]+?)\s+for\s+([a-z ]+)",
                  question.lower())
    if m:
        return m.group(1).strip(), m.group(2).strip().rstrip("?")
    return None
