from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain.models import EntityResult, IntentResult


class JsmPort(ABC):
    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Return summary, description, attachments (URLs), comments."""


class OcrPort(ABC):
    @abstractmethod
    async def extract_text(self, attachment_url: str) -> str:
        """Extract text from an image/Excel attachment URL. Raises on hard failure."""


class LlmPort(ABC):
    @abstractmethod
    async def classify_intent(self, unified_context: str) -> IntentResult:
        """Classify Layer1/Layer2/intent from unified context."""

    @abstractmethod
    async def extract_entities(self, unified_context: str, intent: str) -> EntityResult:
        """Extract entities; missing fields must be null, never guessed."""
