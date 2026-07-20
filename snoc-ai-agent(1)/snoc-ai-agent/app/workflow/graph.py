"""Five-component operational workflow.

Ingress -> Security -> NLU -> Policy -> Fulfilment -> Audit/Event Store
                 -> Fulfilment (rejected request)

Learning is queued by the audit component and processed outside this request
path.  The former 11-agent decomposition remains available in ``app.agents``
as implementation helpers, not as orchestration boundaries.
"""
from langgraph.graph import StateGraph, END

from app.models import WorkflowState
from app.workflow import components


def _route_after_security(state: WorkflowState) -> str:
    return "fulfilment" if state.get("rejected") else "nlu"


def build_graph():
    graph = StateGraph(WorkflowState)
    graph.add_node("ingress", lambda state: components.ingress(state))
    graph.add_node("security", components.security)
    graph.add_node("nlu", components.nlu)
    graph.add_node("policy", components.policy)
    graph.add_node("fulfilment", components.fulfilment)
    graph.add_node("audit", components.audit_and_enqueue_learning)

    graph.set_entry_point("ingress")
    graph.add_edge("ingress", "security")
    graph.add_conditional_edges("security", _route_after_security, {"nlu": "nlu", "fulfilment": "fulfilment"})
    graph.add_edge("nlu", "policy")
    graph.add_edge("policy", "fulfilment")
    graph.add_edge("fulfilment", "audit")
    graph.add_edge("audit", END)
    return graph.compile()


def process_email(email: dict) -> WorkflowState:
    """Run one inbound message through the synchronous operational path."""
    return build_graph().invoke(email)
