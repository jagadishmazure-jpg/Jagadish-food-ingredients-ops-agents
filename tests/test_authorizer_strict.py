"""Strict, view-aware authorizer (SEC-SELECT-03), tested independently of the text check.

A base-table READ is allowed only when SQLite reports it on behalf of an
allowed view (the authorizer's view-name argument). A READ naming the table
directly, with no view, is denied; sqlite_master is always denied.
"""

import sqlite3

import pytest

from fooding import views
from fooding.authz import views_only

ALLOWED = list(views._VIEWS)

DIRECT_READS = [
    "SELECT * FROM ingredients, v_cost_impact",
    "SELECT * FROM/**/\"ingredients\"/**/,/**/v_cost_impact",
    "SELECT * FROM v_cost_impact JOIN (ingredients) ON 1 = 1",
    "SELECT * FROM v_cost_impact WHERE EXISTS (SELECT 1 FROM main.[ingredients] WHERE ingredients.rowid > 0)",
    "SELECT cost_per_kg FROM ingredients",
    "SELECT * FROM\"ingredients\"\t,\nv_cost_impact",
]
GATEWAY_READS = DIRECT_READS


@pytest.fixture()
def conn():
    from fooding import demo_helpers as dh
    return dh.demo_db()


@pytest.mark.parametrize("sql", DIRECT_READS)
def test_authorizer_denies_direct_base_table_reads(conn, sql):
    with views_only(conn, ALLOWED) as denied:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(sql).fetchall()
    assert "ingredients" in [d.lower() for d in denied]


@pytest.mark.parametrize("sql", GATEWAY_READS)
def test_gateway_denies_direct_reads_with_text_check_disabled(conn, monkeypatch, sql):
    monkeypatch.setattr(views, "_referenced_tables", lambda sql: set())
    with pytest.raises(views.GatewayError, match="SEC-SELECT-03"):
        views.run_query(conn, sql)


def test_sqlite_master_is_denied_even_if_listed_as_allowed(conn):
    with views_only(conn, ALLOWED + ["sqlite_master"]):
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute('SELECT name FROM "sqlite_master"').fetchall()


def test_load_extension_is_denied(conn):
    with views_only(conn, ALLOWED):
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("SELECT load_extension('x') FROM v_cost_impact").fetchall()


@pytest.mark.parametrize("view", ALLOWED)
def test_every_published_view_is_readable(conn, view):
    with views_only(conn, ALLOWED) as denied:
        conn.execute(f"SELECT * FROM {view}").fetchall()
    assert denied == []


def test_view_self_join_is_not_falsely_denied(conn):
    with views_only(conn, ALLOWED) as denied:
        conn.execute("SELECT count(*) FROM v_cost_impact a JOIN v_cost_impact b ON 1 = 1").fetchall()
    assert denied == []


def test_base_column_filter_is_denied_even_in_count(conn):
    # Documented residual: count(*) of a table behind a view reads no column.
    # Any column access (here a WHERE filter) is still denied.
    with views_only(conn, ALLOWED):
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("SELECT count(*) FROM ingredients WHERE cost_per_kg > 0").fetchall()


# Queries that got past the text check before 2026-10-18 and read the raw table.
@pytest.mark.parametrize("sql", ['SELECT * FROM "ingredients"', 'SELECT * FROM (ingredients)', 'SELECT * FROM (v_cost_impact), ingredients', 'SELECT * FROM v_cost_impact,(ingredients)'])
def test_former_text_bypasses_are_denied(conn, sql):
    with pytest.raises(views.GatewayError, match="SEC-SELECT-03"):
        views.run_query(conn, sql)
