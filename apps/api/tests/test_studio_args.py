import uuid

import pytest

from app.services.studio.generate import source_ids_from_args, topic_from_args


def test_topic_from_args_prefers_prompt() -> None:
    assert topic_from_args({"prompt": "Nur DSGVO", "topic": "Alt", "focus": "Fokus"}) == "Nur DSGVO"


def test_topic_from_args_falls_back() -> None:
    assert topic_from_args({"focus": "Fokus"}) == "Fokus"
    assert topic_from_args({"topic": "Thema"}) == "Thema"
    assert topic_from_args({}, "Standard") == "Standard"


def test_source_ids_from_args_none_means_selected() -> None:
    assert source_ids_from_args({}) is None


def test_source_ids_from_args_parses_list() -> None:
    first = uuid.uuid4()
    ids = source_ids_from_args({"source_ids": [str(first)]})
    assert ids == [first]


def test_source_ids_from_args_rejects_object() -> None:
    with pytest.raises(ValueError, match="Liste"):
        source_ids_from_args({"source_ids": {"id": "x"}})
