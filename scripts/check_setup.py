#!/usr/bin/env python3
"""Check whether fixed prompts and supplied DOCX templates are ready."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "template-manifest.json"
PLACEHOLDER_MARKER = "PROMPT_STATUS: PLACEHOLDER"
READY_MARKER = "PROMPT_STATUS: READY_FOR_TESTING"
VERSION_MARKER = "PROMPT_VERSION:"
REQUIRED_PROMPT_VERSIONS = {
    "patent": "PROMPT_VERSION: 1.8.2",
    "software-copyright": "PROMPT_VERSION: 1.5.0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_setup() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    modes = {}
    for mode, config in manifest.items():
        prompt_path = ROOT / config["prompt"]
        prompt_contract_errors = []
        prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
        if not prompt_path.is_file():
            prompt_contract_errors.append("prompt file is missing")
        else:
            if PLACEHOLDER_MARKER in prompt_text:
                prompt_contract_errors.append("prompt is still a placeholder")
            if READY_MARKER not in prompt_text:
                prompt_contract_errors.append(f"missing readiness marker: {READY_MARKER}")
            if VERSION_MARKER not in prompt_text:
                prompt_contract_errors.append(f"missing version marker: {VERSION_MARKER}")
            elif REQUIRED_PROMPT_VERSIONS[mode] not in prompt_text:
                prompt_contract_errors.append(
                    f"prompt must use the required contract: {REQUIRED_PROMPT_VERSIONS[mode]}"
                )
            for contract_field in ("evidence_map", "conflicts"):
                if contract_field not in prompt_text:
                    prompt_contract_errors.append(
                        f"prompt is missing required contract field: {contract_field}"
                    )
            for document in config["output_documents"]:
                if document["id"] not in prompt_text:
                    prompt_contract_errors.append(
                        f"prompt is missing document ID: {document['id']}"
                    )
                for section in document["required_sections"]:
                    if section not in prompt_text:
                        prompt_contract_errors.append(
                            f"prompt is missing required section: {section}"
                        )
        prompt_ready = not prompt_contract_errors

        templates = []
        for document in config["output_documents"]:
            template_path = ROOT / document["template"]
            exists = template_path.is_file()
            actual_sha256 = sha256(template_path) if exists else None
            integrity_ok = exists and actual_sha256 == document["sha256"]
            templates.append(
                {
                    "id": document["id"],
                    "path": str(template_path.relative_to(ROOT)),
                    "exists": exists,
                    "integrity_ok": integrity_ok,
                    "actual_sha256": actual_sha256,
                }
            )

        templates_ready = all(item["integrity_ok"] for item in templates)
        modes[mode] = {
            "prompt": str(prompt_path.relative_to(ROOT)),
            "prompt_ready": prompt_ready,
            "prompt_contract_errors": prompt_contract_errors,
            "templates_ready": templates_ready,
            "templates": templates,
        }

    ready = all(
        details["prompt_ready"] and details["templates_ready"]
        for details in modes.values()
    )
    return {"ready": ready, "modes": modes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    result = inspect_setup()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for mode, details in result["modes"].items():
            prompt_status = "ready" if details["prompt_ready"] else "not ready"
            template_status = "ready" if details["templates_ready"] else "missing or changed"
            print(f"{mode}: prompt={prompt_status}; templates={template_status}")
            for error in details["prompt_contract_errors"]:
                print(f"  prompt: {error}")
            for template in details["templates"]:
                status = "ready" if template["integrity_ok"] else "missing or changed"
                print(f"  {template['id']}: {status}")
        print("setup: ready" if result["ready"] else "setup: incomplete")
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
