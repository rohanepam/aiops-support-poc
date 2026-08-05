from __future__ import annotations

import json
import re
from typing import Any

import boto3
import structlog

from domain.interfaces import LlmPort
from domain.models import EntityResult, Intent, IntentResult

logger = structlog.get_logger(__name__)

SUPPORTED_INTENTS = (
    "create_user",
    "reset_password",
    "grant_role",
    "unlock_user",
    "unknown",
)


class MockLlmClient(LlmPort):
    """Deterministic LLM for local/tests — no AWS required."""

    async def classify_intent(self, unified_context: str) -> IntentResult:
        text = unified_context.lower()
        if "resize" in text or re.search(r"\btablespace\b", text):
            return IntentResult(
                layer1="database",
                layer2="oracle",
                intent=Intent.UNKNOWN,
                message="Unsupported request: tablespace operations are not automated",
            )
        if "create user" in text or "create a user" in text:
            return IntentResult(layer1="database", layer2="oracle", intent=Intent.CREATE_USER)
        if "reset password" in text or "password reset" in text:
            return IntentResult(layer1="database", layer2="oracle", intent=Intent.RESET_PASSWORD)
        if "grant" in text and "role" in text:
            return IntentResult(layer1="database", layer2="oracle", intent=Intent.GRANT_ROLE)
        if "unlock user" in text or re.search(r"\bunlock\b.+\buser\b", text) or (
            "unlock" in text and ("account" in text or "oracle" in text)
        ):
            return IntentResult(layer1="database", layer2="oracle", intent=Intent.UNLOCK_USER)
        return IntentResult(
            layer1="database",
            layer2=None,
            intent=Intent.UNKNOWN,
            message="Unable to classify request intent",
        )

    async def extract_entities(self, unified_context: str, intent: str) -> EntityResult:
        ident = r"([A-Za-z][A-Za-z0-9_.-]*)"
        username = _best_identifier(
            rf"(?:create\s+(?:a\s+)?user|unlock\s+(?:a\s+)?user|username|account)\s+{ident}",
            unified_context,
        )
        if not username:
            username = _match(rf"\bfor\s+{ident}\s+on\b", unified_context, flags=re.I)
        if not username:
            username = _match(rf"\breset\s+password\s+(?:for\s+)?{ident}", unified_context, flags=re.I)

        database = _match(rf"\bin\s+(?:the\s+)?{ident}", unified_context, flags=re.I)
        if not database:
            database = _match(rf"\bon\s+{ident}\b", unified_context, flags=re.I)

        role = _match(r"grant\s+([A-Za-z0-9_ ]+?)\s+role", unified_context, flags=re.I)
        if not role:
            role = _match(r"role\s+([A-Za-z0-9_ ]+)", unified_context, flags=re.I)

        # Never invent — leave null if not found
        return EntityResult(
            username=username.upper() if username else None,
            database=database.upper() if database else None,
            role=role.strip() if role else None,
        )


def _match(pattern: str, text: str, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _best_identifier(pattern: str, text: str) -> str | None:
    """Prefer technical identifiers (underscore/digit) over English words."""
    matches = [m.group(1).strip() for m in re.finditer(pattern, text, flags=re.I)]
    if not matches:
        return None

    def score(token: str) -> tuple[int, int]:
        return (1 if re.search(r"[_0-9]", token) else 0, len(token))

    return sorted(matches, key=score, reverse=True)[0]


class BedrockClient(LlmPort):
    """AWS Bedrock Runtime via boto3 default credential chain."""

    def __init__(self, model_id: str, region: str) -> None:
        self._model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    async def classify_intent(self, unified_context: str) -> IntentResult:
        prompt = (
            "Classify this IT service request. Return JSON only with keys: "
            "layer1 (domain e.g. database), layer2 (technology e.g. oracle), "
            f"intent (one of {list(SUPPORTED_INTENTS)}), message (optional string). "
            "Use intent=unknown for unsupported ops. Do not invent facts.\n\n"
            f"Request:\n{unified_context}"
        )
        raw = self._invoke(prompt)
        return IntentResult.model_validate(raw)

    async def extract_entities(self, unified_context: str, intent: str) -> EntityResult:
        prompt = (
            "Extract entities from this request as JSON with keys: "
            "username, database, role, environment, hostname, schema, tablespace, tenant. "
            "Use null for anything not explicitly stated — never guess.\n"
            f"Intent: {intent}\n\nRequest:\n{unified_context}"
        )
        raw = self._invoke(prompt)
        return EntityResult.model_validate(raw)

    def _invoke(self, prompt: str) -> dict[str, Any]:
        # Avoid logging request body (may contain identifiers); log length only
        logger.info("bedrock_invoke", prompt_chars=len(prompt), model=self._model_id)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(response["body"].read())
        content = payload.get("content") or []
        if not content or not isinstance(content[0], dict) or "text" not in content[0]:
            raise ValueError("empty Bedrock content")
        text = content[0]["text"]
        return _parse_json_object(text)


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class RetryingLlmClient(LlmPort):
    """Validate via Pydantic at call sites; retry classify/extract up to max_retries."""

    def __init__(self, inner: LlmPort, max_retries: int = 2) -> None:
        self._inner = inner
        self._max_retries = max_retries

    async def classify_intent(self, unified_context: str) -> IntentResult:
        return await self._with_retry(lambda: self._inner.classify_intent(unified_context), IntentResult)

    async def extract_entities(self, unified_context: str, intent: str) -> EntityResult:
        return await self._with_retry(
            lambda: self._inner.extract_entities(unified_context, intent), EntityResult
        )

    async def _with_retry(self, factory, model_cls):  # type: ignore[no-untyped-def]
        last_exc: Exception | None = None
        attempts = max(1, self._max_retries + 1)
        for attempt in range(attempts):
            try:
                result = await factory()
                # Re-validate to catch mock/live drift
                return model_cls.model_validate(result.model_dump(by_alias=True))
            except Exception as exc:  # noqa: BLE001 — convert to pipeline error upstream
                last_exc = exc
                logger.warning("llm_retry", attempt=attempt + 1, error=type(exc).__name__)
        raise last_exc or RuntimeError("LLM failed without exception")
