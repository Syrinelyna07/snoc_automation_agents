"""Fulfilment graph agent."""

from __future__ import annotations

import uuid

from langgraph.runtime import Runtime

from snoc_agent.graph.context import GraphExecutionContext
from snoc_agent.graph.legacy_adapter import LegacyStageAdapter
from snoc_agent.graph.serialization import result_to_dict
from snoc_agent.graph.state import WorkflowState


def fulfilment_agent(
    state: WorkflowState, runtime: Runtime[GraphExecutionContext]
) -> WorkflowState:
    result = LegacyStageAdapter().fulfil(
        runtime.context,
        email_id=uuid.UUID(state["inbound_email_id"]),
        request_ids=[uuid.UUID(value) for value in state.get("request_ids", [])],
        execute_ids=[uuid.UUID(value) for value in state.get("execute_operation_ids", [])],
        decisions=list(state.get("decisions", [])),
    )
    return {
        "processing_status": result.status,
        "result": result_to_dict(result),
        "terminal": True,
        "completed_agents": [*state.get("completed_agents", []), "fulfilment"],
    }
