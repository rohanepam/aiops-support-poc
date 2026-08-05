# API Reference

Request Automation API — Request Intelligence (Flow 2)

**Base URL:** `http://localhost:8000`  
**Content-Type:** `application/json`

---

## Endpoints

### GET /health

Health check endpoint for load balancers and monitoring.

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Service is healthy |

---

### POST /api/process/{ticket_id}

Process a JSM ticket through the full Request Intelligence pipeline: intake (fetch ticket + OCR attachments) → intelligence (classify intent + extract entities) → normalize.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticket_id` | string | Yes | The JSM/Jira ticket ID (e.g., `DB-1234`) |

**Request:**

No body required. The system fetches ticket data from JSM using the ticket ID.

```bash
curl -X POST http://localhost:8000/api/process/DB-DEMO
```

**Response — Normalized Request:**

```json
{
  "request_id": "uuid-v4",
  "ticket_id": "DB-DEMO",
  "layer1": "database",
  "layer2": "oracle",
  "layer3": "create_user",
  "intent": "create_user",
  "intent_message": null,
  "resolved_entities": {
    "username": "APP_READONLY",
    "database": "DEVDB",
    "role": "Read Only",
    "environment": "non-production",
    "hostname": "dev-oracle-01",
    "technology": "oracle",
    "schema_name": null,
    "tablespace": null,
    "tenant": null
  },
  "confidence": 100,
  "confidence_metadata": {
    "missing_fields": [],
    "ambiguities": []
  },
  "status": "normalized",
  "error": null
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique UUID for this processing run |
| `ticket_id` | string | The original ticket ID |
| `layer1` | string | Domain classification (e.g., `database`) |
| `layer2` | string \| null | Technology classification (e.g., `oracle`) |
| `layer3` | string \| null | Same as intent (for catalog matching) |
| `intent` | string | Detected intent: `create_user`, `reset_password`, `grant_role`, `unlock_user`, `unknown` |
| `intent_message` | string \| null | Explanation when intent is `unknown` |
| `resolved_entities` | object | Extracted and resolved entity fields |
| `confidence` | integer | Confidence score 0-100 |
| `confidence_metadata` | object | Details about missing/ambiguous fields |
| `status` | string | Pipeline outcome (see below) |
| `error` | object \| null | Error details if processing failed |

**Status Values:**

| Status | Meaning | Action |
|--------|---------|--------|
| `normalized` | Fully resolved, automation-ready | Proceed to catalog matching |
| `needs_clarification` | Missing fields or ambiguous entities | Request info from user |
| `error` | Unsupported intent or processing failure | Route to manual handling |

**Confidence Score:**

| Range | Interpretation |
|-------|---------------|
| 90-100 | Fully resolved, all entities matched |
| 80-89 | Resolved, minor uncertainty |
| 50-79 | Incomplete — missing fields or unresolved DB alias |
| 10-49 | Very incomplete — multiple missing fields |
| 10 | Unknown/unsupported intent |

**Ambiguity Object:**

When a database alias maps to multiple hosts:
```json
{
  "field": "database",
  "raw_value": "PROD",
  "candidates": [
    {"hostname": "prod-oracle-01", "environment": "production", "alias": "PROD1"},
    {"hostname": "prod-oracle-02", "environment": "production", "alias": "PROD2"}
  ]
}
```

**Error Object:**

```json
{
  "error_code": "unsupported_intent",
  "message": "Unsupported request: tablespace operations are not automated",
  "details": {}
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Request processed (check `status` field for outcome) |
| 400 | Invalid input (empty ticket_id) |
| 500 | Internal processing failure |

---

## Supported Intents

| Intent | Description | Required Entities |
|--------|-------------|-------------------|
| `create_user` | Create a new database user account | username, database, role |
| `reset_password` | Reset user password | username, database |
| `grant_role` | Grant a role to an existing user | username, database, role |
| `unlock_user` | Unlock a locked user account | username, database |
| `unknown` | Unsupported or unrecognizable request | — |

---

## Attachment Processing

The intake step automatically processes ticket attachments. Supported formats:

| Format | Extensions | Processing Method |
|--------|-----------|-------------------|
| Images | .png, .jpg, .jpeg, .gif, .webp, .bmp | Claude Vision API (visual OCR) |
| PDF (text-based) | .pdf | PyPDF2 text extraction |
| PDF (scanned) | .pdf | Claude Document API |
| Log files | .log, .txt, .conf, .ini, .cfg | Direct text read |
| Spreadsheets | .csv, .tsv | Direct text read |
| Data formats | .json, .xml, .yaml, .yml | Direct text read |
| Excel | .xlsx, .xls | openpyxl structured parsing |
| Word | .docx | XML extraction |
| Word (legacy) | .doc, .rtf | Claude Document API |

Attachments that fail OCR are skipped gracefully — the pipeline continues using ticket text fields.

---

## Error Handling

The API uses graceful degradation:

1. **OCR failure** — Attachment processing fails silently; pipeline continues with ticket text
2. **LLM failure** — Retries up to 2 times; returns error status on exhaustion
3. **Unknown ticket** — Returns `intent=unknown` with error, never crashes
4. **Invalid input** — Returns HTTP 400 for empty/whitespace ticket IDs
5. **Internal error** — Returns HTTP 500 with generic message (no sensitive info leaked)

---

## Rate Limits & Performance

| Metric | Value |
|--------|-------|
| Typical response time (mock) | < 10ms |
| Typical response time (live, no attachments) | 1-3s |
| Typical response time (live, with image OCR) | 3-8s |
| Max attachment size | Limited by Claude API (20MB images) |
| Max text extraction | 15,000 characters (truncated beyond) |
| Concurrent requests | Limited by uvicorn workers |

---

## Examples

### Create User (happy path)
```bash
curl -s -X POST http://localhost:8000/api/process/DB-DEMO | jq .
```

### Ambiguous Database
```bash
curl -s -X POST http://localhost:8000/api/process/DB-AMBIG | jq .status
# "needs_clarification"
```

### Unsupported Request
```bash
curl -s -X POST http://localhost:8000/api/process/DB-UNSUPPORTED | jq .error
# {"error_code": "unsupported_intent", "message": "..."}
```

### OCR Failure (graceful)
```bash
curl -s -X POST http://localhost:8000/api/process/DB-OCR-FAIL | jq .status
# "normalized" — pipeline continues from ticket text
```
