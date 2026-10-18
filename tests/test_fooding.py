"""Regression checks for Jagadish-food-ingredients-ops-agents (synthetic data)."""


import pytest

from fooding import audit, escalation, feedback, pii, pricesignal, sop_rag, substitute, text2sql, trials
from fooding.demo_helpers import (
    answer_question,
    price_showcase,
    substitution_showcase,
    trial_showcase,
)
from fooding.orchestrator import Orchestrator
from fooding.telemetry import build_db
from fooding.views import GatewayError, create_views, run_query


@pytest.fixture()
def conn():
    c = build_db()
    create_views(c)
    yield c
    c.close()


# --- seed anchors -----------------------------------------------------------

def test_anchor_formulation_in_trial(conn):
    row = conn.execute(
        "SELECT status, target_claim FROM formulations WHERE form_id='F-CLEAN-01'"
    ).fetchone()
    assert row == ("in_trial", "clean label")


def test_anchor_substitution_match(conn):
    row = conn.execute(
        "SELECT func_match FROM substitutions WHERE sub_id='SUB-01'").fetchone()
    assert row[0] == pytest.approx(0.82)


def test_anchor_trial_failed_texture(conn):
    row = conn.execute(
        "SELECT outcome, texture FROM trials WHERE trial_id='T-002'").fetchone()
    assert row == ("fail", 5)


def test_anchor_preservative_not_clean_label(conn):
    row = conn.execute(
        "SELECT clean_label FROM ingredients WHERE name='sodium benzoate'").fetchone()
    assert row[0] == 0


# --- gateway ----------------------------------------------------------------

def test_gateway_select_ok(conn):
    cols, rows = run_query(conn, "SELECT form_id FROM v_formulations")
    assert "form_id" in cols and len(rows) == 5


def test_gateway_rejects_delete(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "DELETE FROM trials")


def test_gateway_rejects_hidden_write(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-02"):
        run_query(conn, "SELECT * FROM v_formulations WHERE product = 'x' OR 1=1; UPDATE trials SET outcome='pass'")


def test_gateway_literal_no_false_positive(conn):
    # 'UPDATE' inside a quoted literal must not trip SEC-SELECT-02
    cols, rows = run_query(conn, "SELECT * FROM v_trial_outcomes WHERE notes LIKE '%UPDATE%'")
    assert isinstance(rows, list)


def test_gateway_comment_prefix_rejected(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "-- harmless comment\nDROP TABLE ingredients")


def test_gateway_row_cap(conn):
    cols, rows = run_query(conn, "SELECT * FROM v_trial_outcomes")
    assert len(rows) <= 100


# --- text-to-SQL intents ------------------------------------------------------

def test_intent_formulations_by_status(conn):
    out = text2sql.answer(conn, "Which formulations are in trial?")
    assert out["intent"] == "formulations_by_status"
    assert any(r["form_id"] == "F-CLEAN-01" for r in out["rows"])


def test_intent_trial_pass_rates(conn):
    out = text2sql.answer(conn, "What is the pass rate for F-CLEAN-01?")
    assert out["intent"] == "trial_pass_rates"
    by_outcome = {r["outcome"]: r["n"] for r in out["rows"]}
    assert by_outcome == {"pass": 2, "fail": 1}


def test_intent_substitution_options(conn):
    out = text2sql.answer(conn, "Suggest substitutes for cane sugar")
    assert out["intent"] == "substitution_options"
    assert any(r["substitute"] == "date paste" for r in out["rows"])


def test_intent_cost_impact(conn):
    out = text2sql.answer(conn, "What is the cost impact of date paste?")
    assert out["intent"] == "cost_impact"
    assert out["rows"][0]["cost_per_kg"] == pytest.approx(3.40)


def test_intent_claim_coverage(conn):
    out = text2sql.answer(conn, "Which products carry the clean label claim?")
    assert out["intent"] == "claim_coverage"
    assert {r["form_id"] for r in out["rows"]} == {"F-CLEAN-01", "F-CLEAN-02", "F-LEG-01"}


def test_intent_retry_then_escalate(conn):
    # trial intent without a formulation id: retry broadens once
    out = text2sql.answer(conn, "What is the pass rate?")
    assert out["intent"] == "trial_pass_rates"


def test_intent_no_match_escalates(conn):
    with pytest.raises(text2sql.EscalationNeeded):
        text2sql.answer(conn, "What is the weather on Mars?")


# --- substitution engine (differentiator) ------------------------------------

def test_sub_ranking_order(conn):
    opts = substitute.rank_substitutes(conn, "cane sugar", "reduced sugar")
    assert [o["substitute"] for o in opts] == ["date paste", "stevia leaf extract"]
    assert opts[0]["score"] > opts[1]["score"]


def test_sub_breakdown_transparent(conn):
    opts = substitute.rank_substitutes(conn, "cane sugar", "reduced sugar")
    b = opts[0]["breakdown"]
    assert "0.50*" in b and "cost delta" in b and "label improves" in b


def test_sub_func_floor(conn):
    # insert a junk candidate below the 0.50 floor
    conn.execute(
        "INSERT INTO substitutions VALUES ('SUB-X','cane sugar','sawdust','reduced sugar',0.10,-1.00,'worsens')")
    opts = substitute.rank_substitutes(conn, "cane sugar", "reduced sugar")
    assert all(o["substitute"] != "sawdust" for o in opts)


def test_sub_cost_always_reported(conn):
    opts = substitute.rank_substitutes(conn, "sodium benzoate", "clean label")
    assert opts[0]["cost_delta_per_kg"] == pytest.approx(2.70)


def test_sub_unknown_ingredient_empty(conn):
    assert substitute.rank_substitutes(conn, "unobtainium", "clean label") == []


def test_sub_claim_mismatch_empty(conn):
    # date paste is a reduced-sugar candidate, not a clean-label one for sugar
    assert substitute.rank_substitutes(conn, "cane sugar", "dairy free") == []


def test_sub_cheaper_scores_full_cost(conn):
    opts = substitute.rank_substitutes(conn, "whey protein isolate", "dairy free")
    assert opts[0]["substitute"] == "pea protein isolate"
    assert opts[0]["cost_delta_per_kg"] == pytest.approx(-2.60)


# --- trial tracker (differentiator) -------------------------------------------

def test_trial_summary_pass_rate(conn):
    s = trials.trial_summary(conn, "F-CLEAN-01")
    assert s["n_trials"] == 3 and s["n_pass"] == 2
    assert s["pass_rate"] == pytest.approx(0.6667, abs=1e-4)


def test_trial_summary_failing_criteria(conn):
    s = trials.trial_summary(conn, "F-CLEAN-01")
    assert "texture" in s["failing_criteria"]


def test_trial_summary_unknown_form(conn):
    with pytest.raises(trials.TrialError):
        trials.trial_summary(conn, "F-NOPE-99")


def test_record_trial_validation(conn):
    with pytest.raises(trials.TrialError):
        trials.record_trial(conn, "F-CLEAN-01", "B-104", "maybe", 8, 8, 1, 1)
    with pytest.raises(trials.TrialError):
        trials.record_trial(conn, "F-CLEAN-01", "B-104", "pass", 11, 8, 1, 1)
    with pytest.raises(trials.TrialError):
        trials.record_trial(conn, "F-NOPE-99", "B-104", "pass", 8, 8, 1, 1)


def test_record_trial_roundtrip(conn):
    tid = trials.record_trial(conn, "F-SUGAR-01", "B-203", "pass", 8, 8, 1, 1, "ok")
    assert tid.startswith("T-F-SUGAR-01-")
    s = trials.trial_summary(conn, "F-SUGAR-01")
    assert s["n_trials"] == 3


def test_cycle_analytics(conn):
    cycles = {c["form_id"]: c for c in trials.cycle_analytics(conn)}
    assert cycles["F-CLEAN-01"]["trial_cycles"] == 3
    assert cycles["F-PRO-01"]["ever_passed"] is True
    assert cycles["F-LEG-01"]["ever_passed"] is False


# --- SOP RAG ------------------------------------------------------------------

def test_rag_citation_format():
    hits = sop_rag.retrieve("how are substitutes scored")
    assert hits, "expected at least one SOP hit"
    assert hits[0]["citation"].endswith(".md §Scoring") or "§" in hits[0]["citation"]


def test_rag_not_found():
    assert sop_rag.retrieve("quantum cryptography key rotation") == []


def test_rag_skips_title_only():
    chunks = sop_rag.load_chunks()
    for c in chunks:
        assert len(c["text"].split()) > 3


def test_rag_claim_definition():
    hits = sop_rag.retrieve("what does clean label mean")
    assert any("sop-04" in h["citation"] for h in hits)


# --- price signal ---------------------------------------------------------------

def test_fake_price(conn):
    p = pricesignal.FakePriceFeed().price("date paste")
    assert p["usd_per_kg"] == pytest.approx(3.40)
    assert p["backend"] == "fake"


def test_fake_price_unknown():
    with pytest.raises(pricesignal.SignalGap):
        pricesignal.FakePriceFeed().price("moon dust")


def test_live_price_gap():
    with pytest.raises(pricesignal.SignalGap):
        pricesignal.LivePriceFeed().price("date paste")


# --- escalation -----------------------------------------------------------------

def test_tier_formula_approval():
    assert escalation.classify_tier("please approve the formula") == "T4"


def test_tier_micro_issue():
    assert escalation.classify_tier("micro panel failed on B-401") == "T3"


def test_gate_approves():
    g = escalation.gate_for("approve_formula", approver=lambda d: True)
    assert g.request("F-CLEAN-01")["approved"] is True


def test_gate_denies_without_approver():
    g = escalation.gate_for("approve_formula")
    d = g.request("F-CLEAN-01")
    assert d["approved"] is False


def test_gate_unknown_action():
    with pytest.raises(ValueError):
        escalation.gate_for("launch_rockets")


# --- audit ----------------------------------------------------------------------

def test_audit_chain_ok():
    log = audit.AuditLog()
    log.record("r&d", "question", "which formulations are in trial?")
    log.record("agent", "answer", "3 rows")
    assert log.verify() == {"ok": True, "entries": 2}


def test_audit_tamper_detected():
    log = audit.AuditLog()
    log.record("r&d", "question", "x")
    log.entries[0]["detail"] = "tampered"
    assert log.verify()["ok"] is False


# --- PII + feedback ---------------------------------------------------------------

def test_pii_scrub_email_phone():
    clean, n = pii.scrub("call me at jane@verdant.test or 555-123-4567")
    assert "[EMAIL]" in clean and "[PHONE]" in clean and n == 2


def test_feedback_scrubbed_before_storage():
    store = feedback.FeedbackStore()
    item = store.record("correction", "my email is jane@verdant.test, fix the texture score")
    assert "jane@verdant.test" not in item["text"]
    assert item["redactions"] == 1


def test_feedback_validation():
    store = feedback.FeedbackStore()
    with pytest.raises(feedback.FeedbackError):
        store.record("applause", "great")
    with pytest.raises(feedback.FeedbackError):
        store.record("thumbs_up", "   ")


def test_feedback_audited():
    store = feedback.FeedbackStore()
    store.record("thumbs_up", "good ranking")
    assert store.audit.verify()["ok"] is True


# --- orchestrator -------------------------------------------------------------------

def test_orchestrator_fanout(conn):
    orch = Orchestrator(conn)
    out = orch.ask("Suggest substitutes for cane sugar for reduced sugar and show trial outcomes")
    tools = {t["tool"] for t in out["tools"]}
    assert {"text2sql", "substitute"} <= tools


def test_orchestrator_gated_action_blocked(conn):
    orch = Orchestrator(conn)
    out = orch.ask("please approve formula F-CLEAN-01")
    assert out["tier"] == "T4"
    assert out["decision"]["approved"] is False


def test_orchestrator_gated_action_approved(conn):
    orch = Orchestrator(conn)
    out = orch.ask("please approve formula F-CLEAN-01", approver=lambda d: True)
    assert out["decision"]["approved"] is True


def test_orchestrator_audits_turns(conn):
    orch = Orchestrator(conn)
    orch.ask("Which formulations are in trial?")
    assert orch.audit.verify()["ok"] is True


def test_orchestrator_price_gap(conn):
    orch = Orchestrator(conn, price_feed=pricesignal.LivePriceFeed())
    out = orch.ask("What is the price of date paste?")
    price_tools = [t for t in out["tools"] if t["tool"] == "price"]
    assert price_tools and "gap" in price_tools[0]


# --- demo helpers ---------------------------------------------------------------------

def test_demo_answer_question():
    out = answer_question("Which formulations are in trial?")
    assert out["sql"]["intent"] == "formulations_by_status"


def test_demo_substitution_showcase():
    opts = substitution_showcase()
    assert opts[0]["substitute"] == "date paste"


def test_demo_trial_showcase():
    t = trial_showcase()
    assert t["summary"]["form_id"] == "F-CLEAN-01"
    assert len(t["cycles"]) == 5


def test_demo_price_showcase():
    assert price_showcase()["usd_per_kg"] == pytest.approx(3.40)


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def test_review_default_substitution_question_returns_rows(conn):
    out = text2sql.answer(conn, "Suggest substitutes for cane sugar for reduced sugar")
    assert [r["substitute"] for r in out["rows"]] == ["date paste", "stevia leaf extract"]
    out = text2sql.answer(conn, "Suggest substitutes for whey protein isolate for dairy free")
    assert [r["substitute"] for r in out["rows"]] == ["pea protein isolate"]


@pytest.mark.parametrize("outcome,scores", [
    ("pass", (8, 8, 1, 0)),   # micro panel failed
    ("pass", (5, 8, 1, 1)),   # sensory below 6
    ("fail", (8, 8, 1, 1)),   # every criterion met
])
def test_review_trial_outcome_must_match_sop03(conn, outcome, scores):
    with pytest.raises(trials.TrialError, match="TRIAL-OUTCOME-01"):
        trials.record_trial(conn, "F-CLEAN-01", "B-999", outcome, *scores)


def test_review_consistent_trial_is_recorded(conn):
    tid = trials.record_trial(conn, "F-CLEAN-01", "B-999", "pass", 7, 7, 1, 1)
    assert conn.execute("SELECT outcome FROM trials WHERE trial_id = ?", (tid,)).fetchone()[0] == "pass"


def test_review_candidate_breaking_the_claim_is_rejected(conn):
    conn.execute("INSERT INTO substitutions VALUES ('SUB-90', 'palm shortening', "
                 "'mono-diglycerides', 'clean label', 0.95, -1.0, 'improves')")
    conn.execute("INSERT INTO substitutions VALUES ('SUB-91', 'pea protein isolate', "
                 "'whey protein isolate', 'dairy free', 0.95, -1.0, 'neutral')")
    clean = [o["substitute"] for o in substitute.rank_substitutes(conn, "palm shortening", "clean label")]
    assert clean == ["sunflower oil"]   # mono-diglycerides is not clean label
    assert substitute.rank_substitutes(conn, "pea protein isolate", "dairy free") == []  # whey is milk


def test_review_card_numbers_are_redacted():
    assert pii.scrub("card 4111-1111-1111-1111 lot 20261018") == ("card [CARD] lot 20261018", 1)
