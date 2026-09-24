"""Small approved knowledge base for grounded prototype assistance.

This is intentionally retrieval-only. It does not invent maintenance or repair
instructions and can later be replaced by an indexed document store.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    source: str
    content: str
    topics: tuple[str, ...]


DOCUMENTS = (
    KnowledgeDocument(
        "SAFE-STOP-001",
        "Safe stop and escalation",
        "approved://operator/safe-stop",
        "When an abnormal machine condition is detected, reduce load if safe, stop movement, confirm the work area is clear, request assistance, and follow the designated site escalation process. Do not attempt repairs from the operator station.",
        ("stop", "safe", "incident", "escalate", "help"),
    ),
    KnowledgeDocument(
        "FUEL-INCIDENT-001",
        "Abnormal fuel loss response",
        "approved://operator/fuel-loss",
        "If observed fuel loss is inconsistent with reported consumption, stop safely, request maintenance or safety assistance, shut down only according to the approved site procedure, and verify that RPM is zero and the fuel trend has stabilized. Do not inspect, open, or repair the fuel system as an automated instruction.",
        ("fuel", "leak", "loss", "shutdown", "maintenance"),
    ),
    KnowledgeDocument(
        "THERMAL-INCIDENT-001",
        "Thermal escalation response",
        "approved://operator/thermal",
        "For rising engine or coolant temperature, reduce machine load if safe, monitor the trend, move to a safe stop if the trend continues, and contact designated maintenance or safety personnel. This guidance does not authorize continued operation above site-defined limits.",
        ("temperature", "thermal", "overheat", "coolant", "load"),
    ),
    KnowledgeDocument(
        "PROXIMITY-001",
        "Proximity hazard response",
        "approved://operator/proximity",
        "When an object or person enters the safety radius, stop movement if safe, keep the machine stationary, confirm the area is clear through the approved site process, and resume only when authorized.",
        ("proximity", "distance", "reversing", "hazard", "person"),
    ),
)


def search(query: str, limit: int = 3) -> list[dict[str, str | float]]:
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    ranked: list[tuple[float, KnowledgeDocument]] = []
    for document in DOCUMENTS:
        haystack = set(document.topics) | set(re.findall(r"[a-z0-9]+", document.content.lower()))
        score = len(terms & haystack) / max(1, len(terms))
        if score > 0:
            ranked.append((score, document))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "document_id": document.document_id,
            "title": document.title,
            "source": document.source,
            "excerpt": document.content,
            "score": round(score, 3),
        }
        for score, document in ranked[:limit]
    ]
