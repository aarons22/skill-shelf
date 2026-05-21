from app.config import Settings


def test_settings_load_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(["PORT=3000", "PUBLIC_BASE_URL=http://localhost"]))

    settings = Settings(_env_file=env_file)

    assert settings.public_base_url == "http://localhost"


def test_development_cors_allows_any_origin():
    settings = Settings(public_base_url="http://localhost:3000", node_env="development")

    assert settings.cors_allow_origins == ["*"]


def test_production_cors_derives_public_origin():
    settings = Settings(public_base_url="https://skillshelf.example.com/app", node_env="production")

    assert settings.public_origin == "https://skillshelf.example.com"
    assert settings.cors_allow_origins == ["https://skillshelf.example.com"]


def test_secure_cookies_follow_public_base_url_scheme():
    assert Settings(public_base_url="https://skillshelf.example.com", node_env="production").secure_cookies is True
    assert Settings(public_base_url="http://skillshelf.example.com", node_env="production").secure_cookies is False
