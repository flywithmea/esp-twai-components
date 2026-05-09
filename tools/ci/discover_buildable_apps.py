#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def discover_app_paths(collect_output_path: Path) -> list[str]:
    collect_output = json.loads(collect_output_path.read_text(encoding="utf-8"))
    return sorted(
        {
            project_path
            for project_path, project_data in collect_output.get("projects", {}).items()
            if any(
                app.get("build_status") == "should be built"
                for app in project_data.get("apps", [])
            )
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract buildable app paths from idf-ci collect output."
    )
    parser.add_argument(
        "collect_output_json", help="Path to idf-ci build collect JSON output."
    )
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    app_paths = discover_app_paths(Path(args.collect_output_json))

    sys.stdout.write(json.dumps(app_paths, separators=(",", ":")))
    sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
