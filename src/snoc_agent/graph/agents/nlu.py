"""NLU graph agent using the existing audited analyzer and verifier."""

from __future__ import annotations

from langgraph.runtime import Runtime

from snoc_agent.graph.context import GraphExecutionContext
from snoc_agent.graph.legacy_adapter import LegacyStageAdapter
from snoc_agent.graph.serialization import result_to_dict
from snoc_agent.graph.state import WorkflowState


def nlu_agent(state: WorkflowState, runtime: Runtime[GraphExecutionContext]) -> WorkflowState:
    adapter = LegacyStageAdapter()
    work, request_ids, early = adapter.analyze(runtime.context)
    completed = [*state.get("completed_agents", []), "nlu"]
    if early is not None:
        return {
            "request_ids": [str(value) for value in request_ids],
            "processing_status": early.status,
            "result": result_to_dict(early),
            "terminal": True,
            "completed_agents": completed,
        }
    execute_ids, decisions = adapter.verify_and_decide(runtime.context)
    analysis = runtime.context.analysis
    return {
        "request_ids": [str(value) for value in request_ids],
        "operation_ids": [str(item.operation_id) for item in work],
        "analysis": analysis.model_dump(mode="json") if analysis else {},
        "execute_operation_ids": [str(value) for value in execute_ids],
        "decisions": decisions,
        "terminal": False,
        "completed_agents": completed,
    }
