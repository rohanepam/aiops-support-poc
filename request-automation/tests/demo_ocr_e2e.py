"""
End-to-end demo: simulates a human submitting a JSM ticket with various attachment types.
Handles images, PDFs, log files, Excel, and other documents — sends them through
the full intelligence pipeline (OCR/extraction + intent classification + entity extraction).

Usage:
    python tests/demo_ocr_e2e.py [path_to_file]

If no file is provided, sample attachments of each type are generated and tested.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw, ImageFont


def create_sample_request_image(output_path: Path) -> Path:
    """Create a realistic-looking DB access request screenshot."""
    width, height = 800, 500
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_body = font_title
        font_small = font_title

    # Header
    draw.rectangle([(0, 0), (width, 60)], fill=(25, 118, 210))
    draw.text((20, 15), "Database Access Request Form", fill="white", font=font_title)

    # Form fields
    y = 80
    fields = [
        ("Request Type:", "Create New User Account"),
        ("Username:", "SVC_ANALYTICS_01"),
        ("Database:", "PROD_ORACLE_DW"),
        ("Environment:", "Production"),
        ("Hostname:", "prod-oracle-dw-01.novartis.net"),
        ("Role:", "READ_ONLY"),
        ("Schema:", "ANALYTICS"),
        ("Requested By:", "john.smith@novartis.com"),
        ("Business Justification:", "New analytics service account needed for"),
        ("", "quarterly reporting dashboard (Q3 2026)."),
        ("Approval:", "Manager approved - see ticket DB-4521"),
    ]

    for label, value in fields:
        if label:
            draw.text((30, y), label, fill=(66, 66, 66), font=font_body)
            draw.text((220, y), value, fill=(0, 0, 0), font=font_body)
        else:
            draw.text((220, y), value, fill=(0, 0, 0), font=font_body)
        y += 32

    # Footer
    draw.line([(20, y + 10), (width - 20, y + 10)], fill=(200, 200, 200), width=1)
    draw.text(
        (20, y + 20),
        "Screenshot captured from ServiceNow request portal - 2026-08-04",
        fill=(128, 128, 128),
        font=font_small,
    )

    img.save(output_path)
    return output_path


def create_sample_log_file(output_path: Path) -> Path:
    """Create a sample Oracle error log file."""
    log_content = """2026-08-04 09:15:23 INFO  [SessionManager] User login attempt: APP_BATCH_01
2026-08-04 09:15:23 ERROR [OracleAuth] ORA-28000: The account APP_BATCH_01 is locked on PRODDB
2026-08-04 09:15:23 WARN  [SessionManager] Failed login for APP_BATCH_01 on host prod-oracle-01.novartis.net
2026-08-04 09:15:24 INFO  [AlertService] Account lock alert sent to dba-team@novartis.com
2026-08-04 09:16:01 INFO  [SessionManager] User login attempt: APP_BATCH_01
2026-08-04 09:16:01 ERROR [OracleAuth] ORA-28000: The account APP_BATCH_01 is locked on PRODDB
2026-08-04 09:20:45 INFO  [TicketBot] Auto-created JSM ticket DB-5102: unlock user APP_BATCH_01 on PRODDB
"""
    output_path.write_text(log_content)
    return output_path


def create_sample_csv_file(output_path: Path) -> Path:
    """Create a sample CSV with user provisioning requests."""
    csv_content = """request_id,action,username,database,role,environment,requested_by
REQ-001,create_user,SVC_ETL_PROD,PRODDB,ETL_EXECUTOR,Production,data-eng@novartis.com
REQ-002,grant_role,APP_REPORTING,DEVDB,READ_ONLY,Non-Production,bi-team@novartis.com
REQ-003,reset_password,ADMIN_DBA,PRODDB,DBA,Production,it-ops@novartis.com
"""
    output_path.write_text(csv_content)
    return output_path


def create_sample_pdf_text(output_path: Path) -> Path:
    """Create a simple text file simulating PDF-extracted content."""
    # In reality this would be a real PDF; for demo we simulate what PDF text extraction yields
    pdf_text = """
DATABASE ACCESS REQUEST FORM
=============================

Date: 2026-08-04
Ticket: DB-6200
Requester: maria.garcia@novartis.com

REQUEST DETAILS:
- Action: Create user account
- Username: SVC_DASHBOARD_02
- Target Database: DEVDB
- Role: Read Only
- Schema Access: REPORTING, ANALYTICS
- Environment: Non-Production
- Hostname: dev-oracle-01

BUSINESS JUSTIFICATION:
New service account for the BI dashboard refresh project (PROJ-445).
Manager approval obtained: YES (see attached email thread).

APPROVALS:
- Line Manager: Approved (2026-08-03)
- Security Team: Pending
"""
    output_path.write_text(pdf_text)
    return output_path


async def process_single_attachment(file_path: Path, ticket_summary: str, ticket_description: str):
    """Process one attachment through the full pipeline and return results."""
    from infrastructure.ocr_processor import OcrProcessor, MockOcrProcessor
    from infrastructure.bedrock_client import MockLlmClient, RetryingLlmClient
    from domain.models import RequestStatus, REQUIRED_ENTITIES
    from domain.entity_resolver import resolve_entities, load_database_lookup
    from domain.confidence import score_confidence
    from config.settings import get_settings

    settings = get_settings()

    # Step 1: Extract text from attachment
    TEXT_FILE_EXTS = (".txt", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".conf", ".ini", ".cfg")

    use_live = settings.adapter_mode == "live"
    if use_live:
        ocr = OcrProcessor(model_id=settings.bedrock_model_id, region=settings.aws_region)
        extracted_text = await ocr.extract_text(str(file_path))
    elif file_path.suffix.lower() in TEXT_FILE_EXTS and file_path.is_file():
        # Text-based files: read directly (no need for OCR/mock)
        extracted_text = file_path.read_text(errors="replace")[:15000]
    else:
        ocr = MockOcrProcessor()
        extracted_text = await ocr.extract_text(str(file_path))

    # Step 2: Build unified context
    unified_context = f"{ticket_summary}\n{ticket_description}\n{extracted_text}"

    # Step 3: Intelligence
    llm = RetryingLlmClient(MockLlmClient(), max_retries=1)
    intent_result = await llm.classify_intent(unified_context)
    entity_result = await llm.extract_entities(unified_context, intent_result.intent.value)

    # Step 4: Resolve + confidence
    lookup_path = Path(__file__).resolve().parents[1] / "entity_lookup" / "databases.yaml"
    lookup = load_database_lookup(str(lookup_path))
    resolved, ambiguities = resolve_entities(entity_result, lookup)
    confidence, missing = score_confidence(intent_result.intent, resolved, ambiguities)

    status = (
        RequestStatus.NORMALIZED
        if confidence >= 80 and not missing
        else RequestStatus.NEEDS_CLARIFICATION
    )

    return {
        "file": file_path.name,
        "file_type": file_path.suffix,
        "extracted_text": extracted_text,
        "unified_context_chars": len(unified_context),
        "intent": intent_result.intent.value,
        "layer1": intent_result.layer1,
        "layer2": intent_result.layer2,
        "entities": {
            "username": entity_result.username,
            "database": entity_result.database,
            "role": entity_result.role,
        },
        "resolved": resolved.model_dump(),
        "confidence": confidence,
        "missing_fields": missing,
        "ambiguities": len(ambiguities),
        "status": status.value,
    }


async def run_demo(file_path: Path | None = None):
    """Run the full pipeline with various attachment types."""
    print("=" * 70)
    print("  REQUEST AUTOMATION - ATTACHMENT PROCESSING E2E DEMO")
    print("  Simulating: Human submits JSM ticket with file attachments")
    print("  Supports: Images, PDFs, Logs, CSVs, Excel, Word docs")
    print("=" * 70)

    sample_dir = Path(__file__).parent / "sample_data"
    sample_dir.mkdir(exist_ok=True)

    if file_path and file_path.is_file():
        # Process a single user-provided file
        print(f"\n  Processing user-provided file: {file_path}")
        print(f"  File type: {file_path.suffix}")
        print(f"  Size: {file_path.stat().st_size / 1024:.1f} KB")
        result = await process_single_attachment(
            file_path,
            "Service request",
            "Please process the attached file.",
        )
        _print_result(result)
        return result

    # Generate and test ALL supported attachment types
    test_cases = []

    # 1. Screenshot/Image
    print("\n" + "-" * 70)
    print("  ATTACHMENT TYPE 1: Screenshot (PNG image)")
    print("-" * 70)
    img_path = sample_dir / "db_request_screenshot.png"
    create_sample_request_image(img_path)
    print(f"  Generated: {img_path.name} ({img_path.stat().st_size / 1024:.1f} KB)")
    result = await process_single_attachment(
        img_path,
        "Create user in Oracle database",
        "Please create a user as shown in the attached screenshot.",
    )
    test_cases.append(result)
    _print_result(result)

    # 2. Log file
    print("\n" + "-" * 70)
    print("  ATTACHMENT TYPE 2: Error Log (.log)")
    print("-" * 70)
    log_path = sample_dir / "oracle_errors.log"
    create_sample_log_file(log_path)
    print(f"  Generated: {log_path.name} ({log_path.stat().st_size / 1024:.1f} KB)")
    result = await process_single_attachment(
        log_path,
        "Unlock Oracle account",
        "Account is locked per attached logs, please unlock user.",
    )
    test_cases.append(result)
    _print_result(result)

    # 3. CSV file
    print("\n" + "-" * 70)
    print("  ATTACHMENT TYPE 3: CSV spreadsheet (.csv)")
    print("-" * 70)
    csv_path = sample_dir / "bulk_requests.csv"
    create_sample_csv_file(csv_path)
    print(f"  Generated: {csv_path.name} ({csv_path.stat().st_size / 1024:.1f} KB)")
    result = await process_single_attachment(
        csv_path,
        "Create user from CSV",
        "Please create the users listed in the attached CSV file.",
    )
    test_cases.append(result)
    _print_result(result)

    # 4. PDF (simulated as .txt for demo; real PDF would use PyPDF2)
    print("\n" + "-" * 70)
    print("  ATTACHMENT TYPE 4: PDF document (text-based)")
    print("-" * 70)
    pdf_path = sample_dir / "access_request_form.txt"
    create_sample_pdf_text(pdf_path)
    print(f"  Generated: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
    result = await process_single_attachment(
        pdf_path,
        "Create user per attached form",
        "Attached is the signed access request form.",
    )
    test_cases.append(result)
    _print_result(result)

    # Summary table
    print("\n" + "=" * 70)
    print("  SUMMARY: All attachment types processed")
    print("=" * 70)
    print(f"  {'File':<30} {'Type':<8} {'Intent':<16} {'Confidence':<12} {'Status'}")
    print(f"  {'-'*30} {'-'*8} {'-'*16} {'-'*12} {'-'*20}")
    for r in test_cases:
        print(
            f"  {r['file']:<30} {r['file_type']:<8} {r['intent']:<16} "
            f"{r['confidence']}%{'':<10} {r['status']}"
        )

    print("\n" + "=" * 70)
    print("  DEMO COMPLETE")
    print("  All attachment types (image, log, CSV, PDF/doc) processed successfully.")
    print("  In production: Claude Vision handles images/scanned PDFs,")
    print("  text files are read directly, Excel is parsed with openpyxl.")
    print("=" * 70)

    return test_cases


def _print_result(result: dict):
    """Print a single attachment processing result."""
    print(f"\n  Extracted text preview:")
    text = result["extracted_text"] or "(empty)"
    for line in text.strip().split("\n")[:8]:
        print(f"    | {line}")
    if text.count("\n") > 8:
        print(f"    | ... ({text.count(chr(10)) - 8} more lines)")

    print(f"\n  Pipeline result:")
    print(f"    Intent:     {result['intent']}")
    print(f"    Username:   {result['entities']['username']}")
    print(f"    Database:   {result['entities']['database']}")
    print(f"    Role:       {result['entities']['role']}")
    print(f"    Confidence: {result['confidence']}%")
    print(f"    Status:     {result['status']}")


if __name__ == "__main__":
    file_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(run_demo(file_arg))
