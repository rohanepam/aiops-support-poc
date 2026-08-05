from __future__ import annotations

from pathlib import Path

import structlog

from config.settings import Settings
from domain.confidence import score_confidence
from domain.entity_resolver import load_database_lookup, resolve_entities
from domain.interfaces import LlmPort
from domain.models import Intent, PipelineError, RequestContext, RequestStatus

logger = structlog.get_logger(__name__)


def make_intelligence_node(llm: LlmPort, settings: Settings):
    lookup = load_database_lookup(Path(settings.entity_lookup_path))

    async def intelligence(state: RequestContext) -> RequestContext:
        log = logger.bind(request_id=state.request_id, ticket_id=state.ticket_id)
        if state.status == RequestStatus.ERROR:
            return state

        try:
            # Flow 2 — Orchestrator: classification (Layer1 / Layer2 / intent)
            intent_result = await llm.classify_intent(state.unified_context)
            state.layer1 = intent_result.layer1
            state.layer2 = intent_result.layer2
            state.intent = intent_result.intent
            state.intent_message = intent_result.message

            if intent_result.intent == Intent.UNKNOWN:
                state.confidence = 10
                state.status = RequestStatus.ERROR
                state.error = PipelineError(
                    error_code="unsupported_intent",
                    message=intent_result.message or "Unknown intent",
                )
                log.info("intelligence_unknown_intent")
                return state

            # Database module — Entity Extraction
            extracted = await llm.extract_entities(
                state.unified_context, intent_result.intent.value
            )

            # Entity Resolution & Enrichment + Domain Context
            resolved, ambiguities = resolve_entities(extracted, lookup)
            state.entities = resolved
            state.ambiguities = ambiguities
            if resolved.technology and not state.layer2:
                state.layer2 = resolved.technology

            confidence, missing = score_confidence(
                state.intent,
                state.entities,
                state.ambiguities,
                threshold=settings.confidence_threshold,
            )
            state.confidence = confidence
            state.missing_fields = missing

            if ambiguities or missing or confidence < settings.confidence_threshold:
                state.status = RequestStatus.NEEDS_CLARIFICATION
            else:
                state.status = RequestStatus.NORMALIZED

            log.info(
                "intelligence_complete",
                intent=state.intent.value if state.intent else None,
                confidence=state.confidence,
                status=state.status.value,
            )
            return state
        except Exception as exc:  # noqa: BLE001
            state.error = PipelineError(
                error_code="intelligence_failed",
                message=str(exc),
                details={"type": type(exc).__name__},
            )
            state.status = RequestStatus.ERROR
            log.warning("intelligence_failed", error=type(exc).__name__)
            return state

    return intelligence
