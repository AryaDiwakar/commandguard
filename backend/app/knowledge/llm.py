"""Free local-LLM layer for grounded RAG answers.

Talks to a local Ollama server (no API keys, no external network). Uses a small
instruct model to paraphrase an answer strictly from retrieved context. Every
call is defensive: on any failure it returns ``None`` so the caller can fall
back to deterministic templates and the demo keeps working.
"""
from __future__ import annotations

import os
import urllib.request
import json

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
PREFERRED_MODELS = tuple(
    m.strip()
    for m in os.getenv(
        "CAT_LLM_MODELS",
        "llama3.2:3b,qwen2.5:3b",
    ).split(",")
    if m.strip()
)
TIMEOUT_S = 30
MAX_TOKENS = 220


def _available_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [item["name"] for item in data.get("models", [])]
    except Exception:
        return []


def pick_model() -> str | None:
    available = set(_available_models())
    for model in PREFERRED_MODELS:
        if model in available:
            return model
    return available.pop() if available else None


def generate(system: str, user: str, temperature: float = 0.2) -> tuple[str, str] | None:
    """Return ``(provider_label, text)`` or ``None`` when the LLM is unreachable."""
    model = pick_model()
    if not model:
        return None
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": MAX_TOKENS},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = str(body.get("message", {}).get("content", "")).strip()
        if not text:
            return None
        return f"ollama · {model}", text
    except Exception:
        return None