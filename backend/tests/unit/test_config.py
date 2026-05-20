from app.config import Settings


def test_settings_load_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(["PORT=3000", "PUBLIC_BASE_URL=http://localhost"]))

    settings = Settings(_env_file=env_file)

    assert settings.public_base_url == "http://localhost"
