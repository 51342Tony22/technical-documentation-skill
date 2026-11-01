#!/usr/bin/env python3
"""Create a preliminary, deterministic overlap report from captured records."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


LIMITATION = (
    "This is a preliminary machine-assisted search and similarity analysis based "
    "on accessible public information. It is not a legal novelty, inventiveness, "
    "freedom-to-operate, patentability, or registration opinion. Professional "
    "review is required before filing."
)


def normalize(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9\u3400-\u9fff]+", text.lower()))


def ngrams(text: str, size: int = 2) -> set[str]:
    value = normalize(text)
    if not value:
        return set()
    if len(value) < size:
        return {value}
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def similarity(left: str, right: str) -> float:
    left_set = ngrams(left)
    right_set = ngrams(right)
    if not left_set or not right_set:
        return 0.0
    # Compare against the shorter phrase so a concise evidence tag can match a
    # longer case feature without being diluted by the full record text.
    return len(left_set & right_set) / min(len(left_set), len(right_set))


def score_record(features: list[str], record: dict) -> tuple[float, list[str]]:
    explicit_matches = [
        str(item).strip()
        for item in record.get("matching_features", [])
        if str(item).strip()
    ]
    if explicit_matches:
        # Search records already carry reviewer-confirmed overlap tags. Prefer
        # those tags over pretending that lexical similarity proves a full
        # case feature was disclosed.
        coverage = len(explicit_matches) / max(len(features), 1)
        return min(coverage, 1.0), explicit_matches

    evidence_units = [
        str(record.get("title", "")),
        str(record.get("abstract", "")),
    ]
    scores = [
        (feature, max((similarity(feature, unit) for unit in evidence_units), default=0.0))
        for feature in features
    ]
    matched = [feature for feature, score in scores if score >= 0.45]
    return (sum(score for _, score in scores) / len(scores) if scores else 0.0, matched)


def risk_label(score: float) -> str:
    if score >= 0.45:
        return "high review priority"
    if score >= 0.20:
        return "medium review priority"
    return "low automated overlap"


def build_report(case: dict, search: dict) -> str:
    features = [str(item) for item in case.get("known_features", [])]
    rows = []
    for record in search.get("records", []):
        score, matched = score_record(features, record)
        rows.append((score, matched, record))
    rows.sort(key=lambda item: item[0], reverse=True)

    lines = [
        "# Preliminary Prior-Art Overlap Report",
        "",
        f"- Case: {case.get('case_id', 'unknown')}",
        f"- Mode: {case.get('mode', 'unknown')}",
        f"- Search date: {search.get('searched_at', 'unknown')}",
        f"- Verifiable records: {len(rows)}",
        "",
        "| Priority | Score | Record | Title | Captured matching features |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for score, matched, record in rows:
        safe_title = str(record.get("title", "unknown")).replace("|", "\\|")
        safe_record = str(record.get("record_id", "unknown")).replace("|", "\\|")
        feature_text = ", ".join(matched) if matched else "none detected"
        lines.append(
            f"| {risk_label(score)} | {score:.2f} | {safe_record} | {safe_title} | {feature_text} |"
        )

    if not rows:
        lines.extend(
            [
                "| review required | 0.00 | none captured | No verifiable record was captured | n/a |",
                "",
                "An empty result does not establish novelty or absence of relevant prior art.",
            ]
        )

    lines.extend(["", "## Limitation", "", LIMITATION, ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_json", type=Path)
    parser.add_argument("prior_art_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    case = json.loads(args.case_json.read_text(encoding="utf-8"))
    search = json.loads(args.prior_art_json.read_text(encoding="utf-8"))
    if case.get("case_id") != search.get("case_id"):
        raise SystemExit("case_id mismatch between case and prior-art records")

    report = build_report(case, search)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
