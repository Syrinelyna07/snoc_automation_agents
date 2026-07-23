"""Security and correlation graph agent."""

from __future__ import annotations

import uuid

from langgraph.runtime import Runtime

from snoc_agent.graph.context import GraphExecutionContext
from snoc_agent.graph.legacy_adapter import LegacyStageAdapter
from snoc_agent.graph.serialization import result_to_dict
from snoc_agent.graph.state import WorkflowState


def security_agent(state: WorkflowState, runtime: Runtime[GraphExecutionContext]) -> WorkflowState:
    email_id = uuid.UUID(state["inbound_email_id"])
    result = LegacyStageAdapter().security(runtime.context, email_id)
    completed = [*state.get("completed_agents", []), "security"]
    if result is not None:
        return {
            "processing_status": result.status,
            "conversation_id": (str(result.conversation_id) if result.conversation_id else None),
            "result": result_to_dict(result),
            "terminal": True,
            "completed_agents": completed,
        }
    prepared = runtime.context.prepared
    assert prepared is not None
    return {
        "conversation_id": str(prepared.conversation_id),
        "authorization": {"allowed": True},
        "correlation": {
            "strength": prepared.correlation.strength.value,
            "matched_by": prepared.correlation.matched_by,
            "request_id": prepared.correlation.request_id,
            "clarification_id": prepared.correlation.clarification_id,
            "conflicts": list(prepared.correlation.conflicts),
        },
        "terminal": False,
        "completed_agents": completed,
    }
