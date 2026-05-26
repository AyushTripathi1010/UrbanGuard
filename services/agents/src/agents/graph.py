"""LangGraph wiring: triage → route → notify → memory.

We use a plain `StateGraph` with no conditional edges yet. The decision logic
about whether to dispatch lives inside the nodes themselves so this file stays
declarative.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from agents.nodes.memory import memory_node
from agents.nodes.notify import notify_node
from agents.nodes.route import route_node
from agents.nodes.triage import triage_node
from agents.state import IncidentState

log = structlog.get_logger("agents.graph")


def build_graph():
    g = StateGraph(IncidentState)
    g.add_node("triage", triage_node)
    g.add_node("route", route_node)
    g.add_node("notify", notify_node)
    g.add_node("memory", memory_node)
    g.add_edge(START, "triage")
    g.add_edge("triage", "route")
    g.add_edge("route", "notify")
    g.add_edge("notify", "memory")
    g.add_edge("memory", END)
    return g.compile()
