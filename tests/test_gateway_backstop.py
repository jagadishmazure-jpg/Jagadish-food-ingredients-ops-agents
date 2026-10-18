"""Regression tests for the SQLite authorizer backstop (ADR-0001).

A sibling repo proved the gateway's text-only checks could be bypassed:
a ``LIMIT 100000 -- x`` comment smuggled 36,864 rows past a LIMIT-rewriting
cap. These tests pin the fix: every bypass below must be denied (or capped),
and legitimate view queries must keep working.
"""


import pytest

from fooding.pii import scrub
from fooding.telemetry import build_db
from fooding.views import ROW_CAP, GatewayError, create_views, run_query


@pytest.fixture()
def conn():
    c = build_db()
    create_views(c)
    return c


def denied(sql, conn):
    with pytest.raises(GatewayError) as e:
        run_query(conn, sql)
    assert "SEC-SELECT-03" in str(e.value)


# --- bypass attempts: each must be denied ---------------------------------

def test_comma_join_with_raw_table_denied(conn):
    denied("SELECT * FROM v_formulations, trials", conn)


def test_quoted_sqlite_master_denied(conn):
    denied('SELECT * FROM "sqlite_master"', conn)


def test_comment_whitespace_from_denied(conn):
    denied("SELECT/**/*/**/FROM/**/trials", conn)


def test_limit_comment_bypass_capped(conn):
    # The sibling-repo bug: LIMIT 100000 -- x returned 36,864 rows.
    # fetchmany() caps at ROW_CAP regardless of the query's LIMIT.
    _, rows = run_query(conn, "SELECT * FROM v_trial_outcomes LIMIT 100000 -- x")
    assert len(rows) <= ROW_CAP


def test_limit_offset_accepted_but_capped(conn):
    _, rows = run_query(conn, "SELECT * FROM v_trial_outcomes LIMIT 10 OFFSET 5")
    assert len(rows) <= ROW_CAP


def test_raw_base_table_denied(conn):
    denied("SELECT * FROM trials", conn)


def test_raw_base_table_in_subquery_denied(conn):
    denied("SELECT * FROM v_formulations WHERE form_id IN (SELECT form_id FROM trials)",
           conn)


# --- legitimate queries must keep working ----------------------------------

def test_legit_view_query_ok(conn):
    _, rows = run_query(conn, "SELECT * FROM v_formulations")
    assert len(rows) > 0


def test_legit_view_join_ok(conn):
    _, rows = run_query(
        conn,
        "SELECT * FROM v_formulations "
        "JOIN v_trial_outcomes ON v_formulations.form_id = v_trial_outcomes.form_id",
    )
    assert len(rows) > 0


def test_authorizer_restored_after_query(conn):
    # The views_only context manager must not leak the authorizer:
    # a direct (non-gateway) read still works afterwards.
    run_query(conn, "SELECT * FROM v_formulations")
    assert conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0] > 0


# --- PII phone formats -------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "(555) 123-4567",
    "+1 (555) 123-4567",
    "555.123.4567",
    "555-123-4567",
    "call me at (555) 123-4567 tomorrow",
])
def test_phone_formats_redacted(raw):
    text, n = scrub(raw)
    assert "[PHONE]" in text
    assert n >= 1
    assert "555" not in text


def test_ssn_redacted():
    text, n = scrub("ssn 123-45-6789 here")
    assert text == "ssn [SSN] here"
    assert n == 1


@pytest.mark.parametrize("raw", ["2026-10-18", "trial on 2026-10-18 passed"])
def test_dates_not_redacted(raw):
    text, n = scrub(raw)
    assert text == raw
    assert n == 0
