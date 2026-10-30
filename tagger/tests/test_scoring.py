import pytest
from google.cloud import vision

from tagger.scoring import collect_tags, normalize_label, rank_tags


def _label(desc: str, score: float = 0.0, topicality: float = 0.0) -> vision.EntityAnnotation:
    return vision.EntityAnnotation(description=desc, score=score, topicality=topicality)


def _obj(name: str, score: float) -> vision.LocalizedObjectAnnotation:
    return vision.LocalizedObjectAnnotation(name=name, score=score)


def test_normalize_label_strips_punctuation_and_case() -> None:
    assert normalize_label("  Cane!  ") == "cane"
    assert normalize_label("Prato, verde.") == "prato verde"


def test_collect_prefers_topicality_over_score() -> None:
    response = vision.AnnotateImageResponse(
        label_annotations=[_label("cane", score=0.4, topicality=0.9)]
    )
    tags = collect_tags(response)
    assert len(tags) == 1
    assert tags[0].score == pytest.approx(0.9)


def test_collect_dedupes_and_keeps_highest() -> None:
    response = vision.AnnotateImageResponse(
        label_annotations=[_label("cane", topicality=0.5)],
        localized_object_annotations=[_obj("Cane", 0.8)],
    )
    tags = collect_tags(response)
    assert len(tags) == 1
    assert tags[0].score == pytest.approx(0.8)
    assert tags[0].source == "object"


def test_collect_uses_aliases() -> None:
    response = vision.AnnotateImageResponse(
        label_annotations=[_label("automobile", topicality=0.6), _label("auto", topicality=0.4)]
    )
    tags = collect_tags(response, aliases={"automobile": "auto"})
    assert len(tags) == 1
    assert tags[0].score == pytest.approx(0.6)


def test_rank_applies_threshold_and_top_k() -> None:
    response = vision.AnnotateImageResponse(
        label_annotations=[
            _label("a", topicality=0.9),
            _label("b", topicality=0.5),
            _label("c", topicality=0.2),
        ]
    )
    tags = collect_tags(response)
    ranked = rank_tags(tags, threshold=0.3, top_k=1)
    assert [t.tag for t in ranked] == ["a"]
