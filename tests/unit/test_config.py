from reponyx.config import Settings


def test_settings_use_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.openai_api_key is None
    assert settings.model_config["env_prefix"] == "REPONYX_"
