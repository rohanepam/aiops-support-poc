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

## How It Works — Jira ITSM Integration

This system is the **brain** between Jira and the actual automation (Jenkins). It doesn't create tickets — it **reads** them, **understands** what the human is asking, and produces a structured output that automation tools can act on.

### End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  HUMAN (End User)                                                    │
│                                                                       │
│  "I need a new Oracle database account for my analytics service"     │
│                                                                       │
│  1. Opens Jira Service Management portal                             │
│  2. Fills out a request form                                         │
│  3. Attaches a screenshot/log/PDF as evidence                        │
│  4. Submits ticket → gets ticket ID: DB-1234                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  JIRA SERVICE MANAGEMENT (ITSM)                                      │
│                                                                       │
│  Ticket DB-1234:                                                     │
│    Summary: "Create Oracle user"                                     │
│    Description: "Create user APP_READONLY in DEVDB, grant Read Only" │
│    Attachments: [screenshot.png, error.log]                          │
│    Comments: ["Manager approved"]                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │  Webhook / API trigger
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  THIS SYSTEM (Request Automation)                                    │
│                                                                       │
│  POST /api/process/DB-1234                                           │
│                                                                       │
│  Step 1: INTAKE                                                      │
│    → Calls JSM REST API to fetch ticket DB-1234                      │
│    → Gets summary, description, attachments, comments                │
│    → Downloads each attachment                                       │
│    → OCR/reads attachments (image → Claude Vision, log → text read)  │
│    → Merges everything into "Unified Context"                        │
│                                                                       │
│  Step 2: INTELLIGENCE                                                │
│    → LLM classifies intent: "create_user"                            │
│    → LLM extracts entities: username=APP_READONLY, database=DEVDB    │
│    → Resolver maps DEVDB → hostname: dev-oracle-01                   │
│    → Scores confidence: 100%                                         │
│                                                                       │
│  Step 3: OUTPUT                                                      │
│    → Returns Normalized Request JSON                                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DOWNSTREAM (Future — Flow 3+)                                       │
│                                                                       │
│  • Catalog Resolver → matches to automation playbook                 │
│  • Policy Engine → checks if approval needed                         │
│  • Jenkins → executes the actual DB command                          │
│  • Updates Jira ticket with result                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### JSM Integration (Live Mode)

In live mode, the system calls the real Jira REST API:

```
GET  /rest/api/3/issue/{ticket_id}           → summary, description, attachments
GET  /rest/api/3/issue/{ticket_id}/comment   → all comments on the ticket
```

Attachments are downloaded and processed based on file type:

| Attachment Type | Processing Method |
|-----------------|-------------------|
| Images (.png, .jpg, .gif, .webp) | Claude Vision API (visual OCR) |
| PDFs (.pdf) | PyPDF2 text extraction / Claude for scanned |
| Logs (.log, .txt) | Direct text read |
| Spreadsheets (.csv, .xlsx) | Direct read / openpyxl parse |
| Data files (.json, .yaml, .xml) | Direct text read |
| Word docs (.docx) | XML extraction |

### Production Trigger Options

**Option A: Jira Automation Rule (Webhook)**

Configure in Jira → Project Settings → Automation:
```
WHEN: Issue created in project "DBA"
THEN: Send webhook → POST http://request-automation:8000/api/process/{{issue.key}}
```

**Option B: Scheduled Polling**
```
Every 30 seconds:
  → Query JSM for new unprocessed tickets
  → For each ticket, call POST /api/process/{ticket_id}
```

### What the Mock Tickets Simulate

| Mock Ticket | Real-World Scenario |
|---|---|
| `DB-DEMO` | User fills out JSM form completely with all required fields |
| `DB-MISSING` | User forgets to specify the role in their request |
| `DB-AMBIG` | User says "PROD" but there are 2 production databases |
| `DB-UNSUPPORTED` | User asks for an operation we can't automate (tablespace resize) |
| `DB-OCR-FAIL` | User attaches a blurry/corrupt screenshot — pipeline still works from text |

---

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

Bedrock uses the boto3 default credential chain (CLI profile, env vars, or instance role). Live OCR uses Claude Vision via Bedrock to extract text from image attachments.

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

### Human Scenario Tests

Run 21 end-to-end tests simulating real user interactions (all attachment types, edge cases):

```bash
python tests/human_scenario_tests.py
```

Generates a detailed report at `request-automation/test-report.md`.

### Postman Collection

Import `request-automation/postman/Request_Automation_API.postman_collection.json` into Postman for interactive API testing. Includes all mock scenarios with pre-built test assertions.

## Supported intents (POC)

- `create_user`
- `reset_password`
- `grant_role`
- `unlock_user`

Unsupported requests return `intent=unknown` with an error payload.

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/api-reference.md) | Full endpoint specs, schemas, error codes |
| [User Guide](docs/user-guide.md) | Installation, configuration, integration, troubleshooting |
| [Test Report](request-automation/test-report.md) | Human scenario test results (21 tests) |
| [Flow 1 Diagram](docs/flow1.md) | End-to-end catalog automation pipeline |

## Roadmap (deferred)

- Request validation gate + human clarification via JSM comments  
- Catalog resolver (YAML descriptors → Jenkins execution plan)  
- Policy engine (production approval)  
- Jenkins trigger + execution history  

## License

Apache License 2.0 — see [LICENSE](LICENSE).
