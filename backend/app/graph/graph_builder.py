import logging

from langgraph.graph import StateGraph, END

from app.graph.state import ClaimState
from app.graph.nodes import (
    extraction_agent, completeness_gate, route_after_completeness,
    followup_agent, policy_checks_node, route_after_policy_checks,
    weather_agent, risk_language_agent, decision_node, adjudicator_agent,
)

logger = logging.getLogger("fnol.graph")


def build_graph():
    g = StateGraph(ClaimState)

    g.add_node("extract", extraction_agent)
    g.add_node("completeness_gate", completeness_gate)
    g.add_node("followup", followup_agent)
    g.add_node("policy_checks", policy_checks_node)
    g.add_node("weather_agent", weather_agent)
    g.add_node("risk_agent", risk_language_agent)
    g.add_node("decision_node", decision_node)
    g.add_node("adjudicator", adjudicator_agent)

    g.set_entry_point("extract")
    g.add_edge("extract", "completeness_gate")

    g.add_conditional_edges(
        "completeness_gate",
        route_after_completeness,
        {"incomplete": "followup", "complete": "policy_checks"},
    )
    g.add_edge("followup", END)

    g.add_conditional_edges(
        "policy_checks",
        route_after_policy_checks,
        {"no_policy": END, "ok": "weather_agent"},
    )

    g.add_edge("weather_agent", "risk_agent")
    g.add_edge("risk_agent", "decision_node")
    g.add_edge("decision_node", "adjudicator")
    g.add_edge("adjudicator", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("Graph compiled.")
    return _graph


def get_graph_mermaid() -> str:
    """Text mermaid source for the frontend to render (no image rendering
    dependency needed server-side)."""
    return get_graph().get_graph().draw_mermaid()
