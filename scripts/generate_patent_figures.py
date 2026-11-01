#!/usr/bin/env python3
"""Generate deterministic patent figures from reviewed JSON blueprints."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import render_patent_disclosure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprints_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.blueprints_json.read_text(encoding="utf-8"))
    figures = payload.get("figures", [])
    if not figures:
        raise ValueError("blueprints require a non-empty figures array")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for spec in figures:
        figure_id = str(spec.get("图号", "figure"))
        slug = re.sub(r"[^0-9A-Za-z_-]+", "-", figure_id).strip("-") or "figure"
        output = args.output_dir / f"{slug}.png"
        if not (
            render_patent_disclosure.create_altair_chart(spec, output)
            or render_patent_disclosure.create_diagram(spec, output)
        ):
            raise ValueError(f"cannot generate {figure_id}")
        generated.append(str(output))
    print(json.dumps({"generated": generated}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
