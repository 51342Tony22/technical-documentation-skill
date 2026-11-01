#!/usr/bin/env python3
"""Analyze verified public records with an OpenAI-compatible chat API."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
ALLOWED_LEVELS = {"high", "medium", "low"}


def api_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("ANALYSIS_BASE_URL must use HTTPS")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def build_payload(case: dict, prior_art: dict, model: str) -> dict:
    records = [
        {
            key: record.get(key)
            for key in (
                "record_id",
                "title",
                "publication_date",
                "jurisdiction",
                "abstract",
                "matching_features",
                "notes",
                "url",
            )
        }
        for record in prior_art.get("records", [])
    ]
    material = {
        "case": {
            key: case.get(key)
            for key in (
                "case_id",
                "technical_direction",
                "technical_problem",
                "known_features",
                "constraints",
            )
        },
        "verified_public_records": records,
    }
    system = (
        "你是专利公开材料的初步技术比对助手。只能使用用户提供的已核验记录，"
        "不得新增专利号、来源、日期、技术事实或法律结论。逐项比较技术问题、"
        "技术手段、数据关系和效果；仅改写措辞不算差异。输出必须是单个 JSON 对象，"
        "不得使用 Markdown。overlap_level 只能为 high、medium 或 low。"
    )
    output_contract = {
        "overall_assessment": "中文总体判断，不作新颖性或法律结论",
        "ranked_records": [
            {
                "record_id": "必须来自输入",
                "overlap_level": "high|medium|low",
                "overlapping_features": ["输入材料支持的实质重合点"],
                "differentiating_features": ["输入材料支持的差异；没有则写未确认"],
                "drafting_implication": "后续交底应澄清或避开的技术边界",
                "confidence": "high|medium|low",
            }
        ],
        "caveats": ["证据范围和专业复核限制"],
    }
    user = {
        "task": "对每一条已核验公开记录进行比对，并按实质重合程度排序。",
        "materials": material,
        "required_output": output_contract,
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 5000,
    }


def request_completion(payload: dict, api_key: str, base_url: str, timeout: int) -> dict:
    if not api_key.strip():
        raise ValueError("API key is empty")
    request = Request(
        api_endpoint(base_url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "draft-patent-copyright-skill/1.2",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"analysis API returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"analysis API request failed: {error.reason}") from error


def parse_generated(response: dict) -> dict:
    choices = response.get("choices", [])
    if not choices:
        raise ValueError("analysis API returned no choices")
    content = choices[0].get("message", {}).get("content", "").strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return json.loads(content.strip())


def validate_generated(generated: dict, record_ids: list[str]) -> list[dict]:
    if not isinstance(generated, dict):
        raise ValueError("model analysis must be an object")
    assessment = generated.get("overall_assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        raise ValueError("overall_assessment must be non-empty")
    ranked = generated.get("ranked_records")
    if not isinstance(ranked, list):
        raise ValueError("ranked_records must be an array")
    expected = set(record_ids)
    seen = set()
    for index, item in enumerate(ranked):
        if not isinstance(item, dict):
            raise ValueError(f"ranked_records[{index}] must be an object")
        record_id = item.get("record_id")
        if record_id not in expected:
            raise ValueError(f"model introduced an unverified record_id: {record_id}")
        if record_id in seen:
            raise ValueError(f"duplicate analyzed record_id: {record_id}")
        seen.add(record_id)
        for field in ("overlap_level", "confidence"):
            if item.get(field) not in ALLOWED_LEVELS:
                raise ValueError(f"ranked_records[{index}].{field} is invalid")
        for field in ("overlapping_features", "differentiating_features"):
            values = item.get(field)
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"ranked_records[{index}].{field} must be non-empty")
        implication = item.get("drafting_implication")
        if not isinstance(implication, str) or not implication.strip():
            raise ValueError(f"ranked_records[{index}].drafting_implication must be non-empty")
    if seen != expected:
        missing = ", ".join(sorted(expected - seen))
        raise ValueError(f"model omitted verified records: {missing}")
    caveats = generated.get("caveats")
    if not isinstance(caveats, list) or not caveats:
        raise ValueError("caveats must be a non-empty array")
    return ranked


def build_result(case: dict, prior_art: dict, response: dict, model: str) -> dict:
    generated = parse_generated(response)
    record_ids = [record["record_id"] for record in prior_art.get("records", [])]
    ranked = validate_generated(generated, record_ids)
    usage = response.get("usage", {})
    safe_usage = {
        key: usage[key]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance(usage.get(key), int)
    }
    return {
        "case_id": case["case_id"],
        "analyzed_at": date.today().isoformat(),
        "analysis_run": {
            "provider": "siliconflow-openai-compatible-chat",
            "model": model,
            "api_response_id": response.get("id", "unknown"),
            "source_scope": "provided-source-verified-records-only",
            "usage": safe_usage,
        },
        "overall_assessment": generated["overall_assessment"],
        "ranked_records": ranked,
        "caveats": generated["caveats"],
    }


def read_api_key(use_stdin: bool) -> str:
    if use_stdin:
        if sys.stdin.isatty():
            return getpass.getpass("API key (not stored): ")
        return sys.stdin.readline().strip()
    return os.environ.get("ANALYSIS_API_KEY", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("prior_art_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("ANALYSIS_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("ANALYSIS_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--api-key-stdin", action="store_true")
    args = parser.parse_args()

    case = json.loads(args.case_json.read_text(encoding="utf-8"))
    prior_art = json.loads(args.prior_art_json.read_text(encoding="utf-8"))
    if case.get("case_id") != prior_art.get("case_id"):
        raise SystemExit("case_id mismatch between case and prior_art")
    try:
        response = request_completion(
            build_payload(case, prior_art, args.model),
            read_api_key(args.api_key_stdin),
            args.base_url,
            args.timeout,
        )
        result = build_result(case, prior_art, response, args.model)
    except (ValueError, RuntimeError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"analyzed {len(result['ranked_records'])} verified records with {args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
