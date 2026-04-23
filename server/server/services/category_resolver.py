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
        self._session_factory = None  # lazy — set by load_from_db

    def load_defaults(self) -> None:
        """Load built-in keyword mappings (mock mode)."""
        self._keywords = dict(_DEFAULT_KEYWORDS)

    async def load_from_db(self, session_factory) -> None:
        """Load keywords from category_metadata + learned_aliases (real mode).

        Starts with default keywords as a base, then merges DB keywords on top.
        Stores ``session_factory`` on the instance so :meth:`record_learned_alias`
        can write back asynchronously at request time.
        """
        from sqlalchemy import select, text

        from server.models.category import CategoryMetadata

        self._session_factory = session_factory

        # Always start with defaults as base
        self._keywords = dict(_DEFAULT_KEYWORDS)

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

                # GAP-B: learned_aliases (confidence ≥ 0.7 only) — table may
                # not exist on older databases that have not yet run 004.
                try:
                    learned_rows = await session.execute(
                        text("SELECT alias, code FROM learned_aliases WHERE confidence >= 0.7")
                    )
                    for alias, code in learned_rows.all():
                        if alias and code and alias not in self._keywords:
                            self._keywords[alias] = code
                            count += 1
                except Exception:
                    logger.debug("learned_aliases table not available — run alembic 004 to enable")

                if count == 0:
                    logger.info("category_metadata table is empty, using defaults only")
                else:
                    logger.info(
                        "Loaded %d category keywords from DB (merged with %d defaults)",
                        count,
                        len(_DEFAULT_KEYWORDS),
                    )
        except Exception:
            logger.warning("Failed to load categories from DB, using defaults only", exc_info=True)

    async def record_learned_alias(
        self,
        alias: str,
        code: str,
        confidence: float,
        source: str = "llm_gemini_flash",
    ) -> None:
        """Persist a new alias → code mapping so future requests are zero-LLM.

        Idempotent: upsert on the alias primary key, bumps ``hit_count`` and
        ``last_used_at``. Silent no-op when the table is missing or writes fail
        (resolver must not throw from the request path).
        """
        if not self._session_factory or not alias or not code:
            return
        try:
            from sqlalchemy import text

            async with self._session_factory() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO learned_aliases (alias, code, confidence, source)
                        VALUES (:alias, :code, :confidence, :source)
                        ON CONFLICT (alias) DO UPDATE SET
                            hit_count = learned_aliases.hit_count + 1,
                            last_used_at = NOW(),
                            confidence = GREATEST(learned_aliases.confidence, EXCLUDED.confidence)
                        """
                    ),
                    {
                        "alias": alias[:200],
                        "code": code,
                        "confidence": max(0.0, min(1.0, confidence)),
                        "source": source,
                    },
                )
                await session.commit()
            # Reflect in-process so the rest of this request sees it too.
            self._keywords.setdefault(alias, code)
        except Exception:
            logger.debug("record_learned_alias failed (table missing?)", exc_info=True)

    def resolve(self, message: str) -> str | None:
        """Return the first matching category_code, or None."""
        msg_lower = message.lower()
        for kw, code in self._keywords.items():
            if kw.lower() in msg_lower:
                return code
        return None

    def resolve_name(self, message: str) -> str | None:
        """Return the first matching keyword string, or None."""
        msg_lower = message.lower()
        for kw in self._keywords:
            if kw.lower() in msg_lower:
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
