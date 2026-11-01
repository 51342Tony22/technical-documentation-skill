#!/usr/bin/env python3
"""Package four generated copyright documents plus the supplied checklist."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "template-manifest.json"


def required_filenames() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    outputs = [
        item["output_filename"]
        for item in manifest["software-copyright"]["output_documents"]
    ]
    outputs.extend(
        item["output_filename"]
        for item in manifest["software-copyright"].get("supporting_references", [])
        if item.get("output_filename")
    )
    return outputs


def package(input_dir: Path, output_zip: Path) -> None:
    expected = required_filenames()
    missing = [name for name in expected if not (input_dir / name).is_file()]
    if missing:
        raise ValueError("missing required files: " + ", ".join(missing))

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in expected:
            archive.write(input_dir / name, arcname=name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()

    try:
        package(args.input_dir, args.output_zip)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"packaged: {args.output_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
