from __future__ import annotations

import structlog

from domain.interfaces import OcrPort

logger = structlog.get_logger(__name__)

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
EXCEL_EXTS = (".xlsx", ".xls")


class MockOcrProcessor(OcrPort):
    async def extract_text(self, attachment_url: str) -> str:
        lower = attachment_url.lower()
        if "bad" in lower or "fail" in lower:
            raise RuntimeError("OCR failed: unreadable image")
        if lower.endswith(EXCEL_EXTS):
            return "excel:sheet1:username=APP_X"
        if any(lower.endswith(ext) for ext in IMAGE_EXTS) or lower.endswith(".png"):
            return "ocr: Create user from screenshot"
        logger.warning("ocr_skip_unsupported", url_suffix=lower[-12:])
        return ""


class OcrProcessor(OcrPort):
    """Placeholder live OCR — POC uses mock; interface ready for OSS OCR swap-in."""

    async def extract_text(self, attachment_url: str) -> str:
        # Live OCR deferred; keep interface for AD-2
        logger.warning("ocr_live_not_configured", hint="use ADAPTER_MODE=mock")
        raise RuntimeError("Live OCR not configured for POC")
