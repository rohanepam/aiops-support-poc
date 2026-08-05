from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from config.settings import Settings, get_settings


@pytest.fixture
def app(monkeypatch):
    get_settings.cache_clear()
    lookup = str(Path(__file__).resolve().parents[2] / "entity_lookup" / "databases.yaml")
    monkeypatch.setenv("ADAPTER_MODE", "mock")
    monkeypatch.setenv("ENTITY_LOOKUP_PATH", lookup)
    get_settings.cache_clear()
    application = create_app()
    yield application
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_process_happy_path(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/process/DB-DEMO")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "create_user"
    assert body["layer1"] == "database"
    assert body["layer2"] == "oracle"
    assert body["resolved_entities"]["username"] == "APP_READONLY"
    assert body["resolved_entities"]["hostname"] == "dev-oracle-01"
    assert body["confidence"] >= 90
    assert body["status"] == "normalized"


@pytest.mark.asyncio
async def test_process_missing_role(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/process/DB-MISSING")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "create_user"
    assert body["resolved_entities"]["username"] == "APP01"
    assert body["status"] == "needs_clarification"
    assert "role" in body["confidence_metadata"]["missing_fields"]
    assert body["confidence"] < 80


@pytest.mark.asyncio
async def test_process_ambiguous(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/process/DB-AMBIG")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_clarification"
    assert body["confidence"] < 80
    assert body["resolved_entities"]["hostname"] is None
    assert len(body["confidence_metadata"]["ambiguities"]) >= 1


@pytest.mark.asyncio
async def test_process_unsupported(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/process/DB-UNSUPPORTED")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "unknown"
    assert body["error"] is not None
    assert body["status"] == "error"


@pytest.mark.asyncio
async def test_process_ocr_fail_still_ingests(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/process/DB-OCR-FAIL")
    assert resp.status_code == 200
    body = resp.json()
    # Text fields still produce a create_user normalized result
    assert body["intent"] == "create_user"
    assert body["resolved_entities"]["username"] == "APP_READONLY"
    assert body["status"] == "normalized"
