"""Tests for services/propose_features.py.

All LLM calls are intercepted by patching ``services.llm.chat_json``.
No real OpenAI calls are made.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from models.llm_schemas import FeatureProposal, FeatureProposalList
from models.repo_snapshot import FileEntry, RepoSnapshot
from services.propose_features import (
    BANNED_TITLE_WORDS,
    _build_context,
    _slugify,
    propose_features,
)
from services.signals import EntryPoint, ReadingHeading, RepoSignals, RouteSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _snapshot(files: list[str] | None = None) -> RepoSnapshot:
    file_list = [FileEntry(path=p, size=100, content="") for p in (files or ["src/app.py", "src/auth.py"])]
    return RepoSnapshot(
        owner="acme",
        repo="myapp",
        default_branch="main",
        commit_sha="abcdef1234567890",
        files=file_list,
    )


def _signals(
    headings: list[str] | None = None,
    routes: list[tuple[str, str, str]] | None = None,
) -> RepoSignals:
    rh = [ReadingHeading(level=2, text=h) for h in (headings or [])]
    rs = [
        RouteSignal(method=m, path=p, file_path=f, line_no=1)
        for m, p, f in (routes or [])
    ]
    return RepoSignals(readme_headings=rh, routes=rs, entrypoints=[])


def _proposal(id_: str, title: str, desc: str = "A feature.", paths: list[str] | None = None) -> FeatureProposal:
    return FeatureProposal(id=id_, title=title, description=desc, seed_paths=paths or [])


def _proposal_list(*proposals: FeatureProposal) -> FeatureProposalList:
    return FeatureProposalList(features=list(proposals))


# ---------------------------------------------------------------------------
# _slugify (unit)
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_spaces_become_hyphens(self):
        assert _slugify("user authentication") == "user-authentication"

    def test_uppercase_lowercased(self):
        assert _slugify("UserAuth") == "userauth"

    def test_special_chars_stripped(self):
        assert _slugify("search & discovery!") == "search-discovery"

    def test_already_valid_slug_unchanged(self):
        assert _slugify("real-time-notifications") == "real-time-notifications"

    def test_leading_trailing_hyphens_stripped(self):
        assert _slugify(" - hello - ") == "hello"

    def test_empty_string(self):
        assert _slugify("") == ""


# ---------------------------------------------------------------------------
# _build_context (unit)
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_contains_repo_name(self):
        ctx = _build_context(_snapshot(), RepoSignals())
        assert "acme/myapp" in ctx

    def test_contains_commit_sha_prefix(self):
        ctx = _build_context(_snapshot(), RepoSignals())
        assert "abcdef1" in ctx

    def test_contains_readme_headings(self):
        signals = _signals(headings=["Getting Started", "API Reference"])
        ctx = _build_context(_snapshot(), signals)
        assert "Getting Started" in ctx
        assert "API Reference" in ctx

    def test_contains_routes(self):
        signals = _signals(routes=[("POST", "/api/login", "auth.py")])
        ctx = _build_context(_snapshot(), signals)
        assert "/api/login" in ctx

    def test_contains_file_paths(self):
        snap = _snapshot(files=["src/auth.py", "src/models.py"])
        ctx = _build_context(snap, RepoSignals())
        assert "src/auth.py" in ctx
        assert "src/models.py" in ctx

    def test_file_list_capped_at_100(self):
        files = [f"file{i}.py" for i in range(150)]
        snap = _snapshot(files=files)
        ctx = _build_context(snap, RepoSignals())
        assert "50 more files" in ctx

    def test_entrypoints_included(self):
        signals = RepoSignals(entrypoints=[EntryPoint(kind="npm-script", name="start", command="node index.js")])
        ctx = _build_context(_snapshot(), signals)
        assert "start" in ctx
        assert "node index.js" in ctx


# ---------------------------------------------------------------------------
# propose_features – happy path
# ---------------------------------------------------------------------------


class TestProposeFeaturesHappyPath:
    def _mock_llm(self, proposals: list[FeatureProposal]):
        return patch("services.llm.chat_json", return_value=_proposal_list(*proposals))

    def test_returns_feature_proposal_list(self):
        proposals = [_proposal("auth", "User Authentication")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert isinstance(result, FeatureProposalList)

    def test_features_passed_through(self):
        proposals = [
            _proposal("auth", "User Authentication"),
            _proposal("search", "Search & Discovery"),
        ]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        titles = [f.title for f in result.features]
        assert "User Authentication" in titles
        assert "Search & Discovery" in titles

    def test_slugs_normalised(self):
        proposals = [_proposal("User Auth", "User Authentication")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert result.features[0].id == "user-auth"

    def test_slug_falls_back_to_title_if_id_empty(self):
        proposals = [_proposal("", "Real-time Notifications")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert result.features[0].id == "real-time-notifications"

    def test_seed_paths_preserved(self):
        paths = ["src/auth.py", "src/models.py"]
        proposals = [_proposal("auth", "User Authentication", paths=paths)]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert result.features[0].seed_paths == paths

    def test_description_preserved(self):
        proposals = [_proposal("auth", "User Authentication", desc="Users can log in securely.")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert result.features[0].description == "Users can log in securely."


# ---------------------------------------------------------------------------
# propose_features – banned word filtering
# ---------------------------------------------------------------------------


class TestBannedWordFiltering:
    def _mock_llm(self, proposals: list[FeatureProposal]):
        return patch("services.llm.chat_json", return_value=_proposal_list(*proposals))

    def test_banned_word_utils_filtered(self):
        proposals = [
            _proposal("utils", "Utils"),
            _proposal("auth", "User Authentication"),
        ]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        titles = [f.title for f in result.features]
        assert "Utils" not in titles
        assert "User Authentication" in titles

    def test_banned_word_helpers_filtered(self):
        proposals = [_proposal("helpers", "Helpers"), _proposal("login", "Login Flow")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert all(f.title != "Helpers" for f in result.features)

    def test_banned_word_frontend_filtered(self):
        proposals = [_proposal("fe", "Frontend"), _proposal("dash", "Dashboard")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert all(f.title != "Frontend" for f in result.features)

    def test_banned_word_backend_filtered(self):
        proposals = [_proposal("be", "Backend"), _proposal("api", "API Access")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert all(f.title != "Backend" for f in result.features)

    def test_banned_word_components_filtered(self):
        proposals = [_proposal("comp", "UI Components"), _proposal("onboard", "User Onboarding")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert all("Components" not in f.title for f in result.features)

    def test_banned_word_case_insensitive(self):
        proposals = [_proposal("u", "UTILS"), _proposal("auth", "Authentication")]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        titles = [f.title for f in result.features]
        assert "UTILS" not in titles

    def test_all_banned_returns_empty_list(self):
        proposals = [
            _proposal("u", "Utils"),
            _proposal("h", "Helpers"),
            _proposal("f", "Frontend"),
        ]
        with self._mock_llm(proposals):
            result = propose_features(_snapshot(), RepoSignals())
        assert result.features == []

    def test_banned_words_set_contains_expected_words(self):
        for word in ("utils", "helpers", "frontend", "backend", "components", "middleware"):
            assert word in BANNED_TITLE_WORDS


# ---------------------------------------------------------------------------
# propose_features – LLM call contract
# ---------------------------------------------------------------------------


class TestLLMCallContract:
    def test_llm_called_once(self):
        proposals = [_proposal("auth", "User Authentication")]
        with patch("services.llm.chat_json", return_value=_proposal_list(*proposals)) as mock_llm:
            propose_features(_snapshot(), RepoSignals())
        mock_llm.assert_called_once()

    def test_llm_called_with_feature_proposal_list_schema(self):
        proposals = [_proposal("auth", "User Auth")]
        with patch("services.llm.chat_json", return_value=_proposal_list(*proposals)) as mock_llm:
            propose_features(_snapshot(), RepoSignals())
        _, call_args, _ = mock_llm.mock_calls[0]
        # Third positional argument is the schema
        assert call_args[2] is FeatureProposalList

    def test_context_contains_repo_name_in_user_message(self):
        proposals = [_proposal("auth", "User Auth")]
        with patch("services.llm.chat_json", return_value=_proposal_list(*proposals)) as mock_llm:
            propose_features(_snapshot(), RepoSignals())
        user_msg = mock_llm.call_args[0][1]
        assert "acme/myapp" in user_msg

    def test_llm_value_error_propagates(self):
        with patch("services.llm.chat_json", side_effect=ValueError("bad JSON")):
            with pytest.raises(ValueError, match="bad JSON"):
                propose_features(_snapshot(), RepoSignals())
