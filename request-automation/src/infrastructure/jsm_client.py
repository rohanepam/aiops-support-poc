from __future__ import annotations

from typing import Any

import httpx
import structlog

from domain.interfaces import JsmPort

logger = structlog.get_logger(__name__)

# Canned tickets for mock mode
MOCK_TICKETS: dict[str, dict[str, Any]] = {
    "DB-DEMO": {
        "ticket_id": "DB-DEMO",
        "summary": "Create Oracle user",
        "description": "Create user APP_READONLY in DEVDB, grant Read Only role.",
        "attachments": [],
        "comments": [],
    },
    "DB-AMBIG": {
        "ticket_id": "DB-AMBIG",
        "summary": "Reset password",
        "description": "Reset password for admin on PROD.",
        "attachments": [],
        "comments": [],
    },
    "DB-UNSUPPORTED": {
        "ticket_id": "DB-UNSUPPORTED",
        "summary": "Resize tablespace",
        "description": "Resize tablespace USERS to 50G on PRODDB.",
        "attachments": [],
        "comments": [],
    },
    "DB-MISSING": {
        "ticket_id": "DB-MISSING",
        "summary": "Incomplete Oracle access request",
        "description": "Create user APP01 in DEVDB.",
        "attachments": [],
        "comments": [],
    },
    "DB-OCR-FAIL": {
        "ticket_id": "DB-OCR-FAIL",
        "summary": "Oracle access request with screenshot",
        "description": "Create user APP_READONLY in DEVDB, grant Read Only role.",
        "attachments": ["https://example.invalid/bad.png"],
        "comments": [],
    },
}


class MockJsmClient(JsmPort):
    async def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = MOCK_TICKETS.get(ticket_id)
        if ticket is None:
            # Generic fallback so arbitrary IDs still exercise intake
            return {
                "ticket_id": ticket_id,
                "summary": ticket_id,
                "description": "",
                "attachments": [],
                "comments": [],
            }
        return dict(ticket)


class JsmClient(JsmPort):
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (email, api_token)

    async def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            issue_url = f"{self._base_url}/rest/api/3/issue/{ticket_id}"
            resp = await client.get(issue_url, auth=self._auth)
            resp.raise_for_status()
            data = resp.json()
            fields = data.get("fields", {})
            summary = fields.get("summary") or ""
            description = _adf_or_str(fields.get("description"))
            attachments = [
                a.get("content")
                for a in (fields.get("attachment") or [])
                if isinstance(a, dict) and a.get("content")
            ]
            comments_resp = await client.get(f"{issue_url}/comment", auth=self._auth)
            comments_resp.raise_for_status()
            comments = [
                _adf_or_str(c.get("body"))
                for c in (comments_resp.json().get("comments") or [])
                if isinstance(c, dict)
            ]
            logger.info("jsm_ticket_fetched", ticket_id=ticket_id, attachment_count=len(attachments))
            return {
                "ticket_id": ticket_id,
                "summary": summary,
                "description": description,
                "attachments": attachments,
                "comments": comments,
            }


def _adf_or_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Minimal ADF text flatten
        parts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "text":
                    parts.append(str(node.get("text", "")))
                for child in node.get("content", []) or []:
                    walk(child)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(value)
        return " ".join(parts).strip()
    return str(value)
