"""
graph.py — LangGraph agent definition for ParcelPilot support.

Nodes:
  agent          -> calls LLM via LangChain BaseChatModel, decides tool(s) or final answer
  tool_executor  -> dispatches to the correct tool function
  end            -> assembles the structured response

The confirm-gate is NOT a graph node — actions are proposed inside tool_executor
and the frontend holds execution until the user confirms (via /confirm endpoint).

Message format in state:
  Plain dicts {role, content, tool_calls?, tool_call_id?, name?}
  Converted to LangChain message objects before each LLM call.
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph

from agent.llm import call_llm_with_fallback
from agent.prompts import SYSTEM_PROMPT
from agent.tools.actions import PROPOSE_ACTION_TOOL, propose_action
from agent.tools.query_data import QUERY_DATA_TOOL, query_data
from agent.tools.search_docs import SEARCH_DOCS_TOOL, search_docs

ALL_TOOLS = [SEARCH_DOCS_TOOL, QUERY_DATA_TOOL, PROPOSE_ACTION_TOOL]

# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    account_id: str
    messages: Annotated[list[dict], operator.add]   # plain dicts, serialisation-friendly
    tools_used: Annotated[list[str], operator.add]
    proposed_action: dict | None


# ── Message conversion helpers ────────────────────────────────────────────────

def _to_lc_messages(messages: list[dict]) -> list[BaseMessage]:
    """Convert state plain-dict messages to LangChain message objects."""
    lc = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "") or ""

        if role == "system":
            lc.append(SystemMessage(content=content))
        elif role == "user":
            lc.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = m.get("tool_calls")
            if tool_calls:
                # Reconstruct AIMessage with tool_calls (LangChain format)
                lc.append(AIMessage(content=content, tool_calls=tool_calls))
            else:
                lc.append(AIMessage(content=content))
        elif role == "tool":
            lc.append(ToolMessage(
                content=content,
                tool_call_id=m.get("tool_call_id", ""),
                name=m.get("name", ""),
            ))
    return lc


def _ai_msg_to_dict(msg: AIMessage) -> dict:
    """Convert a LangChain AIMessage to a plain dict for state storage."""
    d: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        # LangChain tool_calls: [{id, name, args (dict)}]
        d["tool_calls"] = [
            {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
            for tc in msg.tool_calls
        ]
    return d


# ── Nodes ─────────────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> AgentState:
    """Call the LLM. May return a final answer or request tool calls."""
    # Inject active session context to the system prompt dynamically
    active_id = state.get("account_id", "unknown")
    active_ctx = f"\n\nCURRENT SESSION CONTEXT:\n- Authenticated User: {active_id}\n"
    if active_id == "INTERNAL-OPERATIONS":
        active_ctx += (
            "- Role: Internal Operations Staff / Support Auditor. YOU HAVE UNRESTRICTED ALL-ACCESS CLEARANCE. "
            "You are authorized to query and search across ALL B2B customer accounts, tickets, orders, and contracts. "
            "Skip scoping constraints. Answer operational audit requests using all available records."
        )
    else:
        active_ctx += (
            f"- Role: Customer Representative for {active_id}. You must STRICTLY enforce data privacy. "
            "NEVER search, retrieve, or discuss orders, tickets, or agreements belonging to other accounts."
        )

    system_content = SYSTEM_PROMPT + active_ctx
    system = [{"role": "system", "content": system_content}]
    lc_messages = _to_lc_messages(system + state["messages"])

    try:
        ai_msg = call_llm_with_fallback(lc_messages, tools=ALL_TOOLS)
    except RuntimeError:
        # All providers failed — graceful degradation
        fallback = {
            "role": "assistant",
            "content": (
                "I'm currently unable to reach the AI service. "
                "I've escalated this to a human support agent who will follow up shortly."
            ),
        }
        return {"messages": [fallback], "tools_used": [], "proposed_action": None}

    return {
        "messages": [_ai_msg_to_dict(ai_msg)],
    }


def tool_executor_node(state: AgentState) -> AgentState:
    """Execute all tool calls requested by the LLM in the last assistant message."""
    last_msg = state["messages"][-1]
    tool_calls = last_msg.get("tool_calls", [])

    tool_results = []
    tools_used = []
    proposed_action = None

    for tc in tool_calls:
        # LangChain format: {id, name, args (dict — already parsed)}
        name = tc["name"]
        args = tc["args"]   # already a dict, no json.loads needed
        tc_id = tc["id"]

        tools_used.append(name)

        try:
            if name == "search_docs":
                chunks = search_docs(args.get("query", ""), account_id=state["account_id"])
                result = "\n\n---\n\n".join(
                    f"[{c['source_file']} p.{c['page']}]\n{c['text']}"
                    for c in chunks
                ) or "No relevant documents found."

            elif name == "query_data":
                result_obj = query_data(
                    account_id=state["account_id"],
                    query_type=args.get("query_type", ""),
                    filters=args.get("filters"),
                )
                result = json.dumps(result_obj)

            elif name == "propose_action":
                payload = args.get("payload", {})
                if isinstance(payload, dict) and "account_id" not in payload:
                    payload["account_id"] = state["account_id"]
                action = propose_action(
                    action_type=args.get("action_type", ""),
                    payload=payload,
                    description=args.get("description", ""),
                )
                proposed_action = action.to_dict()
                result = json.dumps({
                    "proposed": True,
                    "action_id": action.action_id,
                    "description": action.description,
                    "note": "Action is PENDING — user must confirm before execution.",
                })

            else:
                result = f"Unknown tool: {name}"

        except PermissionError as exc:
            result = f"ACCESS DENIED: {exc}"
        except Exception as exc:
            result = f"Tool error: {exc}"

        tool_results.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": name,
            "content": result,
        })

    return {
        "messages": tool_results,
        "tools_used": tools_used,
        "proposed_action": proposed_action,
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """Route: tool_calls present -> execute them; else -> end."""
    last_msg = state["messages"][-1]
    if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
        return "tool_executor"
    return END


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {
        "tool_executor": "tool_executor",
        END: END,
    })
    graph.add_edge("tool_executor", "agent")
    return graph.compile()


# Singleton — compiled once at import time
compiled_graph = build_graph()


def run_agent(account_id: str, message: str, history: list[dict] | None = None) -> dict:
    """
    Entry point called by FastAPI routes.

    Args:
        account_id: authenticated caller's account ID
        message:    the user's current message
        history:    prior conversation turns [{role, content}, ...]

    Returns:
        {"answer": str, "tools_used": [str], "proposed_action": dict | None}
    """
    history = history or []
    initial_state: AgentState = {
        "account_id": account_id,
        "messages": history + [{"role": "user", "content": message}],
        "tools_used": [],
        "proposed_action": None,
    }

    final_state = compiled_graph.invoke(initial_state)

    # Last assistant message with content is the answer
    answer = ""
    for msg in reversed(final_state["messages"]):
        if msg.get("role") == "assistant" and msg.get("content"):
            answer = msg["content"]
            break

    # Extract unique PDF source document names from tool results
    import re
    sources = set()
    for msg in final_state.get("messages", []):
        if msg.get("role") == "tool" and msg.get("name") == "search_docs":
            content = msg.get("content", "")
            # Match bracketed source tag format: [01_Support_Policy_v3_CURRENT.pdf p.2]
            matches = re.findall(r"\[([A-Za-z0-9_]+\.pdf) p\.\d+\]", content)
            for m in matches:
                sources.add(m)

    return {
        "answer": answer,
        "tools_used": list(set(final_state.get("tools_used", []))),
        "proposed_action": final_state.get("proposed_action"),
        "sources": sorted(list(sources)),
    }
