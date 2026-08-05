# AIOps Support POC — Request Intelligence Platform

AI-driven automation POC that reads Jira Service Management (JSM) style tickets, understands database operations with an LLM, and produces a **Normalized Request** (domain, technology, intent, resolved entities, confidence).

This repository implements **Flow 2 (Request Intelligence)** from the catalog automation design. Downstream steps (catalog matching, policy, Jenkins execution, JSM closure) are planned but not yet implemented.

## Architecture overview

```
JSM ticket → Intake (merge text + OCR) → Request Intelligence (LLM) → Normalized Request JSON
```

**Request Intelligence (Flow 2)** inside the intelligence step:

1. **Orchestrator** — classify Layer 1 (domain), Layer 2 (technology), intent  
2. **Entity extraction** — LLM extracts username, database, role, etc.  
3. **Entity resolution** — YAML lookup maps aliases (e.g. `DEVDB` → `dev-oracle-01`)  
4. **Confidence scoring** — 0–100; flags missing fields and ambiguities  

See `docs/flow1.md` (end-to-end catalog pipeline) and `docs/flow2.md` (intelligence detail).

## Tech stack

| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Orchestration | LangGraph |
| Models / config | Pydantic v2, pydantic-settings |
| LLM (live) | AWS Bedrock via boto3 |
| Logging | structlog (JSON) |

## Project structure

```
request-automation/
  src/
    api/              # FastAPI routes and app wiring
    orchestration/    # LangGraph pipeline (intake → intelligence)
    domain/           # RequestContext, confidence, entity resolution
    infrastructure/   # JSM, Bedrock, OCR adapters + mocks
    config/           # Settings from environment
  entity_lookup/      # CMDB stub (database alias → hostname)
  tests/              # Unit + integration tests
  docker-compose.yaml
  pyproject.toml
docs/
  flow1.md            # Parent catalog automation flow
  flow2.md            # Request Intelligence architecture
```

## Quick start

### Prerequisites

- Python 3.11+
- Optional: Docker & Docker Compose

### Local development

```bash
cd request-automation

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env                 # ADAPTER_MODE=mock by default
uvicorn api.app:app --reload --port 8000
```

Open **http://localhost:8000/docs** for interactive API documentation.

### Docker

```bash
cd request-automation
cp .env.example .env
docker compose up --build
```

Service runs at **http://localhost:8000**.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/process/{ticket_id}` | Run intake + intelligence; returns Normalized Request |

### Example

```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/process/DB-DEMO | python3 -m json.tool
```

### Sample response (`DB-DEMO`)

```json
{
  "request_id": "...",
  "ticket_id": "DB-DEMO",
  "layer1": "database",
  "layer2": "oracle",
  "intent": "create_user",
  "resolved_entities": {
    "username": "APP_READONLY",
    "database": "DEVDB",
    "hostname": "dev-oracle-01",
    "role": "Read Only",
    "environment": "non-production"
  },
  "confidence": 100,
  "status": "normalized"
}
```

## Mock mode (default)

Set `ADAPTER_MODE=mock` in `.env` (no AWS or Jira required).

### Built-in mock tickets

| Ticket ID | Scenario |
|-----------|----------|
| `DB-DEMO` | Happy path — create user, resolved hostname, `status=normalized` |
| `DB-AMBIG` | Ambiguous `PROD` alias → `needs_clarification` |
| `DB-UNSUPPORTED` | Unsupported intent (resize tablespace) → `status=error` |
| `DB-MISSING` | Missing required role → `needs_clarification` |
| `DB-OCR-FAIL` | OCR failure on attachment; still processes from text |

Mock tickets are defined in `request-automation/src/infrastructure/jsm_client.py`. Mock LLM logic lives in `request-automation/src/infrastructure/bedrock_client.py` (`MockLlmClient`).

## Live mode (optional)

Set in `.env`:

```env
ADAPTER_MODE=live
JSM_BASE_URL=https://your-domain.atlassian.net
JSM_EMAIL=your-email@company.com
JSM_API_TOKEN=your-api-token
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

Bedrock uses the boto3 default credential chain (CLI profile, env vars, or instance role). Live OCR is not fully configured in this POC — use mock mode for attachment testing.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ADAPTER_MODE` | `mock` | `mock` or `live` |
| `CONFIDENCE_THRESHOLD` | `80` | Score below this → `needs_clarification` |
| `ENTITY_LOOKUP_PATH` | `entity_lookup/databases.yaml` | Database alias lookup file |
| `LOG_LEVEL` | `INFO` | Logging level |

## Testing

```bash
cd request-automation
source .venv/bin/activate
pytest -q
```

Run a single integration test:

```bash
pytest tests/integration/test_process_api.py::test_process_happy_path -v
```

## Supported intents (POC)

- `create_user`
- `reset_password`
- `grant_role`
- `unlock_user`

Unsupported requests return `intent=unknown` with an error payload.

## Roadmap (deferred)

- Request validation gate + human clarification via JSM comments  
- Catalog resolver (YAML descriptors → Jenkins execution plan)  
- Policy engine (production approval)  
- Jenkins trigger + execution history  

## License

Apache License 2.0 — see [LICENSE](LICENSE).
