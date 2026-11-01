#!/usr/bin/env python3
"""Validate normalized public-record search results and provenance."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


SECRET_PATTERN = re.compile(r"s" + r"k-[A-Za-z0-9_-]{20,}")
FORBIDDEN_KEYS = {"api_key", "authorization", "cookie", "access_token", "secret"}


def validate(data: dict, case: dict | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    serialized = json.dumps(data, ensure_ascii=False)
    if SECRET_PATTERN.search(serialized):
        errors.append("prior_art contains a likely API key")

    def walk(value: object, path: str = "root") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in FORBIDDEN_KEYS:
                    errors.append(f"forbidden secret-bearing field: {path}.{key}")
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(data)
    case_id = data.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        errors.append("case_id is required")
    if case and case_id != case.get("case_id"):
        errors.append("case_id mismatch between case and prior_art")
    if not isinstance(data.get("searched_at"), str) or not data["searched_at"].strip():
        errors.append("searched_at is required")
    if not isinstance(data.get("sources_attempted"), list):
        errors.append("sources_attempted must be an array")

    search_run = data.get("search_run")
    if not isinstance(search_run, dict):
        errors.append("search_run provenance is required")
    else:
        for field in ("provider", "model", "source_verification"):
            if not isinstance(search_run.get(field), str) or not search_run[field].strip():
                errors.append(f"search_run.{field} is required")
        if search_run.get("provider") == "openai-responses-web-search":
            if search_run.get("store") is not False:
                errors.append("OpenAI search_run.store must be false")
            if not isinstance(search_run.get("api_response_id"), str):
                errors.append("OpenAI search_run.api_response_id is required")

    records = data.get("records")
    if not isinstance(records, list):
        errors.append("records must be an array")
        records = []
    seen = set()
    for index, record in enumerate(records):
        field = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{field} must be an object")
            continue
        for name in ("record_id", "title", "source", "url", "abstract", "notes"):
            if not isinstance(record.get(name), str) or not record[name].strip():
                errors.append(f"{field}.{name} must be non-empty")
        record_id = record.get("record_id")
        if record_id in seen:
            errors.append(f"duplicate record_id: {record_id}")
        seen.add(record_id)
        url = record.get("url", "")
        if isinstance(url, str) and urlparse(url).scheme not in {"http", "https"}:
            errors.append(f"{field}.url must be HTTP(S)")
        matching = record.get("matching_features")
        if not isinstance(matching, list) or not matching:
            errors.append(f"{field}.matching_features must be non-empty")

    benchmark = data.get("benchmark_result")
    if isinstance(benchmark, dict):
        expected = benchmark.get("expected_record_id")
        actual_recall = expected in seen
        if benchmark.get("expected_record_recalled") is not actual_recall:
            errors.append("benchmark_result.expected_record_recalled does not match records")
        if benchmark.get("filing_material_generated") is not False:
            errors.append("public benchmark must not generate filing material")

    if not records:
        warnings.append("no verifiable public record was captured")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prior_art_json", type=Path)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.prior_art_json.read_text(encoding="utf-8"))
    case = json.loads(args.case.read_text(encoding="utf-8")) if args.case else None
    result = validate(data, case)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["valid"]:
        print("prior-art records: valid")
    else:
        for error in result["errors"]:
            print(f"ERROR: {error}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
