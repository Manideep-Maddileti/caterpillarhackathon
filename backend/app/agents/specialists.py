"""The five specialist agents. Each is a LangGraph ReAct agent (create_react_agent)
bound to its own subset of tools from tools.py and a role-specific system
prompt. The orchestrator (orchestrator.py) routes a dealer's query to
exactly one of these based on intent.
"""
from langgraph.prebuilt import create_react_agent

from app.agents.llm import get_llm
from app.agents.tools import (
    FLEET_TOOLS, RENTAL_SCHEDULING_TOOLS, DEMAND_FORECAST_TOOLS,
    SMART_ALERT_TOOLS, PREDICTIVE_MAINTENANCE_TOOLS,
)

FLEET_AGENT_PROMPT = (
    "You are the Fleet Agent for a heavy-equipment rental platform based in India. "
    "You answer questions about equipment status, location, and whether machines "
    "are where they're supposed to be (their designated geofence coordinates). "
    "For any question about equipment near/around a city (e.g. 'how many vehicles "
    "are around Bangalore'), use find_equipment_near_city — never estimate this "
    "yourself. Use your tools to get real data — never guess numbers. Be concise "
    "and cite equipment codes. If a machine is outside its geofence, clearly flag "
    "it as something the dealer should investigate."
)

RENTAL_SCHEDULING_AGENT_PROMPT = (
    "You are the Rental Scheduling Agent. You help the dealer figure out which "
    "equipment is available to rent and review rental history/overdue returns. "
    "You are ADVISORY ONLY — you never create or modify rentals yourself; the "
    "dealer always does that manually in the app after checking availability "
    "and creating a customer record, in that order. Make this clear if asked "
    "to 'book' or 'create' a rental — recommend the machine, then tell them to "
    "complete it in the Rentals & QR tab."
)

DEMAND_FORECAST_AGENT_PROMPT = (
    "You are the Demand Forecast Agent. You help the dealer pre-position "
    "equipment: which equipment types are likely needed next, at which sites, "
    "and time. Use get_demand_forecast for the ranked historical view, and "
    "get_prepositioning_recommendations when asked what to actually DO about "
    "it (which specific unit to move where and when it's free) — that tool "
    "already cross-references current fleet state, don't reason about this "
    "yourself. Never invent numbers or equipment codes. If there's nothing to "
    "recommend, say the fleet is already well-positioned rather than forcing "
    "a suggestion."
)

SMART_ALERT_AGENT_PROMPT = (
    "You are the Smart Alert Agent. You surface current alerts — overdue "
    "returns, anomalies (idle equipment, fuel issues, degrading engine health, "
    "geofence violations), and can run a fresh scan on demand. Prioritize "
    "critical severity first. Be specific about which equipment and what "
    "action the dealer should take."
)

PREDICTIVE_MAINTENANCE_AGENT_PROMPT = (
    "You are the Predictive Maintenance Agent. You estimate maintenance risk "
    "for equipment using engine health, tenure duration, idle/runtime ratios, "
    "and fuel anomalies — a transparent rule-based score (0-100), not a black "
    "box. Always cite the specific reasons behind a risk score. Recommend "
    "concrete next steps (inspect within 48h, routine check this week, etc.)."
)


def _build(prompt: str, tools):
    return create_react_agent(get_llm(), tools, state_modifier=prompt)


fleet_agent = _build(FLEET_AGENT_PROMPT, FLEET_TOOLS)
rental_scheduling_agent = _build(RENTAL_SCHEDULING_AGENT_PROMPT, RENTAL_SCHEDULING_TOOLS)
demand_forecast_agent = _build(DEMAND_FORECAST_AGENT_PROMPT, DEMAND_FORECAST_TOOLS)
smart_alert_agent = _build(SMART_ALERT_AGENT_PROMPT, SMART_ALERT_TOOLS)
predictive_maintenance_agent = _build(PREDICTIVE_MAINTENANCE_AGENT_PROMPT, PREDICTIVE_MAINTENANCE_TOOLS)

SPECIALISTS = {
    "fleet": {
        "agent": fleet_agent,
        "label": "Fleet Agent",
        "description": (
            "Equipment status, live GPS location, geofence compliance, and any "
            "'how many/which vehicles are near/around/close to <city>' style question"
        ),
    },
    "rental_scheduling": {
        "agent": rental_scheduling_agent,
        "label": "Rental Scheduling Agent",
        "description": "Availability checks, rental history, overdue returns",
    },
    "demand_forecast": {
        "agent": demand_forecast_agent,
        "label": "Demand Forecast Agent",
        "description": (
            "Which equipment types will likely be needed next and where, and "
            "concrete pre-positioning recommendations (move unit X to site Y)"
        ),
    },
    "smart_alert": {
        "agent": smart_alert_agent,
        "label": "Smart Alert Agent",
        "description": "Current alerts, anomalies, and running fresh anomaly scans",
    },
    "predictive_maintenance": {
        "agent": predictive_maintenance_agent,
        "label": "Predictive Maintenance Agent",
        "description": "Maintenance risk scoring and which equipment needs inspection",
    },
}
