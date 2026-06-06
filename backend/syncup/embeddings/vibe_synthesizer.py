"""Vibe synthesis: call an LLM to generate taste archetype and summary.

Produces vibe_summary, archetype, and key_themes from a user's top items.
Stored on the users table — explanation layer only, NOT a match score input.

Provider: any OpenAI-compatible API (default: DeepSeek).
Graceful degradation: if llm_api_key is None, synthesis is silently skipped.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from syncup.db.models import Item, PreferenceOverride, User, UserItem

logger = logging.getLogger(__name__)

_MAX_ITEMS_PER_SERVICE = 5
_MAX_TOTAL_ITEMS = 20

_STORE_VIBE_TOOL = {
    "type": "function",
    "function": {
        "name": "store_vibe",
        "description": "Store the synthesised vibe profile for this user.",
        "parameters": {
            "type": "object",
            "properties": {
                "vibe_summary": {
                    "type": "string",
                    "description": "2-3 sentence description of this person's taste.",
                },
                "archetype": {
                    "type": "string",
                    "description": "Short label such as 'The Patient Aesthete'.",
                },
                "key_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 5,
                    "description": "3-5 thematic strings that capture recurring motifs.",
                },
            },
            "required": ["vibe_summary", "archetype", "key_themes"],
        },
    },
}


@dataclass(frozen=True)
class VibeItem:
    name: str
    item_type: str
    service: str


@dataclass(frozen=True)
class VibeResult:
    vibe_summary: str
    archetype: str
    key_themes: list[str]


# ---------------------------------------------------------------------------
# Item selection
# ---------------------------------------------------------------------------


def _select_top_items(db: DbSession, user_id: uuid.UUID) -> list[VibeItem]:
    """Return up to _MAX_TOTAL_ITEMS items for LLM input.

    Rules:
    - Skip excluded items (user_items.excluded = true)
    - Apply boost_multiplier before ranking (from preference_overrides)
    - Cap at _MAX_ITEMS_PER_SERVICE per service
    - Cap at _MAX_TOTAL_ITEMS globally, taking the highest-scored across services
    """
    rows = db.execute(
        select(
            Item.name,
            Item.item_type,
            Item.service,
            UserItem.engagement_score,
            PreferenceOverride.boost_multiplier,
        )
        .join(Item, UserItem.item_id == Item.id)
        .outerjoin(
            PreferenceOverride,
            and_(
                PreferenceOverride.user_id == user_id,
                PreferenceOverride.item_id == UserItem.item_id,
            ),
        )
        .where(
            UserItem.user_id == user_id,
            UserItem.excluded == False,  # noqa: E712
        )
    ).all()

    # Group by service, compute effective score, sort within each service
    by_service: dict[str, list[tuple[float, VibeItem]]] = defaultdict(list)
    for row in rows:
        effective = row.engagement_score * (
            row.boost_multiplier if row.boost_multiplier is not None else 1.0
        )
        by_service[row.service].append(
            (effective, VibeItem(name=row.name, item_type=row.item_type, service=row.service))
        )

    # Take top _MAX_ITEMS_PER_SERVICE per service, then pick global top
    candidates: list[tuple[float, VibeItem]] = []
    for service_items in by_service.values():
        service_items.sort(key=lambda x: x[0], reverse=True)
        candidates.extend(service_items[:_MAX_ITEMS_PER_SERVICE])

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in candidates[:_MAX_TOTAL_ITEMS]]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(items: list[VibeItem]) -> str:
    lines = [f"- {it.name} ({it.service}, {it.item_type})" for it in items]
    return "Here are this user's top cultural interests:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM call (OpenAI-compatible tool use)
# ---------------------------------------------------------------------------


def _call_llm(
    prompt: str,
    *,
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
) -> VibeResult:
    """Call an OpenAI-compatible LLM with tool-use and return a parsed VibeResult."""
    response = httpx.post(
        f"{llm_base_url.rstrip('/')}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {llm_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cultural taste analyst. Analyse the user's top interests "
                        "and synthesise their vibe. Be specific and insightful — avoid "
                        "generic descriptions."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "tools": [_STORE_VIBE_TOOL],
            "tool_choice": {"type": "function", "function": {"name": "store_vibe"}},
            "max_tokens": 400,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    args_str = data["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    args = json.loads(args_str)
    return VibeResult(
        vibe_summary=args["vibe_summary"],
        archetype=args["archetype"],
        key_themes=args["key_themes"],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def synthesize_vibe(
    db_factory: sessionmaker[DbSession],
    user_id: uuid.UUID,
    llm_api_key: str | None,
    llm_base_url: str = "https://api.deepseek.com",
    llm_model: str = "deepseek-chat",
) -> VibeResult | None:
    """Synthesise vibe for a user and persist to the users table.

    Returns the VibeResult on success, None if skipped or on any error.
    Safe to run as a background task — never raises.
    """
    if not llm_api_key:
        return None

    db = db_factory()
    try:
        items = _select_top_items(db, user_id)
        if not items:
            logger.info("Vibe synthesis skipped for user %s: no eligible items", user_id)
            return None

        prompt = _build_prompt(items)
        result = _call_llm(
            prompt,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
        )

        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                vibe_summary=result.vibe_summary,
                archetype=result.archetype,
                key_themes=result.key_themes,
                vibe_computed_at=datetime.now(UTC),
            )
        )
        db.commit()
        logger.info("Vibe synthesis done for user %s — archetype: %s", user_id, result.archetype)
        return result

    except Exception:
        logger.exception("Vibe synthesis failed for user %s", user_id)
        db.rollback()
        return None

    finally:
        db.close()
