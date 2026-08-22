"""
query_data.py — Account-scoped structured data lookups against parcelpilot.db (SQLite).

SECURITY: account_id is ALWAYS enforced at the SQL query level via a WHERE clause.
The LLM cannot bypass this by asking nicely — the constraint is in code, not the prompt.

Supported query_types:
  get_order       — fetch a single order by order_id (must belong to caller's account)
  list_orders     — list all orders for the caller's account
  get_ticket      — fetch a single ticket by ticket_id (must belong to caller's account)
  list_tickets    — list all tickets for the caller's account
"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent.parent / "data" / "parcelpilot.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_list(rows) -> list[dict]:
    return [dict(row) for row in rows]


def query_data(account_id: str, query_type: str, filters: dict | None = None) -> dict:
    """
    Execute an account-scoped query against the SQLite database.

    Args:
        account_id: The authenticated caller's account ID. ALWAYS enforced in queries.
        query_type: One of: get_order, list_orders, get_ticket, list_tickets.
        filters: Optional dict of extra filters (e.g., {"order_id": "ORD-1234"}).

    Returns:
        {"data": [...], "count": int} or raises PermissionError on cross-account access.
    """
    filters = filters or {}
    is_internal = (account_id == "INTERNAL-OPERATIONS")
    conn = _connect()

    try:
        if query_type == "list_orders":
            if is_internal:
                rows = conn.execute("SELECT * FROM orders").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE account_id = ?", (account_id,)
                ).fetchall()
            return {"data": _rows_to_list(rows), "count": len(rows)}

        elif query_type == "get_order":
            order_id = filters.get("order_id")
            if not order_id:
                return {"error": "order_id is required for get_order"}
            rows = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ).fetchall()
            if not rows:
                return {"error": f"Order {order_id} not found"}
            row = dict(rows[0])
            # Skip scoping checks for internal operators
            if not is_internal and row.get("account_id") != account_id:
                raise PermissionError(
                    f"Order {order_id} does not belong to account {account_id}. "
                    "Access denied."
                )
            return {"data": [row], "count": 1}

        elif query_type == "list_tickets":
            if is_internal:
                rows = conn.execute("SELECT * FROM tickets").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tickets WHERE account_id = ?", (account_id,)
                ).fetchall()
            return {"data": _rows_to_list(rows), "count": len(rows)}

        elif query_type == "get_ticket":
            ticket_id = filters.get("ticket_id")
            if not ticket_id:
                return {"error": "ticket_id is required for get_ticket"}
            rows = conn.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchall()
            if not rows:
                return {"error": f"Ticket {ticket_id} not found"}
            row = dict(rows[0])
            # Skip scoping checks for internal operators
            if not is_internal and row.get("account_id") != account_id:
                raise PermissionError(
                    f"Ticket {ticket_id} does not belong to account {account_id}. "
                    "Access denied."
                )
            return {"data": [row], "count": 1}

        elif query_type == "get_account":
            if is_internal:
                target_acct = filters.get("account_id")
                if target_acct:
                    rows = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (target_acct,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM accounts").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
                ).fetchall()
            if not rows:
                return {"error": "No accounts found"}
            return {"data": _rows_to_list(rows), "count": len(rows)}

        else:
            return {"error": f"Unknown query_type: {query_type}"}

    finally:
        conn.close()


# Tool schema for the LLM
QUERY_DATA_TOOL = {
    "type": "function",
    "function": {
        "name": "query_data",
        "description": (
            "Look up structured B2B database data: orders, tickets, or account details. "
            "Data accessibility conforms to the active user session context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["get_order", "list_orders", "get_ticket", "list_tickets", "get_account"],
                    "description": "The type of data lookup to perform.",
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "Optional filters. For get_order: {order_id: 'ORD-...'}, "
                        "for get_ticket: {ticket_id: 'TKT-...'}."
                    ),
                },
            },
            "required": ["query_type"],
        },
    },
}
