from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.orchestrator import run_orchestrator

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentQuery(BaseModel):
    message: str


class AgentResponse(BaseModel):
    response: str
    agent_used: str
    agent_key: str


@router.post("/query", response_model=AgentResponse)
def query_agent(payload: AgentQuery):
    # Synchronous def: FastAPI runs this in a threadpool so the blocking
    # Groq calls don't stall the event loop (and the live-telemetry simulator
    # loop running alongside it).
    return run_orchestrator(payload.message)
