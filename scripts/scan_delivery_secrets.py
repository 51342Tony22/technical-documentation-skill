#!/usr/bin/env python3
"""Reject likely credentials in a delivery directory or archive."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path


PATTERNS = {
    "api-key": re.compile(rb"s" + rb"k-[A-Za-z0-9_-]{20,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "bearer-token": re.compile(rb"Bearer\s+[A-Za-z0-9._~+/=-]{24,}"),
}
MAX_ENTRY_BYTES = 20 * 1024 * 1024
IGNORED_PARTS = {"__pycache__", ".git", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def scan_bytes(data: bytes, location: str) -> list[dict[str, str]]:
    findings = []
    for kind, pattern in PATTERNS.items():
        if pattern.search(data):
            findings.append({"type": kind, "location": location})
    return findings


def scan_zip(path: Path) -> list[dict[str, str]]:
    findings = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or info.file_size > MAX_ENTRY_BYTES:
                    continue
                findings.extend(
                    scan_bytes(archive.read(info), f"{path}!{info.filename}")
                )
    except (zipfile.BadZipFile, OSError):
        pass
    return findings


def scan_path(root: Path) -> list[dict[str, str]]:
    paths = [root] if root.is_file() else [
        item
        for item in root.rglob("*")
        if item.is_file()
        and not (set(item.parts) & IGNORED_PARTS)
        and item.suffix.lower() not in IGNORED_SUFFIXES
    ]
    findings = []
    for path in paths:
        if path.stat().st_size <= MAX_ENTRY_BYTES:
            findings.extend(scan_bytes(path.read_bytes(), str(path)))
        if path.suffix.lower() in {".zip", ".docx", ".pptx", ".xlsx"}:
            findings.extend(scan_zip(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.path.exists():
        raise SystemExit(f"path does not exist: {args.path}")
    findings = scan_path(args.path)
    result = {"valid": not findings, "finding_count": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        for finding in findings:
            print(f"ERROR: {finding['type']} in {finding['location']}")
    else:
        print("secret scan: passed")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
