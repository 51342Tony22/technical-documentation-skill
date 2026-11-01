#!/usr/bin/env python3
"""Validate code-backed patent artifacts and emit a reproducible evidence report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ALLOWED_KINDS = {
    "source-code",
    "generated-technical-figure",
    "actual-runtime-screenshot",
    "public-source",
    "conceptual-non-evidence",
}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(inventory_path: Path, artifact_root: Path) -> dict:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = artifact_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    verified: list[dict] = []
    seen_ids: set[str] = set()

    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("inventory.artifacts requires a non-empty array")
        artifacts = []

    for index, item in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        artifact_id = item.get("id")
        kind = item.get("kind")
        relative = item.get("path")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append(f"{prefix}.id must be non-empty")
            continue
        if artifact_id in seen_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        seen_ids.add(artifact_id)
        if kind not in ALLOWED_KINDS:
            errors.append(f"{prefix}.kind is unsupported: {kind}")
            continue
        if kind == "public-source":
            if not item.get("stable_id") or not item.get("url"):
                errors.append(f"{prefix} public-source requires stable_id and url")
            continue
        if not isinstance(relative, str) or not relative.strip():
            errors.append(f"{prefix}.path must be non-empty")
            continue
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"artifact path escapes root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"artifact is missing: {relative}")
            continue

        actual_hash = sha256(path)
        if item.get("sha256") != actual_hash:
            errors.append(f"sha256 mismatch: {relative}")

        if kind in {"generated-technical-figure", "actual-runtime-screenshot", "conceptual-non-evidence"}:
            try:
                with Image.open(path) as image:
                    width, height = image.size
                    image.verify()
                if width < 640 or height < 360:
                    warnings.append(f"low-resolution image: {relative} ({width}x{height})")
            except Exception as error:
                errors.append(f"invalid image {relative}: {error}")
            if kind == "actual-runtime-screenshot":
                capture = item.get("capture")
                required = ("route", "viewport", "captured_at", "state")
                if not isinstance(capture, dict) or any(not capture.get(key) for key in required):
                    errors.append(f"{prefix}.capture requires route, viewport, captured_at, and state")
                else:
                    framing = capture.get("framing_review")
                    checks = (
                        "full_subject_visible",
                        "centered",
                        "text_readable",
                        "no_occlusion",
                        "no_scroll_cutoff",
                    )
                    if not isinstance(framing, dict) or not framing.get("subject"):
                        errors.append(f"{prefix}.capture.framing_review requires a named subject")
                    elif any(framing.get(check) is not True for check in checks):
                        errors.append(
                            f"{prefix}.capture.framing_review requires all visual checks to be true"
                        )

        if kind == "generated-technical-figure":
            if not item.get("generator") or not item.get("blueprint"):
                errors.append(f"{prefix} generated figure requires generator and blueprint")

        if kind == "source-code":
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"source is not UTF-8: {relative}")
                text = ""
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"secret pattern {label} found in {relative}")
            declared_lines = item.get("line_count")
            actual_lines = len(text.splitlines())
            if declared_lines != actual_lines:
                errors.append(f"line count mismatch: {relative}; declared={declared_lines}, actual={actual_lines}")

        verified.append({"id": artifact_id, "kind": kind, "path": relative, "sha256": actual_hash})

    return {
        "valid": not errors,
        "artifact_preflight": {
            "inventory_verified": not errors,
            "actual_screenshots_verified": any(item["kind"] == "actual-runtime-screenshot" for item in verified),
            "technical_figures_verified": any(item["kind"] == "generated-technical-figure" for item in verified),
            "secrets_scan_status": "passed" if not any("secret pattern" in error for error in errors) else "failed",
            "artifact_count": len(verified),
        },
        "verified_artifacts": verified,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory_json", type=Path)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(args.inventory_json, args.artifact_root)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
