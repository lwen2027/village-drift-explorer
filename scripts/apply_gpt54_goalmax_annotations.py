#!/usr/bin/env python3
"""Apply the source-verified GPT-5.4 goal-max audit to public annotations."""

from pathlib import Path

import apply_gpt5_goalmax_annotations as annotation_migration


if __name__ == "__main__":
    annotation_migration.SPEC_PATH = Path(__file__).with_name(
        "gpt54_goalmax_annotation_spec.json"
    )
    annotation_migration.main()
