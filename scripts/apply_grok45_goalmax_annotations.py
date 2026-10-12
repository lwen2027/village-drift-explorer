#!/usr/bin/env python3
"""Apply the source-verified Grok 4.5 episode reconstruction."""

from pathlib import Path

import apply_gpt5_goalmax_annotations as annotation_migration


if __name__ == "__main__":
    annotation_migration.SPEC_PATH = Path(__file__).with_name(
        "grok45_goalmax_annotation_spec.json"
    )
    annotation_migration.main()
