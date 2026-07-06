import pytest

from src.config import REPO_ROOT, MissingApiKeyError, api_key


def test_repo_root_is_the_project_root():
    assert (REPO_ROOT / "SPEC.md").exists()
    assert (REPO_ROOT / "pyproject.toml").exists()


def test_missing_key_raises_helpful_error(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError, match="EIA_API_KEY"):
        api_key("EIA_API_KEY")


def test_present_key_is_returned(monkeypatch):
    monkeypatch.setenv("NREL_API_KEY", "abc123")
    assert api_key("NREL_API_KEY") == "abc123"
