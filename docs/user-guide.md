# User Guide — Request Automation Platform

## Overview

The Request Automation Platform processes IT service requests (from Jira Service Management) and automatically understands what the user is asking for. It reads ticket text, attached screenshots, log files, PDFs, spreadsheets, and other documents — then extracts the intent, entities, and confidence level needed for downstream automation.

**What it does:**
- Reads a JSM ticket (summary, description, comments, attachments)
- Extracts text from any attachment (images via Claude Vision, PDFs, logs, Excel, etc.)
- Classifies the request intent (create user, reset password, grant role, unlock account)
- Extracts entities (username, database, role, hostname, environment)
- Resolves database aliases to canonical hostnames
- Scores confidence and flags what's missing or ambiguous
- Returns a structured Normalized Request for automation

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- pip (package manager)
- Optional: Docker & Docker Compose
- Optional: AWS credentials (for live Claude/Bedrock integration)

### Installation

```bash
# Clone the repository
git clone https://github.com/rohanepam/aiops-support-poc.git
cd aiops-support-poc/request-automation

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env
```

### Running the Service

**Option 1: Local development**
```bash
cd request-automation
source .venv/bin/activate
uvicorn api.app:app --reload --port 8000
```

**Option 2: Docker**
```bash
cd request-automation
docker compose up --build
```

The service starts at **http://localhost:8000**.

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health
# {"status":"ok"}

# Process a demo ticket
curl -X POST http://localhost:8000/api/process/DB-DEMO | python3 -m json.tool
```

---

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `ADAPTER_MODE` | `mock` | `mock` = no external services needed; `live` = connects to real JSM + AWS Bedrock |
| `CONFIDENCE_THRESHOLD` | `80` | Requests scoring below this need clarification |
| `ENTITY_LOOKUP_PATH` | `entity_lookup/databases.yaml` | Path to the database alias lookup file |
| `LOG_LEVEL` | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `JSM_BASE_URL` | — | Jira base URL (live mode only) |
| `JSM_EMAIL` | — | Jira service account email (live mode only) |
| `JSM_API_TOKEN` | — | Jira API token (live mode only) |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | AWS Bedrock model for LLM + OCR |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |

---

## Operating Modes

### Mock Mode (Default)

No external services required. Uses built-in mock tickets and a regex-based LLM simulator. Ideal for:
- Local development
- Running tests
- Demos and presentations
- CI/CD pipelines

```env
ADAPTER_MODE=mock
```

### Live Mode

Connects to real Jira Service Management and AWS Bedrock (Claude). Requires:
- Valid Jira API credentials
- AWS credentials (via CLI profile, environment, or IAM role)
- Bedrock model access enabled in your AWS account

```env
ADAPTER_MODE=live
JSM_BASE_URL=https://your-domain.atlassian.net
JSM_EMAIL=automation@company.com
JSM_API_TOKEN=your-secret-token
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
AWS_REGION=us-east-1
```

---

## How It Works

### Pipeline Flow

```
1. INTAKE
   ├── Fetch ticket from JSM (summary, description, comments)
   ├── Download attachments
   ├── OCR/extract text from each attachment
   │   ├── Images → Claude Vision API
   │   ├── PDFs → PyPDF2 (or Claude for scanned PDFs)
   │   ├── Logs/Text/CSV → Direct read
   │   ├── Excel → openpyxl parse
   │   └── Word → XML extraction
   └── Merge into Unified Context (deduped)

2. INTELLIGENCE
   ├── Classify intent (create_user, reset_password, grant_role, unlock_user)
   ├── Detect domain (Layer 1: database) and technology (Layer 2: oracle)
   ├── Extract entities (username, database, role, etc.)
   ├── Resolve entities (map aliases → canonical hostnames)
   └── Score confidence (0-100)

3. OUTPUT
   └── Return Normalized Request JSON
       ├── status: "normalized" → ready for automation
       ├── status: "needs_clarification" → ask user for missing info
       └── status: "error" → unsupported or failed
```

### Attachment Processing Details

The system handles any file a user might attach to a ticket:

| What users attach | How the system reads it |
|-------------------|-------------------------|
| Screenshot of a form | Claude Vision reads all text from the image |
| Error screenshot (ORA-28000) | Claude Vision extracts the error code and details |
| Application log file | Read directly as text — no AI needed |
| CSV with user list | Read as text, LLM extracts structured fields |
| PDF access request form | PyPDF2 extracts text; scanned PDFs use Claude |
| Email thread (.txt) | Read directly, LLM parses natural language |
| JSON/YAML config | Read directly as text |
| Excel spreadsheet | Parsed into tab-separated text per sheet |
| Word document | Extracted from internal XML |
| Corrupt/unreadable file | Skipped gracefully — pipeline continues |

### Entity Resolution

The system maps shorthand database names to full infrastructure details:

```yaml
# entity_lookup/databases.yaml
DEVDB:
  hostname: dev-oracle-01
  environment: non-production
  technology: oracle

PRODDB:
  hostname: prod-oracle-02
  environment: production
  technology: oracle
```

When a user says "create user X in DEVDB", the resolver enriches it:
- `database: DEVDB` → `hostname: dev-oracle-01`, `environment: non-production`

If an alias maps to multiple hosts (e.g., "PROD"), it flags an ambiguity and requests clarification.

### Confidence Scoring

| Score | Meaning | System Action |
|-------|---------|---------------|
| 90-100 | All required fields present and resolved | Proceed to automation |
| 80-89 | Complete but with minor uncertainty | Proceed to automation |
| 50-79 | Missing fields or unresolved aliases | Request clarification |
| 10-49 | Significant information gaps | Request clarification |
| 10 | Unknown/unsupported intent | Route to manual queue |

Required fields by intent:
- **create_user**: username, database, role
- **reset_password**: username, database
- **grant_role**: username, database, role
- **unlock_user**: username, database

---

## Integration Guide

### Integrating with Your JSM Instance

1. **Create a service account** in your Jira instance with read access to the relevant project
2. **Generate an API token** at https://id.atlassian.com/manage-profile/security/api-tokens
3. **Configure the environment:**

```env
ADAPTER_MODE=live
JSM_BASE_URL=https://your-domain.atlassian.net
JSM_EMAIL=automation-svc@company.com
JSM_API_TOKEN=ATATT3xF...your-token
```

4. **Test with a real ticket:**
```bash
curl -X POST http://localhost:8000/api/process/YOUR-TICKET-123
```

### Integrating with AWS Bedrock

1. **Enable Bedrock model access** in your AWS console (Claude 3 Haiku or Sonnet)
2. **Configure AWS credentials** via one of:
   - `~/.aws/credentials` (CLI profile)
   - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
   - IAM instance role (recommended for production)
3. **Set the model:**

```env
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
AWS_REGION=us-east-1
```

### Adding New Database Aliases

Edit `entity_lookup/databases.yaml`:

```yaml
# Single-host alias
MY_NEW_DB:
  hostname: my-oracle-server.company.net
  environment: production
  technology: oracle

# Multi-host alias (triggers ambiguity → clarification)
SHARED_DB:
  - hostname: shared-01.company.net
    environment: production
    technology: oracle
    alias: SHARED_DB_01
  - hostname: shared-02.company.net
    environment: production
    technology: oracle
    alias: SHARED_DB_02
```

### Consuming the API from Downstream Systems

**Webhook integration example (Python):**

```python
import httpx

async def process_new_ticket(ticket_id: str) -> dict:
    async with httpx.AsyncClient(base_url="http://request-automation:8000") as client:
        resp = await client.post(f"/api/process/{ticket_id}")
        resp.raise_for_status()
        result = resp.json()

    if result["status"] == "normalized":
        # Ready for automation — forward to catalog resolver
        trigger_automation(result)
    elif result["status"] == "needs_clarification":
        # Ask user for missing info
        missing = result["confidence_metadata"]["missing_fields"]
        post_clarification_comment(ticket_id, missing)
    else:
        # Route to manual queue
        escalate_to_human(ticket_id, result["error"])

    return result
```

**Jenkins integration example:**

```groovy
pipeline {
    agent any
    stages {
        stage('Process Request') {
            steps {
                script {
                    def response = httpRequest(
                        httpMode: 'POST',
                        url: "http://request-automation:8000/api/process/${params.TICKET_ID}",
                        contentType: 'APPLICATION_JSON'
                    )
                    def result = readJSON text: response.content
                    if (result.status == 'normalized') {
                        env.DB_USERNAME = result.resolved_entities.username
                        env.DB_HOSTNAME = result.resolved_entities.hostname
                        env.DB_ROLE = result.resolved_entities.role
                        env.INTENT = result.intent
                    }
                }
            }
        }
    }
}
```

---

## Testing

### Run All Tests

```bash
cd request-automation
source .venv/bin/activate
pytest -v
```

### Run Human Scenario Tests

Simulates 21 real-world scenarios (all attachment types, edge cases):

```bash
python tests/human_scenario_tests.py
```

Generates a detailed report at `test-report.md`.

### Run E2E Demo

Processes a sample image through the full pipeline:

```bash
python tests/demo_ocr_e2e.py
```

Or test with your own file:

```bash
python tests/demo_ocr_e2e.py /path/to/your/screenshot.png
python tests/demo_ocr_e2e.py /path/to/your/error.log
python tests/demo_ocr_e2e.py /path/to/your/request.csv
```

### Mock Tickets for Testing

| Ticket ID | Scenario | Expected Result |
|-----------|----------|-----------------|
| `DB-DEMO` | Create user APP_READONLY in DEVDB | `normalized`, confidence 100 |
| `DB-MISSING` | Create user without specifying role | `needs_clarification` |
| `DB-AMBIG` | Reset password on ambiguous "PROD" | `needs_clarification` + ambiguities |
| `DB-UNSUPPORTED` | Resize tablespace (not automated) | `error`, intent unknown |
| `DB-OCR-FAIL` | Ticket with corrupt image attachment | `normalized` (graceful degradation) |

---

## Troubleshooting

### Common Issues

**"Live OCR not configured for POC"**
- You're running in `ADAPTER_MODE=live` without AWS credentials
- Fix: Set `ADAPTER_MODE=mock` or configure AWS credentials

**Empty entities / low confidence**
- The ticket text doesn't contain enough information
- Fix: Ensure tickets have clear request descriptions with explicit usernames and databases

**"bedrock-runtime" client error**
- AWS credentials not configured or Bedrock model access not enabled
- Fix: Run `aws sts get-caller-identity` to verify credentials; enable model access in Bedrock console

**Database not resolving (no hostname)**
- The database alias isn't in `entity_lookup/databases.yaml`
- Fix: Add the alias mapping to the lookup file

### Logs

The service outputs structured JSON logs:

```json
{"request_id": "...", "ticket_id": "DB-DEMO", "event": "intake_complete", "level": "info"}
{"request_id": "...", "intent": "create_user", "confidence": 100, "event": "intelligence_complete"}
```

Set `LOG_LEVEL=DEBUG` for verbose output including LLM prompt details.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Request Automation Service                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────┐     │
│  │ FastAPI  │───▶│  LangGraph   │───▶│  Normalized Request│     │
│  │ /process │    │  Pipeline    │    │  JSON Response     │     │
│  └──────────┘    └──────┬───────┘    └────────────────────┘     │
│                          │                                        │
│            ┌─────────────┼─────────────┐                         │
│            ▼             ▼             ▼                          │
│     ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│     │  Intake   │ │Intelligence│ │ Confidence│                   │
│     │  Node     │ │   Node     │ │  Scoring  │                   │
│     └─────┬─────┘ └─────┬─────┘ └───────────┘                   │
│           │              │                                        │
│     ┌─────▼─────┐  ┌────▼─────┐                                 │
│     │    OCR    │  │   LLM    │                                  │
│     │ Processor │  │  Client  │                                  │
│     └─────┬─────┘  └────┬─────┘                                 │
│           │              │                                        │
├───────────┼──────────────┼────────────────────────────────────────┤
│  External │              │  Services                              │
│           ▼              ▼                                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  JSM / Jira  │ │ AWS Bedrock  │ │ Entity Lookup│             │
│  │  (tickets)   │ │ (Claude LLM) │ │   (YAML)    │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Considerations

- API tokens and AWS credentials are loaded from environment variables — never commit `.env` files
- The service does not log request bodies containing identifiers (only character counts)
- Attachment content is processed in-memory and not persisted to disk
- All external API calls use TLS (HTTPS for JSM, HTTPS for Bedrock)
- Input validation rejects empty/malformed ticket IDs at the API boundary
- Unsupported file types are skipped (no arbitrary code execution risk)
