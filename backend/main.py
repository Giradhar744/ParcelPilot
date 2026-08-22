"""
main.py — FastAPI application for the ParcelPilot AI Support Agent.

Routes:
  POST /chat     → run agent, return answer + tools_used + proposed_action
  POST /confirm  → execute a previously proposed (confirm-gated) action
  GET  /health   → liveness check
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.graph import run_agent
from agent.tools.actions import execute_action

app = FastAPI(
    title="ParcelPilot AI Support Agent",
    description="LangGraph-powered customer support agent with policy-precedence reasoning.",
    version="1.0.0",
)

# Allow the Vite dev server (and any local origin) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    account_id: str = Field(..., description="The authenticated caller's account ID")
    message: str = Field(..., description="The user's support question")
    history: list[dict] = Field(
        default_factory=list,
        description="Prior conversation turns: [{role, content}, ...]",
    )


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]
    proposed_action: dict | None = None
    sources: list[str] | None = None


class ConfirmRequest(BaseModel):
    action_id: str = Field(..., description="The action_id from a previous proposed_action")


class ConfirmResponse(BaseModel):
    success: bool
    result: dict


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Run the agent for one turn.

    - account_id is forwarded to every tool call for access enforcement.
    - history allows multi-turn conversations (pass prior turns from the frontend).
    """
    if not req.account_id.strip():
        raise HTTPException(status_code=400, detail="account_id is required")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    result = run_agent(
        account_id=req.account_id,
        message=req.message,
        history=req.history,
    )
    return ChatResponse(**result)


@app.post("/confirm", response_model=ConfirmResponse)
def confirm(req: ConfirmRequest):
    """
    Execute a proposed action after the user clicks Confirm in the frontend.
    """
    result = execute_action(req.action_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return ConfirmResponse(success=True, result=result)


@app.get("/internal/tickets")
def get_internal_tickets():
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent / "data" / "parcelpilot.db"
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Fetch active tickets (OPEN or ESCALATED), join with accounts to get user names, priorities, and issues
        rows = conn.execute("""
            SELECT t.ticket_id, t.created_at, t.status, t.subject, t.description, t.priority, t.deadline_at, a.account_name
            FROM tickets t
            LEFT JOIN accounts a ON t.account_id = a.account_id
            WHERE t.status IN ('OPEN', 'ESCALATED')
            ORDER BY t.priority ASC, t.deadline_at ASC
        """).fetchall()
        tickets = [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"tickets": tickets}
