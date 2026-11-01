#!/usr/bin/env python3
"""Search public records through the OpenAI Responses API web-search tool."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.6"
ALLOWED_MODES = {"patent", "software-copyright"}


def compact(value: object, limit: int = 800) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def build_query_groups(case: dict) -> list[dict[str, str]]:
    problem = compact(case.get("technical_problem"), 500)
    direction = compact(case.get("technical_direction"), 500)
    features = [compact(item, 240) for item in case.get("known_features", [])]
    feature_text = "；".join(item for item in features[:8] if item)
    if not problem or not direction or not feature_text:
        raise ValueError(
            "case requires technical_problem, technical_direction, and known_features"
        )
    return [
        {
            "type": "problem",
            "query": f"{direction}；需要解决的问题：{problem}",
        },
        {
            "type": "structure",
            "query": f"关键结构、流程和数据关系：{feature_text}",
        },
        {
            "type": "effect",
            "query": f"技术机制及效果：{feature_text}；目标问题：{problem}",
        },
    ]


def response_schema() -> dict:
    record = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "record_id": {"type": "string"},
            "title": {"type": "string"},
            "source": {"type": "string"},
            "url": {"type": "string"},
            "publication_date": {"type": "string"},
            "jurisdiction": {"type": "string"},
            "abstract": {"type": "string"},
            "matching_features": {
                "type": "array",
                "items": {"type": "string"},
            },
            "notes": {"type": "string"},
        },
        "required": [
            "record_id",
            "title",
            "source",
            "url",
            "publication_date",
            "jurisdiction",
            "abstract",
            "matching_features",
            "notes",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "sources_attempted": {
                "type": "array",
                "items": {"type": "string"},
            },
            "records": {"type": "array", "items": record},
            "search_limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["sources_attempted", "records", "search_limitations"],
    }


def build_payload(case: dict, model: str, query_groups: list[dict[str, str]]) -> dict:
    case_excerpt = {
        "mode": case.get("mode"),
        "technical_direction": case.get("technical_direction"),
        "technical_problem": case.get("technical_problem"),
        "known_features": case.get("known_features", []),
        "constraints": case.get("constraints", []),
    }
    instructions = (
        "You perform a preliminary patent and public-technical-record search. "
        "Use web search for every record. Prefer official patent offices, WIPO, "
        "EPO, Google Patents, publishers, standards bodies, and official project "
        "repositories. Return only records whose identifier, title, URL, and date "
        "can be verified in an accessed source. Never invent metadata. Preserve "
        "adverse close records. A matching feature must describe substantive "
        "technical overlap, not shared topic words. Use 'unknown' when a date or "
        "jurisdiction cannot be confirmed. Do not give a legal conclusion."
    )
    user_input = {
        "task": "Find 5 to 10 verifiable public records relevant to this case.",
        "case": case_excerpt,
        "query_groups": query_groups,
        "output_language": "Chinese summaries; preserve official titles when useful",
    }
    return {
        "model": model,
        "store": False,
        "stream": True,
        "reasoning": {"effort": "medium"},
        "instructions": instructions,
        "input": json.dumps(user_input, ensure_ascii=False),
        "tools": [{"type": "web_search", "search_context_size": "high"}],
        "tool_choice": "required",
        "include": ["web_search_call.action.sources"],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "public_record_search",
                "strict": True,
                "schema": response_schema(),
            }
        },
        "max_output_tokens": 8000,
    }


def api_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("OPENAI_BASE_URL must use HTTPS")
    if base.endswith("/responses"):
        return base
    return f"{base}/responses"


def request_response(
    payload: dict,
    api_key: str,
    base_url: str,
    timeout: int,
    opener=urlopen,
) -> dict:
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
        with opener(request, timeout=timeout) as response:
            if payload.get("stream"):
                return read_streamed_response(response)
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Responses API returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Responses API request failed: {error.reason}") from error


def read_streamed_response(response) -> dict:
    """Return the final response object from a Responses API SSE stream."""
    completed = None
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError as error:
            raise RuntimeError("Responses API returned malformed stream data") from error
        event_type = event.get("type")
        if event_type == "response.completed":
            completed = event.get("response")
        elif event_type in {"error", "response.failed", "response.incomplete"}:
            detail = event.get("error") or event.get("response", {}).get("error") or event
            raise RuntimeError(f"Responses API stream failed: {compact(detail, 1000)}")
    if not isinstance(completed, dict):
        raise RuntimeError("Responses API stream ended without a completed response")
    return completed


def output_text(response: dict) -> str:
    texts = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    if not texts:
        raise ValueError("Responses API returned no output_text")
    return "\n".join(texts)


def source_urls(response: dict) -> set[str]:
    urls: set[str] = set()

    def walk(value: object, in_source_context: bool = False) -> None:
        if isinstance(value, dict):
            kind = str(value.get("type", ""))
            source_context = in_source_context or kind in {
                "url_citation",
                "web_search_call",
                "web_search_result",
            }
            for key, item in value.items():
                if key == "url" and source_context and isinstance(item, str):
                    urls.add(item)
                else:
                    walk(item, source_context or key in {"sources", "annotations"})
        elif isinstance(value, list):
            for item in value:
                walk(item, in_source_context)

    walk(response)
    return urls


def canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", "", ""))


def validate_search_output(generated: dict, verified_urls: set[str]) -> list[dict]:
    if not isinstance(generated, dict):
        raise ValueError("structured search output must be an object")
    records = generated.get("records")
    if not isinstance(records, list):
        raise ValueError("structured search output requires records")
    verified = {canonical_url(url) for url in verified_urls}
    normalized = []
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{index}] must be an object")
        for field in (
            "record_id",
            "title",
            "source",
            "url",
            "publication_date",
            "jurisdiction",
            "abstract",
            "notes",
        ):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"records[{index}].{field} must be non-empty")
        url = record["url"].strip()
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError(f"records[{index}].url must be HTTP(S)")
        if canonical_url(url) not in verified:
            raise ValueError(
                f"records[{index}].url was not returned by the API web-search sources"
            )
        matching = record.get("matching_features")
        if not isinstance(matching, list) or not matching or any(
            not isinstance(item, str) or not item.strip() for item in matching
        ):
            raise ValueError(f"records[{index}].matching_features must be non-empty")
        record_id = record["record_id"].strip()
        if record_id in seen:
            continue
        seen.add(record_id)
        normalized.append({key: record[key] for key in record})
    if not normalized:
        raise ValueError("no source-verified public record was returned")
    return normalized


def build_result(case: dict, response: dict, model: str, query_groups: list[dict]) -> dict:
    generated = json.loads(output_text(response))
    urls = source_urls(response)
    records = validate_search_output(generated, urls)
    usage = response.get("usage", {})
    safe_usage = {
        key: usage[key]
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if isinstance(usage.get(key), int)
    }
    return {
        "case_id": case["case_id"],
        "searched_at": date.today().isoformat(),
        "sources_attempted": generated.get("sources_attempted", []),
        "search_run": {
            "provider": "openai-responses-web-search",
            "model": model,
            "api_response_id": response.get("id", "unknown"),
            "store": False,
            "query_groups": query_groups,
            "source_verification": "cross-checked-against-api-web-search-sources",
            "usage": safe_usage,
        },
        "records": records,
        "search_limitations": generated.get("search_limitations", []),
    }


def read_api_key(use_stdin: bool) -> str:
    if use_stdin:
        if sys.stdin.isatty():
            return getpass.getpass("API key (not stored): ")
        return sys.stdin.readline().strip()
    return os.environ.get("OPENAI_API_KEY", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("OPENAI_SEARCH_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--api-key-stdin",
        action="store_true",
        help="Read a one-time API key without placing it in process arguments",
    )
    parser.add_argument(
        "--fixture-response",
        type=Path,
        help="Use a captured redacted response for deterministic offline testing",
    )
    args = parser.parse_args()

    case = json.loads(args.case_json.read_text(encoding="utf-8"))
    if case.get("mode") not in ALLOWED_MODES:
        raise SystemExit("case mode must be patent or software-copyright")
    if not isinstance(case.get("case_id"), str) or not case["case_id"].strip():
        raise SystemExit("case_id is required")
    try:
        groups = build_query_groups(case)
        if args.fixture_response:
            response = json.loads(args.fixture_response.read_text(encoding="utf-8"))
        else:
            key = read_api_key(args.api_key_stdin)
            response = request_response(
                build_payload(case, args.model, groups),
                key,
                args.base_url,
                args.timeout,
            )
        result = build_result(case, response, args.model, groups)
    except (ValueError, RuntimeError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"captured {len(result['records'])} source-verified records "
        f"with {result['search_run']['model']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
