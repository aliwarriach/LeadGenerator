from app.core.config import Settings, effective_cors_origins


def test_development_keeps_the_localhost_dev_origins():
    settings = Settings(environment="development")
    assert effective_cors_origins(settings) == settings.cors_allowed_origins
    assert effective_cors_origins(settings) != []


def test_production_defaults_to_no_cors_origins_when_unset():
    """A deployed environment must not silently inherit the localhost dev
    origins — see SecurityIssues.md L-1. A same-origin deployment (the
    documented case) needs none."""
    settings = Settings(environment="production")
    assert effective_cors_origins(settings) == []


def test_staging_defaults_to_no_cors_origins_when_unset():
    settings = Settings(environment="staging")
    assert effective_cors_origins(settings) == []


def test_production_honors_an_explicitly_configured_origin_list():
    settings = Settings(environment="production", cors_allowed_origins=["https://app.example.com"])
    assert effective_cors_origins(settings) == ["https://app.example.com"]


def test_production_honors_an_explicitly_configured_empty_origin_list():
    settings = Settings(environment="production", cors_allowed_origins=[])
    assert effective_cors_origins(settings) == []
