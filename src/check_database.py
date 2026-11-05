"""Check connectivity and required project schemas without exposing secrets."""

from __future__ import annotations

import psycopg

from bootstrap_database import PROJECT_SCHEMAS, connection_kwargs, load_settings


def main() -> None:
    settings = load_settings()
    with psycopg.connect(
        **connection_kwargs(settings, settings.database)
    ) as connection:
        database = connection.execute("SELECT current_database()").fetchone()[0]
        rows = connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = ANY(%s)
            ORDER BY schema_name
            """,
            (list(PROJECT_SCHEMAS),),
        ).fetchall()

    schemas = [row[0] for row in rows]
    missing = sorted(set(PROJECT_SCHEMAS) - set(schemas))
    if missing:
        raise RuntimeError(f"Missing project schemas: {', '.join(missing)}")

    print(f"Database connection OK: {database}")
    print(f"Verified schemas: {', '.join(schemas)}")


if __name__ == "__main__":
    main()
