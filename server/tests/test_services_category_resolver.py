"""CategoryResolver — Korean keyword → category_code mapping regression."""

from __future__ import annotations

from server.services.category_resolver import CategoryResolver


def test_default_korean_keywords_resolve(category_resolver_default: CategoryResolver) -> None:
    assert category_resolver_default.resolve("이 동네 카페 어때?") == "CS100001"
    assert category_resolver_default.resolve("한식집이 잘 될까") == "CS200001"
    assert category_resolver_default.resolve("편의점 추천") == "CS300001"


def test_unknown_keyword_returns_none(category_resolver_default: CategoryResolver) -> None:
    assert category_resolver_default.resolve("우주선 가게") is None


def test_resolve_name_returns_keyword_string(category_resolver_default: CategoryResolver) -> None:
    assert category_resolver_default.resolve_name("커피 한 잔") == "커피"
    assert category_resolver_default.resolve_name("치킨집 알려줘") == "치킨"
    assert category_resolver_default.resolve_name("우주선") is None


def test_get_category_resolver_singleton_reuses_instance() -> None:
    from server.services.category_resolver import (
        get_category_resolver,
        set_category_resolver,
    )

    a = get_category_resolver()
    b = get_category_resolver()
    assert a is b
    # Reset singleton at end so other tests are isolated
    fresh = CategoryResolver()
    fresh.load_defaults()
    set_category_resolver(fresh)
