import pytest

from domain.models import EntityResult, IntentResult
from infrastructure.bedrock_client import MockLlmClient, RetryingLlmClient
from infrastructure.ocr_processor import MockOcrProcessor


@pytest.mark.asyncio
async def test_mock_llm_create_user():
    llm = MockLlmClient()
    result = await llm.classify_intent("Create user APP_READONLY in DEVDB, grant Read Only role.")
    assert result.intent.value == "create_user"
    entities = await llm.extract_entities(
        "Create user APP_READONLY in DEVDB, grant Read Only role.", "create_user"
    )
    assert entities.username == "APP_READONLY"
    assert entities.database == "DEVDB"
    assert entities.role is not None


@pytest.mark.asyncio
async def test_mock_llm_unsupported():
    llm = MockLlmClient()
    result = await llm.classify_intent("Resize tablespace USERS to 50G on PRODDB.")
    assert result.intent.value == "unknown"


@pytest.mark.asyncio
async def test_ocr_failure_raises():
    ocr = MockOcrProcessor()
    with pytest.raises(RuntimeError):
        await ocr.extract_text("https://example.invalid/bad.png")


@pytest.mark.asyncio
async def test_llm_retry_then_fail():
    class BadLlm:
        async def classify_intent(self, unified_context: str) -> IntentResult:
            raise ValueError("bad json")

        async def extract_entities(self, unified_context: str, intent: str) -> EntityResult:
            raise ValueError("bad json")

    client = RetryingLlmClient(BadLlm(), max_retries=2)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await client.classify_intent("anything")
