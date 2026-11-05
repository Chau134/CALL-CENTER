"""Create the project database and schemas from environment settings.

This command is idempotent: rerunning it keeps the existing database and
schemas. Credentials are loaded from ``.env`` and are never printed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_ENV_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)
PROJECT_SCHEMAS = ("raw", "staging", "analytics")


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    admin_database: str = "postgres"


def load_settings(env_file: Path = DEFAULT_ENV_FILE) -> DatabaseSettings:
    """Load and validate PostgreSQL connection settings."""
    if not env_file.exists():
        raise FileNotFoundError(
            f"Missing {env_file}. Copy .env.example to .env and add local credentials."
        )

    load_dotenv(env_file, override=False)
    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        raise ValueError(f"Missing required environment keys: {', '.join(missing)}")

    password = os.environ["POSTGRES_PASSWORD"]
    if password == "replace_with_local_password":
        raise ValueError("POSTGRES_PASSWORD still contains the example placeholder")

    try:
        port = int(os.environ["POSTGRES_PORT"])
    except ValueError as error:
        raise ValueError("POSTGRES_PORT must be an integer") from error

    return DatabaseSettings(
        host=os.environ["POSTGRES_HOST"],
        port=port,
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=password,
        admin_database=os.getenv("POSTGRES_ADMIN_DB", "postgres"),
    )


def connection_kwargs(settings: DatabaseSettings, database: str) -> dict[str, object]:
    """Return connection arguments without exposing them in command output."""
    return {
        "host": settings.host,
        "port": settings.port,
        "dbname": database,
        "user": settings.user,
        "password": settings.password,
        "connect_timeout": 5,
    }


def ensure_database(settings: DatabaseSettings) -> bool:
    """Create the configured database when absent; return True when created."""
    with psycopg.connect(
        **connection_kwargs(settings, settings.admin_database), autocommit=True
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.database,)
        ).fetchone()
        if exists:
            return False

        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.database))
        )
        return True


def ensure_schemas(settings: DatabaseSettings) -> None:
    """Create the raw, staging, and analytics schemas when absent."""
    with psycopg.connect(
        **connection_kwargs(settings, settings.database), autocommit=True
    ) as connection:
        for schema_name in PROJECT_SCHEMAS:
            connection.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(schema_name)
                )
            )


def main() -> None:
    settings = load_settings()
    database_created = ensure_database(settings)
    ensure_schemas(settings)

    database_status = "created" if database_created else "already existed"
    print(f"Database {settings.database}: {database_status}")
    print(f"Schemas ready: {', '.join(PROJECT_SCHEMAS)}")


if __name__ == "__main__":
    main()
