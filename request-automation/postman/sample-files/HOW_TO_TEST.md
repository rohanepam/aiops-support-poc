# Sample Files for Postman Testing

Use these files with the `POST /api/process-attachment` endpoint.

## How to use in Postman

1. Start the server: `uvicorn api.app:app --reload --port 8000`
2. Open Postman → `POST http://localhost:8000/api/process-attachment`
3. Body tab → select **form-data**
4. Add key `file` → change type to **File** → select one of these files
5. Add key `summary` → type a short description (see suggestions below)
6. Click **Send**

## Files & Expected Results

| File | Type | Summary to use | Expected Intent | Expected Result |
|------|------|----------------|-----------------|-----------------|
| `unlock_account.log` | Log | `Unlock user APP_BATCH_01 in PRODDB` | unlock_user | confidence: 100%, status: normalized |
| `password_expired.log` | Log | `Reset password for REPORT_SVC` | reset_password | confidence: 100%, status: normalized |
| `create_user_request.csv` | CSV | `Create users from attached CSV` | create_user | Shows full CSV content |
| `grant_role_webhook.json` | JSON | `Grant role from automation` | grant_role | Shows JSON payload |
| `create_user_form.txt` | Text | `Create user per attached form` | create_user | Extracts all form fields |
| `unlock_request_email.txt` | Text | `Unlock user per email request` | unlock_user | Extracts from email body |
| `provision_config.yaml` | YAML | `Create user from config` | create_user | Shows YAML content |
| `create_user_screenshot.png` | Image | `Create user per screenshot` | create_user | OCR extraction (mock/live) |

## What to look for in the response

```json
{
  "file": "unlock_account.log",        ← your uploaded file
  "file_type": ".log",
  "processing": {
    "extracted_text": "...",            ← THE ACTUAL CONTENT READ FROM YOUR FILE
    "extracted_chars": 578,
    "ocr_error": null                   ← null = success, string = what went wrong
  },
  "classification": {
    "intent": "unlock_user",            ← what the system thinks you want
    "layer1": "database",
    "layer2": "oracle"
  },
  "entities": {
    "raw_extracted": {
      "username": "APP_BATCH_01",       ← extracted from your file
      "database": "PRODDB"
    },
    "resolved": {
      "hostname": "prod-oracle-02",     ← resolved from entity lookup
      "environment": "production"
    }
  },
  "confidence": 100,                    ← 0-100 score
  "status": "normalized"                ← ready for automation
}
```

## Tips

- **Text files** (.log, .csv, .txt, .json, .yaml) are read directly — no AI needed
- **Images** (.png, .jpg) go through Claude Vision in live mode; in mock mode you get generic OCR text
- The `summary` and `description` fields help the LLM classify intent (especially for structured files like CSV/JSON where the intent isn't in natural language)
- Try editing the files to change usernames/databases and see how the pipeline responds
