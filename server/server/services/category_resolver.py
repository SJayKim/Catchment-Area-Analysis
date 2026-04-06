"""CategoryResolver — resolves Korean keywords to category codes.

In mock mode, uses built-in defaults. In real mode, loads from DB.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Default Korean keyword → category_code mapping (used in mock mode)
_DEFAULT_KEYWORDS: dict[str, str] = {
    "카페": "CS100001",
    "커피": "CS100001",
    "한식": "CS200001",
    "중식": "CS200002",
    "일식": "CS200003",
    "양식": "CS200004",
    "분식": "CS200006",
    "치킨": "CS200010",
    "편의점": "CS300001",
    "미용": "CS400001",
    "약국": "CS500001",
    "주점": "CS200009",
    "제과": "CS200014",
}


class CategoryResolver:
    """Resolve natural-language category keywords to category codes."""

    def __init__(self) -> None:
        self._keywords: dict[str, str] = {}

    def load_defaults(self) -> None:
        """Load built-in keyword mappings (mock mode)."""
        self._keywords = dict(_DEFAULT_KEYWORDS)

    async def load_from_db(self, session_factory) -> None:
        """Load keywords from category_metadata table (real mode).

        Falls back to defaults if the table is empty.
        """
        from sqlalchemy import select

        from server.models.category import CategoryMetadata

        try:
            async with session_factory() as session:
                rows = await session.execute(
                    select(
                        CategoryMetadata.category_code,
                        CategoryMetadata.category_name,
                        CategoryMetadata.aliases,
                    )
                )
                count = 0
                for row in rows.all():
                    # category_name: "커피전문점/카페" → split by /
                    for part in row.category_name.split("/"):
                        keyword = part.strip()
                        if len(keyword) >= 2:
                            self._keywords[keyword] = row.category_code
                            count += 1
                    # aliases: "스벅,투썸,카공" → individual keywords
                    if row.aliases:
                        for alias in row.aliases.split(","):
                            alias = alias.strip()
                            if alias:
                                self._keywords[alias] = row.category_code
                                count += 1

                if count == 0:
                    logger.warning("category_metadata table is empty, using defaults")
                    self.load_defaults()
                else:
                    logger.info(f"Loaded {count} category keywords from DB")
        except Exception:
            logger.warning("Failed to load categories from DB, using defaults", exc_info=True)
            self.load_defaults()

    def resolve(self, message: str) -> str | None:
        """Return the first matching category_code, or None."""
        for kw, code in self._keywords.items():
            if kw in message:
                return code
        return None

    def resolve_name(self, message: str) -> str | None:
        """Return the first matching keyword string, or None."""
        for kw in self._keywords:
            if kw in message:
                return kw
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_resolver: CategoryResolver | None = None


def get_category_resolver() -> CategoryResolver:
    """Get the global CategoryResolver instance.

    If not yet initialized (e.g., during import-time usage), returns a
    resolver loaded with defaults.
    """
    global _resolver
    if _resolver is None:
        _resolver = CategoryResolver()
        _resolver.load_defaults()
    return _resolver


def set_category_resolver(resolver: CategoryResolver) -> None:
    """Set the global CategoryResolver instance (called from lifespan)."""
    global _resolver
    _resolver = resolver
