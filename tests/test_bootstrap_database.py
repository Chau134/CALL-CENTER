from pathlib import Path

import pytest

from src.bootstrap_database import DatabaseSettings, load_settings


def write_env(path: Path, password: str = "local_test_password") -> None:
    path.write_text(
        "\n".join(
            (
                "POSTGRES_HOST=localhost",
                "POSTGRES_PORT=5432",
                "POSTGRES_DB=call_center_wfm",
                "POSTGRES_USER=postgres",
                f"POSTGRES_PASSWORD={password}",
            )
        ),
        encoding="utf-8",
    )


def test_load_settings_reads_valid_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file)
    for key in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(env_file)

    assert settings == DatabaseSettings(
        host="localhost",
        port=5432,
        database="call_center_wfm",
        user="postgres",
        password="local_test_password",
    )


def test_load_settings_rejects_placeholder_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, password="replace_with_local_password")
    for key in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError, match="placeholder"):
        load_settings(env_file)
