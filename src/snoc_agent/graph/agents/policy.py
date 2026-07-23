"""Deterministic fail-closed policy routing agent."""

from __future__ import annotations

import uuid

from langgraph.runtime import Runtime

from snoc_agent.graph.context import GraphExecutionContext
from snoc_agent.graph.legacy_adapter import LegacyStageAdapter
from snoc_agent.graph.state import WorkflowState


def policy_agent(state: WorkflowState, runtime: Runtime[GraphExecutionContext]) -> WorkflowState:
    operation_ids = [uuid.UUID(value) for value in state.get("operation_ids", [])]
    execute_ids = [uuid.UUID(value) for value in state.get("execute_operation_ids", [])]
    LegacyStageAdapter().assert_policy_outputs(runtime.context, operation_ids, execute_ids)
    return {
        "completed_agents": [*state.get("completed_agents", []), "policy"],
        "terminal": False,
    }
