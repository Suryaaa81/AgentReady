"""Regression test: types.Part.from_text is keyword-only (text=...),
not positional. A positional call crashes every /agent/chat turn."""

from __future__ import annotations

import pytest

genai = pytest.importorskip(
    "google.genai", reason="google-genai not installed; see pyproject.toml"
)

from app.services.agent import _to_gemini_contents  # noqa: E402


def test_to_gemini_contents_builds_valid_parts():
    messages = [
        {"role": "user", "content": "Find me running shoes"},
        {"role": "assistant", "content": "Sure, searching now."},
    ]
    contents = _to_gemini_contents(messages)
    assert len(contents) == 2
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Find me running shoes"
    assert contents[1].role == "model"


def test_to_gemini_contents_normalizes_unknown_role_to_user():
    contents = _to_gemini_contents([{"role": "system", "content": "be helpful"}])
    assert contents[0].role == "user"


def test_to_gemini_contents_skips_messages_with_no_content():
    contents = _to_gemini_contents(
        [{"role": "user", "content": None}, {"role": "user", "content": "hi"}]
    )
    assert len(contents) == 1
