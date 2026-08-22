"""
test_tools.py — Deterministic pytest suite for tools (no LLM calls).

Tests:
  1. Cross-account order access → PermissionError
  2. Cross-account ticket access → PermissionError
  3. get_order for own account → succeeds
  4. list_orders for own account → returns data
  5. search_docs never returns deprecated chunks
  6. Unknown query_type → returns error dict (no crash)
"""

import sqlite3
from unittest.mock import patch, MagicMock

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def temp_db(tmp_path):
    """Create a minimal in-memory-like SQLite DB for testing query_data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE orders (
            order_id TEXT, account_id TEXT, status TEXT, amount TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE tickets (
            ticket_id TEXT, account_id TEXT, subject TEXT, status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE accounts (
            account_id TEXT, name TEXT, plan TEXT
        )
    """)
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [
        ("ORD-001", "ACCT-NORTHSTAR", "delivered", "500.00"),
        ("ORD-002", "ACCT-LUMENWORKS", "pending", "200.00"),
    ])
    conn.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?)", [
        ("TKT-001", "ACCT-NORTHSTAR", "Late delivery", "open"),
        ("TKT-002", "ACCT-LUMENWORKS", "Failed pickup", "open"),
    ])
    conn.executemany("INSERT INTO accounts VALUES (?, ?, ?)", [
        ("ACCT-NORTHSTAR", "Northstar Logistics", "enterprise"),
        ("ACCT-LUMENWORKS", "LumenWorks", "standard"),
    ])
    conn.commit()
    conn.close()
    return db_path


# ── Tests: query_data ─────────────────────────────────────────────────────────

def test_get_order_own_account(temp_db):
    """Account can fetch its own order."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        result = qd_module.query_data("ACCT-NORTHSTAR", "get_order", {"order_id": "ORD-001"})
    assert result["count"] == 1
    assert result["data"][0]["order_id"] == "ORD-001"


def test_get_order_cross_account_blocked(temp_db):
    """Account CANNOT fetch another account's order — must raise PermissionError."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        with pytest.raises(PermissionError):
            qd_module.query_data("ACCT-NORTHSTAR", "get_order", {"order_id": "ORD-002"})


def test_get_ticket_own_account(temp_db):
    """Account can fetch its own ticket."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        result = qd_module.query_data("ACCT-LUMENWORKS", "get_ticket", {"ticket_id": "TKT-002"})
    assert result["count"] == 1
    assert result["data"][0]["ticket_id"] == "TKT-002"


def test_get_ticket_cross_account_blocked(temp_db):
    """Account CANNOT fetch another account's ticket — must raise PermissionError."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        with pytest.raises(PermissionError):
            qd_module.query_data("ACCT-LUMENWORKS", "get_ticket", {"ticket_id": "TKT-001"})


def test_list_orders_scoped(temp_db):
    """list_orders only returns the calling account's orders."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        result = qd_module.query_data("ACCT-NORTHSTAR", "list_orders")
    order_ids = [r["order_id"] for r in result["data"]]
    assert "ORD-001" in order_ids
    assert "ORD-002" not in order_ids   # belongs to LumenWorks


def test_list_tickets_scoped(temp_db):
    """list_tickets only returns the calling account's tickets."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        result = qd_module.query_data("ACCT-LUMENWORKS", "list_tickets")
    ticket_ids = [r["ticket_id"] for r in result["data"]]
    assert "TKT-002" in ticket_ids
    assert "TKT-001" not in ticket_ids


def test_unknown_query_type_returns_error(temp_db):
    """Unknown query_type returns an error dict, does not raise."""
    from agent.tools import query_data as qd_module
    with patch.object(qd_module, "DB_FILE", temp_db):
        result = qd_module.query_data("ACCT-NORTHSTAR", "delete_everything")
    assert "error" in result


# ── Tests: search_docs ────────────────────────────────────────────────────────

def test_search_docs_no_deprecated_chunks():
    """search_docs must never return chunks flagged is_deprecated=True."""
    from agent.tools import search_docs as sd_module

    # Mock the loaded chunks with a mix of deprecated and non-deprecated
    mock_chunks = [
        {"chunk_id": "good::chunk_0", "source_file": "01_Support_Policy_v3_CURRENT.pdf",
         "page": 1, "text": "P1 response time is 1 hour", "is_deprecated": False},
        {"chunk_id": "bad::chunk_0", "source_file": "02_Support_Policy_v2_DEPRECATED.pdf",
         "page": 1, "text": "P1 response time is 4 hours (old)", "is_deprecated": True},
    ]
    chunk_map = {c["chunk_id"]: c for c in mock_chunks}
    good_ids = {"good::chunk_0"}
    bad_ids = {"bad::chunk_0"}

    with (
        patch.object(sd_module, "_chunks", mock_chunks),
        patch.object(sd_module, "_chunk_map", chunk_map),
        patch.object(sd_module, "_faiss_index", MagicMock(**{"search.return_value": (None, [[0, 1]])})),
        patch.object(sd_module, "_faiss_ids", ["good::chunk_0", "bad::chunk_0"]),
        patch.object(sd_module, "_bm25", MagicMock(**{"get_scores.return_value": [1.0, 0.9]})),
        patch.object(sd_module, "_bm25_ids", ["good::chunk_0", "bad::chunk_0"]),
        patch.object(sd_module, "_embed_model", MagicMock(**{"encode.return_value": [[0.1] * 384]})),
    ):
        import numpy as np
        sd_module._embed_model.encode.return_value = np.array([[0.1] * 384])
        results = sd_module.search_docs("P1 response time", "ACCT-NORTHSTAR")

    deprecated_returned = any(r.get("is_deprecated") for r in results)
    assert not deprecated_returned, "search_docs returned deprecated chunks!"


# ── Tests: propose_action / execute_action ────────────────────────────────────

def test_propose_action_does_not_execute():
    """propose_action must return a ProposedAction with executed=False."""
    from agent.tools.actions import propose_action
    action = propose_action(
        action_type="escalate_ticket",
        payload={"ticket_id": "TKT-001", "reason": "test"},
        description="Escalate TKT-001 to a human agent.",
    )
    assert action.executed is False
    assert action.action_id is not None


def test_execute_action_after_confirm():
    """execute_action marks the action as executed and returns success."""
    from agent.tools.actions import propose_action, execute_action, _pending_actions
    action = propose_action(
        action_type="escalate_ticket",
        payload={"ticket_id": "TKT-999", "reason": "unit test"},
        description="Escalate TKT-999",
    )
    result = execute_action(action.action_id)
    assert result["success"] is True
    assert _pending_actions[action.action_id]["executed"] is True


def test_execute_action_twice_fails():
    """Executing the same action twice should return an error."""
    from agent.tools.actions import propose_action, execute_action
    action = propose_action(
        action_type="escalate_ticket",
        payload={"ticket_id": "TKT-DUPE", "reason": "duplicate test"},
        description="Escalate TKT-DUPE",
    )
    execute_action(action.action_id)
    result2 = execute_action(action.action_id)
    assert "error" in result2
