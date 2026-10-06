#!/usr/bin/env python3
"""Refresh the explorer's embedded AI Village goal and agent records."""

import argparse
import gzip
import json
import pathlib
import re


def read_jsonl_gz(path: pathlib.Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def replace_constant(html: str, name: str, records: list[dict]) -> str:
    replacement = f"const {name} = {json.dumps(records, ensure_ascii=False, separators=(',', ':'))};"
    pattern = re.compile(rf"const {re.escape(name)} = \[.*?\];", re.DOTALL)
    # A callable replacement preserves JSON escape sequences such as ``\n``;
    # passing the JSON string directly would let ``re`` interpret backslashes.
    updated, count = pattern.subn(lambda _match: replacement, html, count=1)
    if count != 1:
        raise SystemExit(f"could not uniquely replace {name}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=pathlib.Path)
    parser.add_argument("--html", required=True, type=pathlib.Path)
    args = parser.parse_args()

    sources = {
        "agentGoalRecords": (
            "agent_goals.jsonl.gz",
            ("id", "agent_id", "name", "short_name", "description", "start_time", "end_time"),
        ),
        "agentRecords": ("agents.jsonl.gz", ("id", "name", "created_at")),
        "villageGoalRecords": ("village_goals.jsonl.gz", ("id", "goal", "start_time", "end_time")),
    }
    html = args.html.read_text(encoding="utf-8")
    for constant, (filename, fields) in sources.items():
        records = [
            {field: record.get(field) for field in fields}
            for record in read_jsonl_gz(args.source_dir / filename)
        ]
        html = replace_constant(html, constant, records)
        print(f"{constant}: {len(records)} records")
    args.html.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
