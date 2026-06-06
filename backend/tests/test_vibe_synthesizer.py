"""Tests for Block F: vibe synthesis.

Covers:
- _select_top_items: exclusion filter, per-service cap, boost ranking, global cap
- _build_prompt: content verification
- _call_llm: tool-use parsing, HTTP error propagation
- synthesize_vibe: graceful skip when no key/items, happy path, error recovery
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from syncup.embeddings.vibe_synthesizer import (
    VibeItem,
    VibeResult,
    _build_prompt,
    _call_llm,
    _select_top_items,
    synthesize_vibe,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    name: str,
    item_type: str = "game",
    service: str = "steam",
    engagement_score: float = 0.5,
    boost_multiplier: float | None = None,
) -> MagicMock:
    row = MagicMock()
    row.name = name
    row.item_type = item_type
    row.service = service
    row.engagement_score = engagement_score
    row.boost_multiplier = boost_multiplier
    return row


def _tool_response(
    vibe_summary: str,
    archetype: str,
    key_themes: list[str],
) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": json.dumps(
                                    {
                                        "vibe_summary": vibe_summary,
                                        "archetype": archetype,
                                        "key_themes": key_themes,
                                    }
                                )
                            }
                        }
                    ]
                }
            }
        ]
    }
    return resp


def _make_db_factory(rows: list) -> tuple[MagicMock, MagicMock]:
    """Return (factory, db) where db.execute().all() yields rows."""
    db = MagicMock()
    db.execute.return_value.all.return_value = rows
    factory = MagicMock(return_value=db)
    return factory, db


# ---------------------------------------------------------------------------
# _select_top_items
# ---------------------------------------------------------------------------


class TestSelectTopItems:
    def test_returns_empty_when_no_items(self) -> None:
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        result = _select_top_items(db, uuid.uuid4())
        assert result == []

    def test_caps_at_five_per_service(self) -> None:
        db = MagicMock()
        rows = [
            _make_row(f"Game {i}", service="steam", engagement_score=float(i)) for i in range(8)
        ]
        db.execute.return_value.all.return_value = rows

        result = _select_top_items(db, uuid.uuid4())

        steam = [r for r in result if r.service == "steam"]
        assert len(steam) <= 5

    def test_takes_highest_scored_items_within_service(self) -> None:
        db = MagicMock()
        rows = [
            _make_row(f"Game {i}", service="steam", engagement_score=float(i)) for i in range(8)
        ]
        db.execute.return_value.all.return_value = rows

        result = _select_top_items(db, uuid.uuid4())
        names = {r.name for r in result}

        # Scores 7,6,5,4,3 are the top 5
        assert "Game 7" in names
        assert "Game 4" in names
        # Scores 2,1,0 are excluded
        assert "Game 2" not in names

    def test_boost_multiplier_elevates_item_into_top_five(self) -> None:
        db = MagicMock()
        # 5 items at score=0.9, 1 item at score=0.1 but boost=10.0 → effective=1.0
        rows = [_make_row(f"Item {i}", service="steam", engagement_score=0.9) for i in range(5)]
        rows.append(
            _make_row("Boosted", service="steam", engagement_score=0.1, boost_multiplier=10.0)
        )
        db.execute.return_value.all.return_value = rows

        result = _select_top_items(db, uuid.uuid4())
        names = {r.name for r in result}

        assert "Boosted" in names

    def test_global_cap_at_twenty(self) -> None:
        db = MagicMock()
        # 10 services × 5 items = 50 eligible rows → must cap at 20
        rows = []
        for svc in range(10):
            for i in range(5):
                rows.append(
                    _make_row(f"S{svc}-{i}", service=f"svc_{svc}", engagement_score=float(i))
                )
        db.execute.return_value.all.return_value = rows

        result = _select_top_items(db, uuid.uuid4())

        assert len(result) <= 20

    def test_returns_vibe_items(self) -> None:
        db = MagicMock()
        db.execute.return_value.all.return_value = [
            _make_row("Disco Elysium", item_type="game", service="steam")
        ]
        result = _select_top_items(db, uuid.uuid4())
        assert len(result) == 1
        assert isinstance(result[0], VibeItem)
        assert result[0].name == "Disco Elysium"
        assert result[0].service == "steam"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_contains_item_names(self) -> None:
        items = [
            VibeItem(name="Disco Elysium", item_type="game", service="steam"),
            VibeItem(name="Godspeed You! Black Emperor", item_type="artist", service="lastfm"),
        ]
        prompt = _build_prompt(items)
        assert "Disco Elysium" in prompt
        assert "Godspeed You! Black Emperor" in prompt

    def test_contains_service_and_type(self) -> None:
        items = [VibeItem(name="Hades", item_type="game", service="steam")]
        prompt = _build_prompt(items)
        assert "steam" in prompt
        assert "game" in prompt

    def test_nonempty(self) -> None:
        items = [VibeItem(name="X", item_type="t", service="s")]
        assert len(_build_prompt(items)) > 10


# ---------------------------------------------------------------------------
# _call_llm
# ---------------------------------------------------------------------------


class TestCallLlm:
    def test_parses_tool_use_response(self) -> None:
        fake_resp = _tool_response(
            vibe_summary="Drawn to melancholy and slow-burn narratives.",
            archetype="The Patient Aesthete",
            key_themes=["melancholy", "slow burn", "agency"],
        )
        with patch("syncup.embeddings.vibe_synthesizer.httpx") as mock_httpx:
            mock_httpx.post.return_value = fake_resp
            result = _call_llm(
                "some prompt",
                llm_api_key="test-key",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
            )

        assert result.vibe_summary == "Drawn to melancholy and slow-burn narratives."
        assert result.archetype == "The Patient Aesthete"
        assert result.key_themes == ["melancholy", "slow burn", "agency"]

    def test_returns_vibe_result_instance(self) -> None:
        fake_resp = _tool_response("Summary.", "Archetype", ["a", "b", "c"])
        with patch("syncup.embeddings.vibe_synthesizer.httpx") as mock_httpx:
            mock_httpx.post.return_value = fake_resp
            result = _call_llm(
                "p",
                llm_api_key="k",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
            )
        assert isinstance(result, VibeResult)

    def test_propagates_http_error(self) -> None:
        with patch("syncup.embeddings.vibe_synthesizer.httpx") as mock_httpx:
            err_resp = MagicMock()
            err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
            mock_httpx.post.return_value = err_resp
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError
            with pytest.raises(httpx.HTTPStatusError):
                _call_llm(
                    "p",
                    llm_api_key="k",
                    llm_base_url="https://api.deepseek.com",
                    llm_model="deepseek-chat",
                )


# ---------------------------------------------------------------------------
# synthesize_vibe
# ---------------------------------------------------------------------------


class TestSynthesizeVibe:
    def test_skips_and_returns_none_when_no_api_key(self) -> None:
        factory = MagicMock()
        result = synthesize_vibe(
            db_factory=factory,
            user_id=uuid.uuid4(),
            llm_api_key=None,
        )
        assert result is None
        factory.assert_not_called()

    def test_skips_llm_when_no_items(self) -> None:
        factory, _ = _make_db_factory([])
        with patch("syncup.embeddings.vibe_synthesizer._call_llm") as mock_llm:
            result = synthesize_vibe(factory, uuid.uuid4(), llm_api_key="key")
        assert result is None
        mock_llm.assert_not_called()

    def test_happy_path_returns_and_stores_result(self) -> None:
        user_id = uuid.uuid4()
        factory, db = _make_db_factory(
            [_make_row("Disco Elysium", service="steam", engagement_score=0.9)]
        )
        expected = VibeResult(
            vibe_summary="Melancholic and thoughtful.",
            archetype="The Patient Aesthete",
            key_themes=["melancholy", "philosophy", "slow burn"],
        )
        with patch("syncup.embeddings.vibe_synthesizer._call_llm", return_value=expected):
            result = synthesize_vibe(factory, user_id, llm_api_key="key")

        assert result == expected
        # DB execute called at least twice: once for item query, once for UPDATE
        assert db.execute.call_count >= 2
        db.commit.assert_called()
        db.close.assert_called()

    def test_handles_llm_error_gracefully(self) -> None:
        factory, db = _make_db_factory([_make_row("Some game")])
        with patch(
            "syncup.embeddings.vibe_synthesizer._call_llm", side_effect=Exception("LLM down")
        ):
            result = synthesize_vibe(factory, uuid.uuid4(), llm_api_key="key")

        assert result is None
        db.rollback.assert_called()
        db.close.assert_called()

    def test_session_always_closed_on_db_error(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("DB exploded")
        factory = MagicMock(return_value=db)

        result = synthesize_vibe(factory, uuid.uuid4(), llm_api_key="key")

        assert result is None
        db.close.assert_called()

    def test_passes_correct_api_args_to_call_llm(self) -> None:
        factory, _ = _make_db_factory([_make_row("Game")])
        fake_result = VibeResult("s", "a", ["t"])
        with patch(
            "syncup.embeddings.vibe_synthesizer._call_llm", return_value=fake_result
        ) as mock_llm:
            synthesize_vibe(
                factory,
                uuid.uuid4(),
                llm_api_key="sk-real",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
            )

        _, kwargs = mock_llm.call_args
        assert kwargs.get("llm_api_key") or mock_llm.call_args.args[1] == "sk-real"
