"""Main orchestrator agent: a LangGraph StateGraph with an LLM router node
that classifies the dealer's question and dispatches to exactly one of the
five specialist agents in specialists.py, then returns its answer plus which
agent handled it (so the UI can show attribution).

Anything unrelated to fleet/rental management (e.g. "what is BFS") is routed
to a dedicated out_of_scope branch that answers directly, instead of being
force-fit into a specialist that would otherwise call a tool and hallucinate
an answer to a question its tools have nothing to do with.
"""
from typing import TypedDict, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from app.agents.llm import get_llm
from app.agents.specialists import SPECIALISTS

AgentKey = Literal[
    "fleet", "rental_scheduling", "demand_forecast", "smart_alert",
    "predictive_maintenance", "out_of_scope",
]

OUT_OF_SCOPE_LABEL = "Assistant"


class RouteDecision(BaseModel):
    agent: AgentKey = Field(
        description=(
            "Which specialist agent should handle this query. Use out_of_scope "
            "if the question has nothing to do with equipment rental, fleet "
            "management, alerts, forecasting, or maintenance."
        )
    )


class OrchestratorState(TypedDict):
    query: str
    route: Optional[str]
    response: Optional[str]


ROUTER_SYSTEM_PROMPT = (
    "You are the orchestrator for a heavy-equipment rental platform's AI assistant. "
    "Route the dealer's question to exactly one specialist agent based on what "
    "it's actually asking:\n"
    + "\n".join(f"- {key}: {meta['description']}" for key, meta in SPECIALISTS.items())
    + "\n- out_of_scope: the question is unrelated to this platform (equipment, "
    "rentals, alerts, forecasting, maintenance) — e.g. general trivia, coding "
    "questions, or anything else outside fleet/rental management."
)


def _route_node(state: OrchestratorState) -> OrchestratorState:
    router = get_llm(temperature=0).with_structured_output(RouteDecision)
    decision = router.invoke([
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": state["query"]},
    ])
    return {**state, "route": decision.agent}


def _dispatch(state: OrchestratorState) -> str:
    return state["route"]


def _make_specialist_node(key: str):
    def node(state: OrchestratorState) -> OrchestratorState:
        agent = SPECIALISTS[key]["agent"]
        result = agent.invoke({"messages": [{"role": "user", "content": state["query"]}]})
        final_message = result["messages"][-1]
        return {**state, "response": final_message.content}
    return node


def _out_of_scope_node(state: OrchestratorState) -> OrchestratorState:
    return {
        **state,
        "response": (
            "I'm the fleet assistant for this rental platform — I can only help with "
            "equipment status, rentals, alerts, demand forecasts, and maintenance. "
            "That question is outside what I can answer here."
        ),
    }


def _build_orchestrator():
    graph = StateGraph(OrchestratorState)
    graph.add_node("router", _route_node)
    for key in SPECIALISTS:
        graph.add_node(key, _make_specialist_node(key))
    graph.add_node("out_of_scope", _out_of_scope_node)

    graph.set_entry_point("router")
    routes = {key: key for key in SPECIALISTS}
    routes["out_of_scope"] = "out_of_scope"
    graph.add_conditional_edges("router", _dispatch, routes)
    for key in SPECIALISTS:
        graph.add_edge(key, END)
    graph.add_edge("out_of_scope", END)
    return graph.compile()


_orchestrator = _build_orchestrator()


def run_orchestrator(query: str) -> dict:
    result = _orchestrator.invoke({"query": query, "route": None, "response": None})
    route = result["route"]
    label = OUT_OF_SCOPE_LABEL if route == "out_of_scope" else SPECIALISTS[route]["label"]
    return {
        "response": result["response"],
        "agent_used": label,
        "agent_key": route,
    }
