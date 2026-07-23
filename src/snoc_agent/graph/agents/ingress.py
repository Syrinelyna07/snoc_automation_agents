"""Ingress graph agent."""

from __future__ import annotations

from langgraph.runtime import Runtime

from snoc_agent.graph.context import GraphExecutionContext
from snoc_agent.graph.legacy_adapter import LegacyStageAdapter
from snoc_agent.graph.serialization import result_to_dict
from snoc_agent.graph.state import WorkflowState


def ingress_agent(state: WorkflowState, runtime: Runtime[GraphExecutionContext]) -> WorkflowState:
    result = LegacyStageAdapter().ingress(runtime.context)
    completed = [*state.get("completed_agents", []), "ingress"]
    if result is not None:
        return {
            "inbound_email_id": str(result.email_message_id),
            "processing_status": result.status,
            "result": result_to_dict(result),
            "terminal": True,
            "completed_agents": completed,
        }
    if runtime.context.email_id is None:
        raise RuntimeError("ingress completed without a persisted email ID")
    return {
        "inbound_email_id": str(runtime.context.email_id),
        "terminal": False,
        "completed_agents": completed,
    }
