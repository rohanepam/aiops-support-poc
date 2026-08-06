from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from domain.confidence import score_confidence
from domain.entity_resolver import load_database_lookup, resolve_entities
from domain.models import Intent, RequestContext, RequestStatus

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


@router.post("/api/process-attachment")
async def process_attachment(
    request: Request,
    file: UploadFile = File(...),
    summary: Optional[str] = Form(default=""),
    description: Optional[str] = Form(default=""),
) -> dict:
    """Process an uploaded file attachment through the full pipeline.

    Accepts any file (image, PDF, log, CSV, Excel, etc.), extracts text,
    runs intent classification + entity extraction, and returns the full
    result with extracted text visible in the response.

    Use this endpoint from Postman with form-data:
      - file: the attachment (required)
      - summary: ticket summary text (optional)
      - description: ticket description text (optional)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")

    log = logger.bind(filename=file.filename, content_type=file.content_type)
    log.info("attachment_process_started")

    # Save uploaded file to temp location
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        settings = request.app.state.settings
        ocr = request.app.state.ocr
        llm = request.app.state.llm

        # Step 1: Extract text from attachment
        extracted_text = ""
        ocr_error = None
        text_exts = (".txt", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".conf")

        if suffix.lower() in text_exts:
            # Text-based files: read directly (no OCR needed)
            extracted_text = Path(tmp_path).read_text(errors="replace")[:15000]
        else:
            try:
                extracted_text = await ocr.extract_text(tmp_path)
            except Exception as exc:
                ocr_error = f"{type(exc).__name__}: {exc}"
                log.warning("ocr_failed", error=ocr_error)

        # Step 2: Build unified context
        unified_context = "\n".join(
            part for part in [summary or "", description or "", extracted_text] if part.strip()
        )

        if not unified_context.strip():
            return {
                "status": "error",
                "error": "No text could be extracted from the file and no summary/description provided",
                "file": file.filename,
                "file_size_bytes": len(content),
                "extracted_text": "",
            }

        # Step 3: Intent classification
        intent_result = await llm.classify_intent(unified_context)

        # Step 4: Entity extraction
        entity_result = await llm.extract_entities(unified_context, intent_result.intent.value)

        # Step 5: Entity resolution
        lookup = load_database_lookup(Path(settings.entity_lookup_path))
        resolved, ambiguities = resolve_entities(entity_result, lookup)

        # Step 6: Confidence scoring
        confidence, missing = score_confidence(
            intent_result.intent, resolved, ambiguities, threshold=settings.confidence_threshold
        )

        # Determine status
        if intent_result.intent == Intent.UNKNOWN:
            status = RequestStatus.ERROR
        elif ambiguities or missing or confidence < settings.confidence_threshold:
            status = RequestStatus.NEEDS_CLARIFICATION
        else:
            status = RequestStatus.NORMALIZED

        log.info(
            "attachment_process_complete",
            intent=intent_result.intent.value,
            confidence=confidence,
            status=status.value,
        )

        return {
            "file": file.filename,
            "file_size_bytes": len(content),
            "file_type": suffix,
            "processing": {
                "extracted_text": extracted_text,
                "extracted_chars": len(extracted_text),
                "ocr_error": ocr_error,
                "unified_context_chars": len(unified_context),
            },
            "classification": {
                "layer1": intent_result.layer1,
                "layer2": intent_result.layer2,
                "intent": intent_result.intent.value,
                "intent_message": intent_result.message,
            },
            "entities": {
                "raw_extracted": {
                    "username": entity_result.username,
                    "database": entity_result.database,
                    "role": entity_result.role,
                },
                "resolved": resolved.model_dump(),
            },
            "confidence": confidence,
            "confidence_metadata": {
                "missing_fields": missing,
                "ambiguities": [a.model_dump() for a in ambiguities],
            },
            "status": status.value,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)
