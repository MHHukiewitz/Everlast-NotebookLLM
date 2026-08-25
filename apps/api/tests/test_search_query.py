from app.services.search_query import (
    RETRY_WEB_SYSTEM,
    WEB_REWRITE_SYSTEM,
    clean_search_query,
    looks_like_web_query,
    rewrite_route,
    strip_web_query,
)


def test_clean_search_query_takes_first_line() -> None:
    assert clean_search_query('"KI Beratung DACH Firmen"\nMehr Text', "fallback") == "KI Beratung DACH Firmen"
    assert clean_search_query("   ", "Ursprung") == "Ursprung"


def test_rewrite_route_uses_hetzner_small_model(monkeypatch) -> None:
    monkeypatch.setattr("app.services.search_query.settings.search_rewrite_provider", "")
    monkeypatch.setattr("app.services.search_query.settings.search_rewrite_model", "Qwen3.8-27B")
    monkeypatch.setattr("app.services.search_query.settings.hetzner_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.search_query.settings.hetzner_models",
        "Qwen/Qwen3.6-35B-A3B-FP8,Qwen3.8-27B",
    )
    assert rewrite_route() == ("hetzner", "Qwen3.8-27B")


def test_strip_web_query_drops_research_verbs() -> None:
    assert strip_web_query("recherchiere wichtige mitbewerber von everlast") == "wichtige mitbewerber von everlast"
    assert strip_web_query("Bitte research the company history") == "the company history"
    assert strip_web_query("suche im web nach Everlast Consulting") == "Everlast Consulting"
    assert looks_like_web_query("Everlast Consulting KI Mitbewerber Deutschland")
    assert not looks_like_web_query("recherchiere wichtige mitbewerber von everlast")
    assert "gleichnamigen Marken" in WEB_REWRITE_SYSTEM
    assert "andere Suchanfrage" in RETRY_WEB_SYSTEM
