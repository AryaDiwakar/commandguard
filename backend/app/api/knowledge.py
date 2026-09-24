"""Search endpoint for approved operator guidance."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.knowledge.base import search

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/search")
async def knowledge_search(query: str = Query(min_length=1, max_length=300)):
    return {"results": search(query)}
