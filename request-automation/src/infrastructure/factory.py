from __future__ import annotations

from config.settings import Settings
from domain.interfaces import JsmPort, LlmPort, OcrPort
from infrastructure.bedrock_client import BedrockClient, MockLlmClient, RetryingLlmClient
from infrastructure.jsm_client import JsmClient, MockJsmClient
from infrastructure.ocr_processor import MockOcrProcessor, OcrProcessor


def build_jsm(settings: Settings) -> JsmPort:
    if settings.adapter_mode == "mock":
        return MockJsmClient()
    return JsmClient(settings.jsm_base_url, settings.jsm_email, settings.jsm_api_token)


def build_ocr(settings: Settings) -> OcrPort:
    if settings.adapter_mode == "mock":
        return MockOcrProcessor()
    return OcrProcessor()


def build_llm(settings: Settings) -> LlmPort:
    inner: LlmPort
    if settings.adapter_mode == "mock":
        inner = MockLlmClient()
    else:
        inner = BedrockClient(settings.bedrock_model_id, settings.aws_region)
    return RetryingLlmClient(inner, max_retries=2)
