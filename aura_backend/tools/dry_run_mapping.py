from __future__ import annotations

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mapping_loader import load_tag_mappings, normalize_tag_id


def main() -> None:
    root = ROOT

    logger = logging.getLogger("dryrun")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    mappings = load_tag_mappings(
        base_dir=root,
        json_mapping_path="data/tag_mappings.json",
        legacy_enabled=True,
        legacy_mapping_path="../Story_Reader.py",
        logger=logger,
    )

    sample_lines = [
        "TAG_ID:0B3B0F16",
        "TAG_ID:B3B0F16",
        "TAG_ID:0061DD07",
        "TAG_ID:85D950FC",
        "TAG_ID:FFFFFFFF",
    ]

    print("--- DRY RUN: ESP32 TAG LINE TO MAPPING ---")
    for line in sample_lines:
        tag = normalize_tag_id(line.split(":", 1)[1])
        alias = tag.lstrip("0") or "0"
        key = tag if tag in mappings else alias
        item = mappings.get(key)
        if item:
            print(f"{line} -> {item['name']} ({item['category']})")
        else:
            print(f"{line} -> UNMAPPED")


if __name__ == "__main__":
    main()
