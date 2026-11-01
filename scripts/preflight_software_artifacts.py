#!/usr/bin/env python3
"""Verify software screenshots and source inventory before copyright drafting."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "credential-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
}
THIRD_PARTY_SEGMENTS = {"node_modules", "vendor", "third_party", "third-party", "dist", "build"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(
    inventory_path: Path,
    source_root: Path,
    screenshots: list[Path],
    *,
    confirm_actual_screenshots: bool,
    confirm_complete_framing: bool = False,
) -> dict:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    errors = []
    notes = []
    verified_lines = 0
    submitted_lines = 0
    secret_findings = []
    included_third_party = []

    files = inventory.get("files")
    if not isinstance(files, list) or not files:
        errors.append("source inventory requires a non-empty files array")
        files = []

    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"files[{index}] must be an object")
            continue
        relative = item.get("path")
        if not isinstance(relative, str) or not relative.strip():
            errors.append(f"files[{index}].path must be non-empty")
            continue
        path = (source_root / relative).resolve()
        try:
            path.relative_to(source_root.resolve())
        except ValueError:
            errors.append(f"source path escapes source root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"source file is missing: {relative}")
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"source file is not UTF-8: {relative}")
            continue
        actual_lines = len(text.splitlines())
        verified_lines += actual_lines
        if item.get("included") is True:
            submitted_lines += actual_lines
        if item.get("line_count") != actual_lines:
            errors.append(
                f"line count mismatch for {relative}: inventory={item.get('line_count')}, actual={actual_lines}"
            )
        if item.get("sha256") != hashlib.sha256(raw).hexdigest():
            errors.append(f"sha256 mismatch for {relative}")
        if item.get("included") is True and THIRD_PARTY_SEGMENTS & set(Path(relative).parts):
            included_third_party.append(relative)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                secret_findings.append({"path": relative, "pattern": label})

    screenshot_errors = []
    if not screenshots:
        screenshot_errors.append("no screenshots were supplied")
    for screenshot in screenshots:
        if not screenshot.is_file():
            screenshot_errors.append(f"screenshot is missing: {screenshot}")
            continue
        try:
            with Image.open(screenshot) as image:
                image.verify()
        except Exception as error:
            screenshot_errors.append(f"invalid screenshot {screenshot}: {error}")
    errors.extend(screenshot_errors)

    declared_project = inventory.get("project_owned_source_line_count")
    if declared_project != verified_lines:
        errors.append(
            "project_owned_source_line_count does not match verified inventory lines: "
            f"declared={declared_project}, actual={verified_lines}"
        )
    declared_submitted = inventory.get("submitted_source_line_count")
    if declared_submitted is not None and declared_submitted != submitted_lines:
        errors.append(
            "submitted_source_line_count does not match included inventory lines: "
            f"declared={declared_submitted}, actual={submitted_lines}"
        )
    if included_third_party:
        errors.append("included source contains third-party or generated paths")
    if not confirm_actual_screenshots:
        notes.append("screenshot files passed image checks but actual-software origin was not confirmed")
    if not confirm_complete_framing:
        notes.append(
            "screenshot framing was not confirmed complete, centered, readable, and free of edge cutoffs"
        )

    preflight = {
        "screenshots_verified_actual": not screenshot_errors and confirm_actual_screenshots,
        "screenshot_framing_verified": not screenshot_errors and confirm_complete_framing,
        "source_inventory_verified": not any(
            "source" in error or "line count" in error or "sha256" in error
            for error in errors
        ),
        "secrets_scan_status": "passed" if not secret_findings else "failed",
        "third_party_exclusions_reviewed": not included_third_party,
        "notes": notes,
    }
    return {
        "valid": (
            not errors
            and not secret_findings
            and preflight["screenshots_verified_actual"]
            and preflight["screenshot_framing_verified"]
        ),
        "artifact_preflight": preflight,
        "source_counts": {
            "project_qualifying_line_count": verified_lines,
            "submitted_source_line_count": submitted_lines,
        },
        "secret_findings": secret_findings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory_json", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, action="append", default=[])
    parser.add_argument("--confirm-actual-screenshots", action="store_true")
    parser.add_argument(
        "--confirm-complete-framing",
        action="store_true",
        help="confirm every screenshot is complete, centered, readable, and has no edge cutoff",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = inspect(
        args.inventory_json,
        args.source_root,
        args.screenshot,
        confirm_actual_screenshots=args.confirm_actual_screenshots,
        confirm_complete_framing=args.confirm_complete_framing,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
