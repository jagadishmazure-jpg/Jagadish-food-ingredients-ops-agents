"""Stdlib logic behind the Streamlit demo (fully tested; demo/app.py is thin)."""

from __future__ import annotations

import sqlite3

from . import pricesignal, sop_rag, substitute, text2sql, trials
from .telemetry import build_db
from .views import create_views

DEFAULT_QUESTIONS = [
    "Which formulations are in trial?",
    "What is the pass rate for F-CLEAN-01?",
    "Suggest substitutes for cane sugar for reduced sugar",
    "What is the cost impact of date paste?",
    "Which products carry the clean label claim?",
]


def demo_db() -> sqlite3.Connection:
    conn = build_db()
    create_views(conn)
    return conn


def answer_question(question: str) -> dict:
    """Answer one demo question: SQL rows + substitution ranking + SOP hit."""
    conn = demo_db()
    out: dict = {"question": question}
    try:
        out["sql"] = text2sql.answer(conn, question)
    except text2sql.EscalationNeeded as e:
        out["sql"] = {"escalated": str(e)}
    if "substitut" in question.lower():
        out["substitutes"] = substitute.rank_substitutes(
            conn, "cane sugar", "reduced sugar")
    hits = sop_rag.retrieve(question)
    out["sop"] = hits[0] if hits else None
    return out


def substitution_showcase() -> list[dict]:
    """The differentiator, runnable in one call for the demo."""
    conn = demo_db()
    return substitute.rank_substitutes(conn, "cane sugar", "reduced sugar")


def trial_showcase() -> dict:
    conn = demo_db()
    return {
        "summary": trials.trial_summary(conn, "F-CLEAN-01"),
        "cycles": trials.cycle_analytics(conn),
    }


def price_showcase() -> dict:
    return pricesignal.FakePriceFeed().price("date paste")
