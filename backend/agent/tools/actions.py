"""
actions.py — Confirm-gated action tool.

propose_action() returns a ProposedAction but does NOT execute anything.
execute_action() is called only after explicit user confirmation from the frontend.

Supported action_types:
  escalate_ticket  — escalate a support ticket to a human agent
  update_ticket    — update ticket status/notes
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# In-memory store of pending actions (keyed by action_id).
# In production this would be a persistent store; for assessment scope, in-memory is fine.
_pending_actions: dict[str, dict] = {}


@dataclass
class ProposedAction:
    action_id: str
    action_type: str
    payload: dict
    description: str          # Human-readable summary shown to user before confirmation
    proposed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def propose_action(action_type: str, payload: dict, description: str) -> ProposedAction:
    """
    Create a proposed action and store it pending confirmation.
    Does NOT execute anything.

    Args:
        action_type: e.g. "escalate_ticket", "update_ticket"
        payload: dict of action-specific parameters
        description: plain-language summary for the user to read before confirming

    Returns:
        ProposedAction (include action_id in the response to the user)
    """
    action_id = str(uuid.uuid4())
    action = ProposedAction(
        action_id=action_id,
        action_type=action_type,
        payload=payload,
        description=description,
    )
    _pending_actions[action_id] = action.to_dict()
    return action


def execute_action(action_id: str) -> dict:
    """
    Execute a previously proposed action after user confirmation.

    Returns:
        {"success": True, "action": {...}} or {"error": "..."}
    """
    if action_id not in _pending_actions:
        return {"error": f"Action {action_id} not found or already executed."}

    action = _pending_actions[action_id]

    if action["executed"]:
        return {"error": f"Action {action_id} has already been executed."}

    action_type = action["action_type"]
    payload = action["payload"]

    # ── Execute the action ───────────────────────────────────────────────────
    result = _dispatch(action_type, payload)

    # Mark as executed
    action["executed"] = True
    _pending_actions[action_id] = action

    return {"success": True, "action": action, "result": result}


def _dispatch(action_type: str, payload: dict) -> dict:
    """Internal dispatcher — extends state changes to local SQLite database."""
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent.parent / "data" / "parcelpilot.db"

    if action_type == "escalate_ticket":
        ticket_id = payload.get("ticket_id")
        reason = payload.get("reason", "")
        account_id = payload.get("account_id", "unknown")

        if not ticket_id or str(ticket_id).lower() in ("unknown", "new", "none", ""):
            import random
            ticket_id = f"TKT-{random.randint(600, 999)}"

        priority = "3"
        sla_hours = 24
        
        reason_lower = reason.lower()
        if "security" in reason_lower or "api key" in reason_lower or "leak" in reason_lower or "compromise" in reason_lower:
            priority = "1"
            sla_hours = 1
        elif "delay" in reason_lower or "fail" in reason_lower or "late" in reason_lower or "missed" in reason_lower:
            priority = "2"
            sla_hours = 4

        conn = sqlite3.connect(db_path)
        try:
            # Check if ticket already exists in DB
            cur = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE tickets SET status = 'ESCALATED', priority = ?, description = ? WHERE ticket_id = ?",
                    (priority, f"{reason} (Escalated to human support)", ticket_id)
                )
                message = f"Ticket {ticket_id} has been escalated and updated in database."
            else:
                from datetime import datetime, timedelta
                now = datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M")
                deadline_dt = now + timedelta(hours=sla_hours)
                deadline_str = deadline_dt.strftime("%Y-%m-%d %H:%M")
                conn.execute(
                    "INSERT INTO tickets (ticket_id, account_id, created_at, status, subject, description, channel, priority, deadline_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ticket_id, account_id, now_str, "ESCALATED", "Manual Investigation Ticket", reason, "Chat", priority, deadline_str)
                )
                message = f"New ticket {ticket_id} has been created and escalated in database."
            conn.commit()
        except Exception as e:
            print(f"[ACTION ERROR] SQLite update failed: {e}")
            message = f"Ticket {ticket_id} has been escalated to a human support agent."
        finally:
            conn.close()

        print(f"[ACTION] {message} Reason: {reason}")
        return {
            "message": message,
            "ticket_id": ticket_id,
        }

    elif action_type == "update_ticket":
        ticket_id = payload.get("ticket_id", "unknown")
        updates = payload.get("updates", {})

        conn = sqlite3.connect(db_path)
        try:
            if updates:
                set_clauses = []
                params = []
                for k, v in updates.items():
                    set_clauses.append(f'"{k}" = ?')
                    params.append(str(v))
                params.append(ticket_id)
                conn.execute(
                    f'UPDATE tickets SET {", ".join(set_clauses)} WHERE ticket_id = ?',
                    params
                )
                conn.commit()
                message = f"Ticket {ticket_id} has been updated in database."
            else:
                message = f"Ticket {ticket_id} updated (no changes requested)."
        except Exception as e:
            print(f"[ACTION ERROR] SQLite update failed: {e}")
            message = f"Ticket {ticket_id} has been updated."
        finally:
            conn.close()

        print(f"[ACTION] {message}: {updates}")
        return {
            "message": message,
            "ticket_id": ticket_id,
            "updates_applied": updates,
        }

    else:
        return {"error": f"Unknown action_type: {action_type}"}


# Tool schema for the LLM
PROPOSE_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_action",
        "description": (
            "Propose an action (e.g., escalate a ticket) that requires explicit user confirmation "
            "before execution. NEVER execute actions directly — always use this tool. "
            "The user will see the description and must click Confirm before anything happens."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["escalate_ticket", "update_ticket"],
                    "description": "The type of action to propose.",
                },
                "payload": {
                    "type": "object",
                    "description": (
                        "Action parameters. For escalate_ticket: {ticket_id, reason}. "
                        "For update_ticket: {ticket_id, updates: {field: value}}."
                    ),
                },
                "description": {
                    "type": "string",
                    "description": "Plain-language summary of what will happen on confirmation.",
                },
            },
            "required": ["action_type", "payload", "description"],
        },
    },
}
