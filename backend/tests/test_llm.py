"""Tests for services/llm.py.

All tests are fully isolated — no real OpenAI calls are made.
The ``_set_client`` escape-hatch is used to inject mock clients.
``time.sleep`` is patched to keep retry tests fast.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import openai
import pytest

import services.llm as llm_module
from services.llm import chat_json, chat_text, strip_fences, _set_client
from models.llm_schemas import FeatureProposalList, WikiPageDraft, EvidenceSelection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(content: str):
    """Build a minimal fake openai ChatCompletion response."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _mock_client(content: str) -> MagicMock:
    """Return a mock openai.OpenAI whose completions.create returns *content*."""
    client = MagicMock()
    client.chat.completions.create.return_value = _make_response(content)
    return client


# ---------------------------------------------------------------------------
# strip_fences (unit)
# ---------------------------------------------------------------------------


class TestStripFences:
    def test_no_fences_returns_stripped(self):
        assert strip_fences('  {"a": 1}  ') == '{"a": 1}'

    def test_json_fence_removed(self):
        text = '```json\n{"a": 1}\n```'
        assert strip_fences(text) == '{"a": 1}'

    def test_plain_fence_removed(self):
        text = '```\n{"a": 1}\n```'
        assert strip_fences(text) == '{"a": 1}'

    def test_content_with_newlines_preserved(self):
        text = '```json\n{\n  "key": "value"\n}\n```'
        result = strip_fences(text)
        assert '"key"' in result
        assert '"value"' in result

    def test_empty_string(self):
        assert strip_fences("") == ""

    def test_plain_text_no_json_unchanged(self):
        text = "Here is some prose without fences."
        assert strip_fences(text) == text.strip()

    def test_only_inner_content_returned(self):
        """Text before/after fences is discarded."""
        text = 'Some preamble\n```json\n{"x": 2}\n```\nsome suffix'
        assert strip_fences(text) == '{"x": 2}'


# ---------------------------------------------------------------------------
# chat_text
# ---------------------------------------------------------------------------


class TestChatText:
    def setup_method(self):
        _set_client(None)  # reset before each test

    def teardown_method(self):
        _set_client(None)

    def test_returns_response_text(self):
        _set_client(_mock_client("Hello from LLM!"))
        result = chat_text("You are helpful.", "Say hello.")
        assert result == "Hello from LLM!"

    def test_passes_system_and_user_messages(self):
        client = _mock_client("ok")
        _set_client(client)
        chat_text("sys prompt", "user prompt")
        create_call = client.chat.completions.create
        _, kwargs = create_call.call_args
        messages = kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "sys prompt"}
        assert messages[1] == {"role": "user", "content": "user prompt"}

    def test_uses_default_model(self):
        client = _mock_client("ok")
        _set_client(client)
        chat_text("s", "u")
        _, kwargs = client.chat.completions.create.call_args
        assert kwargs["model"] == llm_module.DEFAULT_MODEL

    def test_none_content_returns_empty_string(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response(None)
        _set_client(client)
        result = chat_text("s", "u")
        assert result == ""


# ---------------------------------------------------------------------------
# chat_json – successful cases
# ---------------------------------------------------------------------------


class TestChatJsonSuccess:
    def setup_method(self):
        _set_client(None)

    def teardown_method(self):
        _set_client(None)

    def test_returns_validated_schema(self):
        payload = '{"features": [{"id": "auth", "title": "Authentication", "description": "Manages login.", "seed_paths": ["auth.py"]}]}'
        _set_client(_mock_client(payload))
        result = chat_json("sys", "user", FeatureProposalList)
        assert isinstance(result, FeatureProposalList)
        assert result.features[0].id == "auth"

    def test_strips_json_fence(self):
        fenced = '```json\n{"title": "Page", "content_md": "# Hello"}\n```'
        _set_client(_mock_client(fenced))
        result = chat_json("sys", "user", WikiPageDraft)
        assert result.title == "Page"
        assert "Hello" in result.content_md

    def test_strips_plain_fence(self):
        fenced = '```\n{"title": "Overview", "content_md": "content"}\n```'
        _set_client(_mock_client(fenced))
        result = chat_json("sys", "user", WikiPageDraft)
        assert result.title == "Overview"

    def test_evidence_selection_schema(self):
        payload = '{"selected_chunk_ids": ["auth.py:1-20", "models.py:5-30"], "rationale": "Contains auth logic."}'
        _set_client(_mock_client(payload))
        result = chat_json("sys", "user", EvidenceSelection)
        assert "auth.py:1-20" in result.selected_chunk_ids
        assert result.rationale == "Contains auth logic."

    def test_json_instruction_appended_to_system(self):
        client = _mock_client('{"title": "T", "content_md": "C"}')
        _set_client(client)
        chat_json("Original system prompt.", "user msg", WikiPageDraft)
        _, kwargs = client.chat.completions.create.call_args
        system_content = kwargs["messages"][0]["content"]
        assert "Original system prompt." in system_content
        assert "JSON" in system_content

    def test_uses_json_object_response_format(self):
        client = _mock_client('{"title": "T", "content_md": "C"}')
        _set_client(client)
        chat_json("s", "u", WikiPageDraft)
        _, kwargs = client.chat.completions.create.call_args
        assert kwargs.get("response_format") == {"type": "json_object"}


# ---------------------------------------------------------------------------
# chat_json – error cases
# ---------------------------------------------------------------------------


class TestChatJsonErrors:
    def setup_method(self):
        _set_client(None)

    def teardown_method(self):
        _set_client(None)

    def test_invalid_json_raises_value_error(self):
        _set_client(_mock_client("this is not json at all!!!"))
        with pytest.raises(ValueError, match="non-JSON"):
            chat_json("s", "u", WikiPageDraft)

    def test_schema_mismatch_raises_value_error(self):
        # Valid JSON but missing required fields for WikiPageDraft
        _set_client(_mock_client('{"unexpected_field": "oops"}'))
        with pytest.raises(ValueError, match="WikiPageDraft"):
            chat_json("s", "u", WikiPageDraft)

    def test_empty_response_raises_value_error(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response(None)
        _set_client(client)
        with pytest.raises(ValueError):
            chat_json("s", "u", WikiPageDraft)

    def test_fenced_invalid_json_raises_value_error(self):
        _set_client(_mock_client("```json\nnot { valid json\n```"))
        with pytest.raises(ValueError, match="non-JSON"):
            chat_json("s", "u", WikiPageDraft)


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetry:
    def setup_method(self):
        _set_client(None)

    def teardown_method(self):
        _set_client(None)

    @patch("services.llm.time.sleep")
    def test_retries_on_rate_limit_then_succeeds(self, mock_sleep):
        client = MagicMock()
        # Fail once, then succeed
        client.chat.completions.create.side_effect = [
            openai.RateLimitError("rate limited", response=MagicMock(), body={}),
            _make_response("recovered"),
        ]
        _set_client(client)
        result = chat_text("s", "u")
        assert result == "recovered"
        assert client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("services.llm.time.sleep")
    def test_retries_on_connection_error(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            openai.APIConnectionError(request=MagicMock()),
            _make_response("ok after retry"),
        ]
        _set_client(client)
        result = chat_text("s", "u")
        assert result == "ok after retry"
        assert mock_sleep.call_count == 1

    @patch("services.llm.time.sleep")
    def test_exhausted_retries_raises(self, mock_sleep):
        client = MagicMock()
        # Always fail (MAX_RETRIES + 1 attempts total)
        client.chat.completions.create.side_effect = openai.RateLimitError(
            "always rate limited", response=MagicMock(), body={}
        )
        _set_client(client)
        with pytest.raises(openai.RateLimitError):
            chat_text("s", "u")
        # Should have attempted MAX_RETRIES + 1 = 3 times
        assert client.chat.completions.create.call_count == llm_module.MAX_RETRIES + 1

    @patch("services.llm.time.sleep")
    def test_non_transient_error_not_retried(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.AuthenticationError(
            "bad key", response=MagicMock(), body={}
        )
        _set_client(client)
        with pytest.raises(openai.AuthenticationError):
            chat_text("s", "u")
        # Should only attempt once — no retry for auth errors
        assert client.chat.completions.create.call_count == 1
        mock_sleep.assert_not_called()

    @patch("services.llm.time.sleep")
    def test_retry_delay_increases(self, mock_sleep):
        """Each retry waits longer (linear backoff)."""
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            openai.RateLimitError("1", response=MagicMock(), body={}),
            openai.RateLimitError("2", response=MagicMock(), body={}),
            _make_response("finally"),
        ]
        _set_client(client)
        result = chat_text("s", "u")
        assert result == "finally"
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays[1] > delays[0]  # second wait is longer
