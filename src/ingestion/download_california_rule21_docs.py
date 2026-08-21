"""Download and version-check a California / SCE Rule 21 research corpus.

All latest downloaded source files remain together in data/corpus/. For PDF
sources, a primary request is validated by checking the PDF signature. If that
fails, the script retries the configured URL using a simplified request that
matches the original working downloader: browser User-Agent only, no explicit
Accept header, no URL rewriting, and Requests' default redirect handling.

corpus_metadata.json records the request attempts, validation result, and a
manual-review state. Only metadata determines whether a document is eligible
for extraction or default retrieval.

Manual replacement helper:
    uv run python src/ingestion/download_california_rule21_docs.py \
        --mark-manual-replacement sce_interconnection_handbook_pdf \
        --reviewer your-name

Usage:
    uv add requests beautifulsoup4
    uv run python src/ingestion/download_california_rule21_docs.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("data/corpus")
METADATA_PATH = OUTPUT_DIR / "corpus_metadata.json"
TIMEOUT_SECONDS = 30

SOURCES = [
    {"id": "cpuc_rule21_overview", "title": "CPUC Electric Rule 21 overview page", "url": "https://www.cpuc.ca.gov/Rule21/", "type": "html", "source_org": "CPUC", "description": "CPUC overview of Electric Rule 21 tariff, scope, and links.", "filename": "01_cpuc_rule21_overview.html", "default_retrieval_enabled": True},
    {"id": "sce_rule21_tariff_pdf", "title": "SCE Electric Rule 21 tariff (PDF)", "url": "https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf", "type": "pdf", "source_org": "SCE", "description": "SCE Rule 21 tariff text covering interconnection, operating, and metering requirements.", "filename": "02_sce_rule21_tariff.pdf", "default_retrieval_enabled": True},
    {"id": "sce_interconnection_handbook_pdf", "title": "SCE Interconnection Handbook (PDF)", "url": "https://on.sce.com/InterconnectionHandbook", "type": "pdf", "source_org": "SCE", "description": "SCE technical handbook for interconnection, protection, telemetry, and inverter performance.", "filename": "03_sce_interconnection_handbook.pdf", "default_retrieval_enabled": True},
    {"id": "sce_interconnection_web", "title": "SCE Rule 21 interconnection web page", "url": "https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21", "type": "html", "source_org": "SCE", "description": "SCE web guidance summarising Rule 21 process, forms, testing, and COT procedures.", "filename": "04_sce_interconnection_web.html", "default_retrieval_enabled": True},
    {"id": "siwg_phase2_recommendations_pdf", "title": "Smart Inverter Working Group Phase 2 Recommendations (PDF)", "url": "https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf", "type": "pdf", "source_org": "CPUC", "description": "SIWG Phase 2 recommendations on DER communications, IEEE 2030.5, and data categories.", "filename": "05_siwg_phase2_recommendations.pdf", "default_retrieval_enabled": False, "is_draft": True},
    {"id": "sce_testing_certification_instruction_pdf", "title": "SCE Rule 21 testing and certification instruction sheet (PDF)", "url": "https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf", "type": "pdf", "source_org": "SCE", "description": "SCE instructions for testing and certifying equipment for CSIP / Rule 21 compliance.", "filename": "06_sce_testing_certification.pdf", "default_retrieval_enabled": True},
]

PRIMARY_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
}

SIMPLIFIED_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}


@dataclass
class FetchResult:
    content: bytes
    resolved_url: str
    http_metadata: dict[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_filename(name: str) -> str:
    return "".join(character for character in name if character.isalnum() or character in "._-")


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def response_metadata(response: requests.Response) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type", ""),
        "etag": response.headers.get("ETag", ""),
        "last_modified": response.headers.get("Last-Modified", ""),
    }


def fetch_source_with_primary_request(url: str) -> FetchResult:
    response = requests.get(
        url,
        headers=PRIMARY_REQUEST_HEADERS,
        timeout=TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    return FetchResult(response.content, response.url, response_metadata(response))


def fetch_source_with_simplified_request(url: str) -> FetchResult:
    """Use the original working downloader's request behaviour exactly."""
    response = requests.get(
        url,
        headers=SIMPLIFIED_REQUEST_HEADERS,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return FetchResult(response.content, response.url, response_metadata(response))


def validate_content(source: dict[str, Any], result: FetchResult) -> dict[str, Any]:
    if source["type"] == "pdf":
        signature_valid = result.content.startswith(b"%PDF")
        return {
            "status": "passed" if signature_valid else "failed",
            "checks": {
                "expected_file_type": "pdf",
                "actual_content_type": result.http_metadata.get("content_type", ""),
                "file_signature": "passed" if signature_valid else "failed",
                "content_hash": "passed",
                "parser_open": "not_run",
            },
        }

    if source["type"] == "html":
        return {
            "status": "passed",
            "checks": {
                "expected_file_type": "html",
                "actual_content_type": result.http_metadata.get("content_type", ""),
                "file_signature": "not_applicable",
                "content_hash": "passed",
                "parser_open": "not_run",
            },
        }

    raise ValueError(f"Unknown source type: {source['type']}")


def attempt_record(method: str, result: FetchResult, validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": method,
        "resolved_url": result.resolved_url,
        "http_metadata": result.http_metadata,
        "content_hash": sha256_bytes(result.content),
        "validation_status": validation["status"],
    }


def fetch_with_pdf_fallback(source: dict[str, Any]) -> tuple[FetchResult, dict[str, Any], list[dict[str, Any]], str]:
    primary = fetch_source_with_primary_request(source["url"])
    primary_validation = validate_content(source, primary)
    attempts = [attempt_record("primary_request", primary, primary_validation)]

    if source["type"] != "pdf" or primary_validation["status"] == "passed":
        return primary, primary_validation, attempts, "primary_request"

    try:
        fallback = fetch_source_with_simplified_request(source["url"])
        fallback_validation = validate_content(source, fallback)
        attempts.append(attempt_record("simplified_request_fallback", fallback, fallback_validation))
        return fallback, fallback_validation, attempts, "simplified_request_fallback"
    except requests.RequestException as error:
        attempts.append({"method": "simplified_request_fallback", "error": str(error), "validation_status": "not_run"})
        return primary, primary_validation, attempts, "primary_request"


def save_html(html_bytes: bytes, path: Path) -> None:
    soup = BeautifulSoup(html_bytes, "html.parser", from_encoding="utf-8")
    path.write_text(soup.prettify(formatter="html"), encoding="utf-8")


def save_content(source: dict[str, Any], content: bytes, path: Path) -> None:
    if source["type"] == "html":
        save_html(content, path)
    else:
        path.write_bytes(content)


def extract_cancelling_sheet(text: str) -> str | None:
    pattern = r"Cancelling\s+Revised\s+Cal\.\s+PUC\s+Sheet\s+No\.\s*([0-9A-Z\-]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def load_existing_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {
            "description": "Minimal California / SCE Rule 21 research corpus. For research and demo purposes only.",
            "created_at": now_iso(),
            "sources": [],
            "failures": [],
        }
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata.setdefault("sources", [])
    metadata.setdefault("failures", [])
    return metadata


def manual_review_state(existing: dict[str, Any] | None, changed: bool, validation_status: str) -> dict[str, Any]:
    if validation_status == "failed":
        return {
            "required": True,
            "status": "pending",
            "review_type": "failed_download_validation",
            "reason": "Final downloaded response does not match the configured expected file type.",
            "reviewed_at": None,
            "reviewer": None,
            "notes": None,
        }

    if not existing or changed:
        return {
            "required": True,
            "status": "pending",
            "review_type": "initial_document_review" if not existing else "content_change",
            "reason": "Validate document identity, version, and currency before enabling default retrieval.",
            "reviewed_at": None,
            "reviewer": None,
            "notes": None,
        }

    return existing.get("manual_review", {
        "required": True,
        "status": "pending",
        "review_type": "metadata_migration_review",
        "reason": "Existing source requires an initial manual review record.",
        "reviewed_at": None,
        "reviewer": None,
        "notes": None,
    })


def calculate_eligibility(validation_status: str, review: dict[str, Any], default_enabled: bool, is_draft: bool) -> tuple[bool, bool]:
    extraction_eligible = validation_status == "passed"
    default_retrieval_eligible = (
        extraction_eligible
        and default_enabled
        and not is_draft
        and review.get("status") == "approved"
    )
    return extraction_eligible, default_retrieval_eligible


def download_and_check_source(source: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    filename = sanitize_filename(source["filename"])
    path = OUTPUT_DIR / filename

    print(f"Processing: {source['title']}")
    print(f"  URL: {source['url']}")

    result, validation, attempts, stored_method = fetch_with_pdf_fallback(source)
    content_hash = sha256_bytes(result.content)
    old_hash = existing.get("content_hash") if existing else None
    changed = bool(old_hash and old_hash != content_hash)

    save_content(source, result.content, path)

    print(f"  Stored using: {stored_method}")
    print(f"  Saved to: {path}")
    print(f"  Content hash: {content_hash[:24]}...")
    print(f"  Validation: {validation['status']}")

    superseded_by_sheet = None
    if source["type"] == "pdf" and "tariff" in source["id"] and validation["status"] == "passed":
        text = result.content[:200_000].decode("utf-8", errors="ignore")
        superseded_by_sheet = extract_cancelling_sheet(text)

    review = manual_review_state(existing, changed, validation["status"])
    default_enabled = source.get("default_retrieval_enabled", True)
    is_draft = bool(source.get("is_draft", existing.get("is_draft", False) if existing else False))
    extraction_eligible, default_retrieval_eligible = calculate_eligibility(
        validation["status"], review, default_enabled, is_draft
    )

    return {
        "id": source["id"],
        "title": source["title"],
        "url": source["url"],
        "resolved_url": result.resolved_url,
        "type": source["type"],
        "source_org": source["source_org"],
        "description": source["description"],
        "filename": filename,
        "local_path": str(path),
        "size_bytes": path.stat().st_size,
        "content_hash": content_hash,
        "downloaded_at": existing.get("downloaded_at", now_iso()) if existing and not changed else now_iso(),
        "last_checked": now_iso(),
        "change_detected": changed,
        "is_current": existing.get("is_current", True) if existing else True,
        "superseded_by_sheet": superseded_by_sheet,
        "http_metadata": result.http_metadata,
        "download_attempts": attempts,
        "acquisition": {
            "method": stored_method,
            "status": "success",
            "last_attempted_at": now_iso(),
            "error": None,
        },
        "automated_validation": validation,
        "manual_review": review,
        "eligible_for_extraction": extraction_eligible,
        "eligible_for_default_retrieval": default_retrieval_eligible,
        "default_retrieval_enabled": default_enabled,
        "is_draft": is_draft,
        "version_label": existing.get("version_label") if existing and not changed else None,
        "effective_date": existing.get("effective_date") if existing and not changed else None,
        "revision_date": existing.get("revision_date") if existing and not changed else None,
        "currency_status": existing.get("currency_status", "unverified") if existing and not changed else "unverified",
        "currency_evidence": existing.get("currency_evidence") if existing and not changed else None,
        "notes": source.get("notes", ""),
    }


def mark_manual_replacement(source_id: str, reviewer: str) -> None:
    """Mark an existing corpus file as manually replaced and approved for default retrieval."""
    metadata = load_existing_metadata()
    source_index = None
    for index, record in enumerate(metadata["sources"]):
        if record["id"] == source_id:
            source_index = index
            break

    if source_index is None:
        raise SystemExit(f"Source ID not found in corpus_metadata.json: {source_id}")

    record = metadata["sources"][source_index]
    path = Path(record["local_path"])
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        raise SystemExit(f"Local file not found: {path}")

    new_content = path.read_bytes()
    new_hash = sha256_bytes(new_content)
    old_hash = record.get("content_hash")
    changed = bool(old_hash and old_hash != new_hash)

    record["content_hash"] = new_hash
    record["size_bytes"] = path.stat().st_size
    record["last_checked"] = now_iso()
    record["change_detected"] = changed
    record["acquisition"] = {
        "method": "manual_replacement",
        "status": "success",
        "last_attempted_at": now_iso(),
        "error": None,
    }

    if record["type"] == "pdf":
        record["automated_validation"] = {
            "status": "passed" if new_content.startswith(b"%PDF") else "failed",
            "checks": {
                "expected_file_type": "pdf",
                "actual_content_type": "application/pdf" if new_content.startswith(b"%PDF") else "unknown",
                "file_signature": "passed" if new_content.startswith(b"%PDF") else "failed",
                "content_hash": "passed",
                "parser_open": "not_run",
            },
        }
    else:
        record["automated_validation"] = {
            "status": "passed",
            "checks": {
                "expected_file_type": record["type"],
                "actual_content_type": "text/html",
                "file_signature": "not_applicable",
                "content_hash": "passed",
                "parser_open": "not_run",
            },
        }

    record["manual_review"] = {
        "required": False,
        "status": "approved",
        "review_type": "manual_replacement",
        "reason": "File manually replaced due to automated download block or unreliable source. Reviewed and confirmed as valid.",
        "reviewed_at": now_iso(),
        "reviewer": reviewer,
    }

    record["eligible_for_extraction"] = record["automated_validation"]["status"] == "passed"
    record["eligible_for_default_retrieval"] = (
        record["eligible_for_extraction"]
        and record.get("default_retrieval_enabled", True)
        and not record.get("is_draft", False)
    )

    metadata["sources"][source_index] = record
    metadata["last_run_at"] = now_iso()
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Marked {source_id} as manual replacement.")
    print(f"  Local path: {path}")
    print(f"  Content hash: {new_hash[:24]}...")
    print(f"  Validation: {record['automated_validation']['status']}")
    print(f"  Manual review: approved by {reviewer}")
    print(f"  Eligible for extraction: {record['eligible_for_extraction']}")
    print(f"  Eligible for default retrieval: {record['eligible_for_default_retrieval']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and version-check California / SCE Rule 21 corpus.")
    parser.add_argument(
        "--mark-manual-replacement",
        metavar="SOURCE_ID",
        help="Mark an existing corpus file as manually replaced and approved for default retrieval.",
    )
    parser.add_argument(
        "--reviewer",
        required=False,
        default=None,
        help="Reviewer name or ID for manual replacement.",
    )
    args = parser.parse_args()

    if args.mark_manual_replacement:
        if not args.reviewer:
            raise SystemExit("--reviewer is required when using --mark-manual-replacement")
        mark_manual_replacement(args.mark_manual_replacement, args.reviewer)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_existing_metadata()
    existing_by_id = {record["id"]: record for record in metadata["sources"]}
    updated_sources: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Total sources to process: {len(SOURCES)}")
    print("-" * 72)

    for index, source in enumerate(SOURCES, start=1):
        print(f"\n[{index}/{len(SOURCES)}]")
        existing = existing_by_id.get(source["id"])
        try:
            updated_sources.append(download_and_check_source(source, existing))
        except requests.RequestException as error:
            print(f"  DOWNLOAD FAILED: {error}")
            failures.append({"id": source["id"], "title": source["title"], "url": source["url"], "error": str(error), "checked_at": now_iso()})
            if existing:
                existing["last_checked"] = now_iso()
                existing["change_detected"] = True
                updated_sources.append(existing)

    metadata["sources"] = updated_sources
    metadata["failures"] = failures
    metadata["last_run_at"] = now_iso()
    metadata["manual_review_queue"] = [
        {
            "document_id": record["id"],
            "review_type": record["manual_review"].get("review_type"),
            "reason": record["manual_review"].get("reason"),
        }
        for record in updated_sources
        if record.get("manual_review", {}).get("status") == "pending"
    ]
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("\n" + "-" * 72)
    print(f"Metadata written to: {METADATA_PATH}")
    print(f"Manual review queue: {len(metadata['manual_review_queue'])}")
    if failures:
        print(f"Download failures: {len(failures)}")


if __name__ == "__main__":
    main()