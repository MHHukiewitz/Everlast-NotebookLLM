from types import SimpleNamespace

from app.services.retrieve import (
    LOW_SCORE,
    merge_chunks,
    query_tokens,
    search_is_weak,
    select_diverse_chunks,
    title_boost,
)


def test_title_boost_matches_query_name() -> None:
    tokens = query_tokens("Ist Mike Hukiewitz ein Kandidat für Everlast?")
    assert title_boost("CVMikeHukiewitz.pdf", tokens) == 0.2
    assert title_boost("Datenschutz-Grundverordnung", tokens) == 0.0


def test_select_diverse_chunks_caps_per_source() -> None:
    rows = [
        SimpleNamespace(source_id="cv", text="a"),
        SimpleNamespace(source_id="cv", text="b"),
        SimpleNamespace(source_id="cv", text="c"),
        SimpleNamespace(source_id="cv", text="d"),
        SimpleNamespace(source_id="everlast", text="e"),
        SimpleNamespace(source_id="everlast", text="f"),
        SimpleNamespace(source_id="other", text="g"),
        SimpleNamespace(source_id="other", text="h"),
    ]
    picked = select_diverse_chunks(rows, limit=8, per_source=3)
    counts = {}
    for row in picked:
        counts[row.source_id] = counts.get(row.source_id, 0) + 1
    assert counts["cv"] >= 3
    assert counts["everlast"] == 2
    assert counts["other"] == 2
    assert len(picked) == 8


def test_search_is_weak_for_empty_or_low_score() -> None:
    assert search_is_weak([], 4) is True
    assert search_is_weak([{"score": LOW_SCORE - 0.01, "source_id": "a"}], 4) is True
    assert search_is_weak([{"score": 0.8, "source_id": "a"}], 3) is False
    assert search_is_weak([{"score": 0.8, "source_id": "a"}], 12) is True


def test_merge_chunks_dedupes_and_caps() -> None:
    first = [{"chunk_id": "1", "text": "a"}, {"chunk_id": "2", "text": "b"}]
    second = [{"chunk_id": "2", "text": "dup"}, {"chunk_id": "3", "text": "c"}]
    merged = merge_chunks(first, second, limit=2)
    assert [item["chunk_id"] for item in merged] == ["1", "2"]
