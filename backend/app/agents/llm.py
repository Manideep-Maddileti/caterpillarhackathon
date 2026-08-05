"""Groq LLM factory shared by every agent. Anchored to backend/.env by an
absolute path rather than relying on dotenv's cwd-relative auto-discovery —
uvicorn's working directory isn't guaranteed to be backend/, and a silent
miss here would look like a missing API key.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

from langchain_groq import ChatGroq

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_llm(temperature: float = 0.2) -> ChatGroq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set (expected in backend/.env)")
    return ChatGroq(model=GROQ_MODEL, api_key=api_key, temperature=temperature)
