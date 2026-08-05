from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Intent(str, Enum):
    CREATE_USER = "create_user"
    RESET_PASSWORD = "reset_password"
    GRANT_ROLE = "grant_role"
    UNLOCK_USER = "unlock_user"
    UNKNOWN = "unknown"


class RequestStatus(str, Enum):
    NEW = "new"
    INGESTED = "ingested"
    NORMALIZED = "normalized"
    NEEDS_CLARIFICATION = "needs_clarification"
    ERROR = "error"


REQUIRED_ENTITIES: dict[Intent, list[str]] = {
    Intent.CREATE_USER: ["username", "database", "role"],
    Intent.RESET_PASSWORD: ["username", "database"],
    Intent.GRANT_ROLE: ["username", "database", "role"],
    Intent.UNLOCK_USER: ["username", "database"],
    Intent.UNKNOWN: [],
}


class PipelineError(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class IntentResult(BaseModel):
    layer1: str = "database"
    layer2: str | None = None
    intent: Intent
    message: str | None = None
    confidence_hint: float | None = None


class EntityResult(BaseModel):
    username: str | None = None
    database: str | None = None
    role: str | None = None
    environment: str | None = None
    hostname: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    tablespace: str | None = None
    tenant: str | None = None

    model_config = {"populate_by_name": True}


class Ambiguity(BaseModel):
    field: str
    raw_value: str
    candidates: list[dict[str, Any]]


class ResolvedEntities(BaseModel):
    username: str | None = None
    database: str | None = None
    role: str | None = None
    environment: str | None = None
    hostname: str | None = None
    technology: str | None = None
    schema_name: str | None = None
    tablespace: str | None = None
    tenant: str | None = None


class RequestContext(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    ticket_id: str = ""
    summary: str = ""
    description: str = ""
    attachments: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    unified_context: str = ""

    layer1: str | None = None
    layer2: str | None = None
    intent: Intent | None = None
    intent_message: str | None = None

    entities: ResolvedEntities = Field(default_factory=ResolvedEntities)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    confidence: int = 0
    status: RequestStatus = RequestStatus.NEW
    clarification_round: int = 0

    error: PipelineError | None = None
    created_at: datetime = Field(default_factory=utc_now)

    def normalized_request(self) -> dict[str, Any]:
        """Platform Normalized Request payload (Flow 2 output)."""
        return {
            "request_id": self.request_id,
            "ticket_id": self.ticket_id,
            "layer1": self.layer1,
            "layer2": self.layer2,
            "layer3": self.intent.value if self.intent else None,
            "intent": self.intent.value if self.intent else None,
            "intent_message": self.intent_message,
            "resolved_entities": self.entities.model_dump(),
            "confidence": self.confidence,
            "confidence_metadata": {
                "missing_fields": self.missing_fields,
                "ambiguities": [a.model_dump() for a in self.ambiguities],
            },
            "status": self.status.value,
            "error": self.error.model_dump() if self.error else None,
        }
