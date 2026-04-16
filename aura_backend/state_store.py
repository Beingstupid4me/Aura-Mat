from __future__ import annotations

import threading
from typing import Dict, List


class AuraStateStore:
    def __init__(self, cards_needed: int) -> None:
        self._cards_needed = cards_needed
        self._lock = threading.Lock()
        self._status = "idle"
        self._error = ""
        self._scanned_cards: List[Dict[str, str]] = []
        self._seen_tag_ids = set()
        self._story = ""
        self._transcript_words: List[str] = []

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "status": self._status,
                "error": self._error,
                "cards_needed": self._cards_needed,
                "scanned_cards": list(self._scanned_cards),
                "count": len(self._scanned_cards),
                "story": self._story,
                "transcript": " ".join(self._transcript_words).strip(),
            }

    def set_status(self, status: str, error: str = "") -> None:
        with self._lock:
            self._status = status
            self._error = error

    def add_card(self, tag_id: str, label: str, category: str = "unknown") -> bool:
        with self._lock:
            if tag_id in self._seen_tag_ids:
                return False
            if len(self._scanned_cards) >= self._cards_needed:
                return False

            self._seen_tag_ids.add(tag_id)
            self._scanned_cards.append({"tag_id": tag_id, "label": label, "category": category})

            if len(self._scanned_cards) > 0:
                self._status = "collecting"
            self._error = ""
            return True

    def labels_for_story(self) -> List[str]:
        with self._lock:
            return [item["label"] for item in self._scanned_cards]

    def grouped_words_for_story(self) -> Dict[str, List[str]]:
        with self._lock:
            grouped = {"characters": [], "places": [], "things": []}
            for item in self._scanned_cards:
                label = item.get("label", "")
                category = str(item.get("category", "unknown")).lower()

                if category.startswith("character"):
                    grouped["characters"].append(label)
                elif category.startswith("place"):
                    grouped["places"].append(label)
                else:
                    grouped["things"].append(label)
            return grouped

    def is_round_complete(self) -> bool:
        with self._lock:
            return len(self._scanned_cards) >= self._cards_needed

    def set_story(self, story: str, reset_transcript: bool = True) -> None:
        with self._lock:
            self._story = story
            if reset_transcript:
                self._transcript_words = []

    def append_transcript_word(self, word: str) -> None:
        with self._lock:
            self._transcript_words.append(word)

    def reset_round(self, keep_story: bool = True) -> None:
        with self._lock:
            self._status = "idle"
            self._error = ""
            self._scanned_cards = []
            self._seen_tag_ids = set()
            self._transcript_words = []
            if not keep_story:
                self._story = ""
