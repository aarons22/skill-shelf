from app.config import Settings


def test_provider_secret_env_vars_do_not_break_settings(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "PORT=3000",
                "PUBLIC_BASE_URL=http://localhost",
                "SKILLSHELF_GITHUB_CLIENT_SECRET=provider-secret",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.public_base_url == "http://localhost"
