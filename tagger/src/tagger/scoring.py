"""Score normalisation, deduplication and ranking of Vision results."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from google.cloud import vision

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)


@dataclass
class Tag:
    tag: str
    score: float
    source: str  # "label" or "object"


def normalize_label(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def load_aliases(path: Path) -> dict[str, str]:
    """Load an optional alias map used only for deduplication."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load tag aliases from %s: %s", path, exc)
        return {}
    if not isinstance(raw, dict):
        logger.warning("tag_aliases.json must be an object, got %s", type(raw))
        return {}
    return {normalize_label(k): normalize_label(v) for k, v in raw.items()}


def _label_score(annotation: vision.EntityAnnotation) -> float | None:
    """Prefer topicality (centrality) over score (confidence)."""
    for attr in ("topicality", "score"):
        value = getattr(annotation, attr, None)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _object_score(annotation: vision.LocalizedObjectAnnotation) -> float | None:
    value = getattr(annotation, "score", None)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def collect_tags(
    response: vision.AnnotateImageResponse,
    aliases: dict[str, str] | None = None,
) -> list[Tag]:
    """Merge label and object annotations into a flat list of tags."""
    aliases = aliases or {}
    merged: dict[str, Tag] = {}

    def _add(name: str, score: float, source: str) -> None:
        key = normalize_label(name)
        if not key:
            return
        key = aliases.get(key, key)
        existing = merged.get(key)
        if existing is None:
            merged[key] = Tag(tag=name.strip(), score=score, source=source)
            return
        # Keep the highest score; prefer "object" on ties.
        if score > existing.score or (score == existing.score and source == "object"):
            merged[key] = Tag(tag=name.strip(), score=score, source=source)

    for label in response.label_annotations:
        score = _label_score(label)
        if score is None:
            continue
        _add(label.description, score, "label")

    for obj in response.localized_object_annotations:
        score = _object_score(obj)
        if score is None:
            continue
        _add(obj.name, score, "object")

    return list(merged.values())


def rank_tags(
    tags: list[Tag],
    threshold: float,
    top_k: int,
) -> list[Tag]:
    """Sort by score desc, apply threshold and top_k once at the end."""
    filtered = [t for t in tags if t.score >= threshold]
    filtered.sort(key=lambda t: t.score, reverse=True)
    return filtered[:top_k]
