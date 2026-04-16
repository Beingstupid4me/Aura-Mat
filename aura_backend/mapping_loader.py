from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def normalize_tag_id(tag_id: str) -> str:
    return "".join(tag_id.strip().upper().split())


def tag_lookup_keys(tag_id: str) -> List[str]:
    normalized = normalize_tag_id(tag_id)
    if not normalized:
        return []

    keys: List[str] = []
    seen = set()

    def push(key: str) -> None:
        if not key:
            return
        if key in seen:
            return
        seen.add(key)
        keys.append(key)

    push(normalized)
    push(normalized.lstrip("0") or "0")

    is_hex = all(ch in "0123456789ABCDEF" for ch in normalized)
    if is_hex:
        padded = normalized if len(normalized) % 2 == 0 else f"0{normalized}"
        chunks = [padded[i : i + 2] for i in range(0, len(padded), 2)]
        compact = "".join(chunk.lstrip("0") or "0" for chunk in chunks)
        push(compact)
        push(compact.lstrip("0") or "0")

    return keys


def _alias_keys(tag_id: str) -> Iterable[str]:
    return tag_lookup_keys(tag_id)


def _resolve(base_dir: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _build_category_lookup(word_categories: Dict[str, object]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for category, items in word_categories.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str):
                lookup[item] = str(category).lower().rstrip("s")
    return lookup


def _load_legacy_python_mappings(legacy_file: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    source = legacy_file.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(legacy_file))

    card_mappings: Dict[str, str] = {}
    word_categories: Dict[str, object] = {}

    for node in parsed.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "card_mappings":
                value = ast.literal_eval(node.value)
                if isinstance(value, dict):
                    card_mappings = {
                        str(k): str(v)
                        for k, v in value.items()
                        if isinstance(k, str) and isinstance(v, str)
                    }
            if target.id == "word_categories":
                value = ast.literal_eval(node.value)
                if isinstance(value, dict):
                    word_categories = value

    category_lookup = _build_category_lookup(word_categories)
    return card_mappings, category_lookup


def _load_json_mappings(json_file: Path) -> Dict[str, Dict[str, str]]:
    with json_file.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    loaded: Dict[str, Dict[str, str]] = {}
    for tag_id, details in raw.items():
        if not isinstance(tag_id, str):
            continue

        if isinstance(details, str):
            name = details
            category = "unknown"
        elif isinstance(details, dict):
            name = str(details.get("name", normalize_tag_id(tag_id)))
            category = str(details.get("category", "unknown")).lower()
        else:
            continue

        for key in _alias_keys(tag_id):
            loaded[key] = {"name": name, "category": category}

    return loaded


def load_tag_mappings(
    base_dir: Path,
    json_mapping_path: str,
    legacy_enabled: bool,
    legacy_mapping_path: str,
    logger: logging.Logger,
) -> Dict[str, Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}

    json_file = _resolve(base_dir, json_mapping_path)
    if json_file.exists():
        merged.update(_load_json_mappings(json_file))
        logger.info("Loaded %s tag mappings from JSON: %s", len(merged), json_file)
    else:
        logger.warning("Tag mapping JSON not found: %s", json_file)

    if legacy_enabled:
        legacy_file = _resolve(base_dir, legacy_mapping_path)
        if legacy_file.exists():
            card_mappings, category_lookup = _load_legacy_python_mappings(legacy_file)
            legacy_count = 0
            for tag_id, name in card_mappings.items():
                category = category_lookup.get(name, "unknown")
                details = {"name": name, "category": category}
                for key in _alias_keys(tag_id):
                    merged[key] = details
                legacy_count += 1

            logger.info("Imported %s legacy mappings from %s", legacy_count, legacy_file)
        else:
            logger.warning("Legacy mapping file not found: %s", legacy_file)

    return merged
