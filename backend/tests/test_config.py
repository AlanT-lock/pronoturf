from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
    settings = Settings()
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_key == "test-key"
