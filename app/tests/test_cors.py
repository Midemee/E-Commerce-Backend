import pytest

from app.config.cors import get_allowed_origins, DEFAULT_ORIGINS


class TestAllowedOrigins:

    def test_defaults_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        assert get_allowed_origins() == DEFAULT_ORIGINS

    def test_reads_comma_separated_origins_from_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://shop.example.com/")

        assert get_allowed_origins() == ["http://localhost:5173", "https://shop.example.com"]

    def test_wildcard_is_rejected(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,*")

        with pytest.raises(RuntimeError):
            get_allowed_origins()

    def test_returned_defaults_are_a_copy(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        get_allowed_origins().append("http://evil.example.com")

        assert "http://evil.example.com" not in get_allowed_origins()