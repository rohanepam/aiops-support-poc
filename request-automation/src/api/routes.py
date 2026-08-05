from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request

from domain.models import RequestContext

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/process/{ticket_id}")
async def process_ticket(ticket_id: str, request: Request) -> dict:
    if not ticket_id.strip():
        raise HTTPException(status_code=400, detail="ticket_id is required")
    graph = request.app.state.graph
    ctx = RequestContext(ticket_id=ticket_id.strip())
    log = logger.bind(request_id=ctx.request_id, ticket_id=ctx.ticket_id)
    log.info("process_started")
    try:
        result = await graph.ainvoke(ctx)
        # LangGraph may return dict-like state
        if isinstance(result, RequestContext):
            final = result
        else:
            final = RequestContext.model_validate(result)
        payload = final.normalized_request()
        log.info("process_finished", status=final.status.value, confidence=final.confidence)
        return payload
    except Exception as exc:  # noqa: BLE001
        log.warning("process_exception", error=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Request processing failed") from exc
