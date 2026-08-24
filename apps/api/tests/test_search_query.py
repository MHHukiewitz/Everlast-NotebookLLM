from app.services.search_query import clean_search_query, rewrite_route


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
