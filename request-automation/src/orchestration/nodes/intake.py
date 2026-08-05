from __future__ import annotations

import structlog

from domain.interfaces import JsmPort, OcrPort
from domain.models import PipelineError, RequestContext, RequestStatus

logger = structlog.get_logger(__name__)


def make_intake_node(jsm: JsmPort, ocr: OcrPort):
    async def intake(state: RequestContext) -> RequestContext:
        log = logger.bind(request_id=state.request_id, ticket_id=state.ticket_id)
        try:
            ticket = await jsm.get_ticket(state.ticket_id)
            state.summary = ticket.get("summary") or ""
            state.description = ticket.get("description") or ""
            state.attachments = _as_str_list(ticket.get("attachments"))
            state.comments = _as_str_list(ticket.get("comments"))

            attachment_texts: list[str] = []
            for url in state.attachments:
                try:
                    text = await ocr.extract_text(url)
                    if text:
                        attachment_texts.append(text)
                except Exception as exc:  # noqa: BLE001 — graceful degrade
                    log.warning("ocr_failed_continue", error=type(exc).__name__)

            state.unified_context = _merge_context(
                state.summary, state.description, attachment_texts, state.comments
            )
            state.status = RequestStatus.INGESTED
            log.info("intake_complete", unified_chars=len(state.unified_context))
            return state
        except Exception as exc:  # noqa: BLE001
            state.error = PipelineError(
                error_code="intake_failed",
                message=str(exc),
                details={"type": type(exc).__name__},
            )
            state.status = RequestStatus.ERROR
            return state

    return intake


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _merge_context(
    summary: str,
    description: str,
    attachment_texts: list[str],
    comments: list[str],
) -> str:
    parts: list[str] = []
    seen: set[str] = set()

    def add(chunk: str) -> None:
        cleaned = chunk.strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        # Skip if fully contained in an already-added longer part
        for existing in list(seen):
            if key in existing:
                return
        seen.add(key)
        parts.append(cleaned)

    add(summary)
    add(description)
    for t in attachment_texts:
        add(t)
    for c in comments:
        add(c)
    return "\n".join(parts)
