"""Build the marts: write the pseudonym links, then run `dbt build`.

dbt reads its connection from environment variables set here from
DATABASE_URL. The password goes in DBT_ENV_SECRET_PG_PASSWORD: dbt scrubs
variables with that prefix from its logs. The pseudonym key is never
passed to dbt at all (see pseudonyms.py).
"""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg
from dbt.cli.main import dbtRunner

from transform.pseudonyms import write_links

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"


class DbtError(Exception):
    pass


def dbt_environment(url: str) -> dict[str, str]:
    parts = urlparse(url)
    return {
        "DBT_PG_HOST": parts.hostname or "127.0.0.1",
        "DBT_PG_PORT": str(parts.port or 5432),
        "DBT_PG_USER": unquote(parts.username or ""),
        "DBT_ENV_SECRET_PG_PASSWORD": unquote(parts.password or ""),
        "DBT_PG_DBNAME": parts.path.lstrip("/"),
        # Also set in dbt_project.yml: no usage statistics sent to dbt Labs.
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "False",
    }


def dbt(url: str, *args: str) -> None:
    """Run a dbt command against the database in `url`; raise if it fails."""
    os.environ.update(dbt_environment(url))
    result = dbtRunner().invoke(
        [
            *args,
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(DBT_DIR),
            "--quiet",
        ]
    )
    if not result.success:
        raise DbtError(
            f"dbt {' '.join(args)} failed: {result.exception or 'see the output above'}"
        )


def build(url: str, key: bytes) -> int:
    """Pseudonyms, then every seed, model and dbt test. Returns the patients linked.

    The marts schema is dropped first, so every build starts from empty: a
    model that was renamed or removed leaves no stale table behind, and a
    seed whose column types changed is created afresh.
    """
    with psycopg.connect(url) as conn:
        conn.execute("drop schema if exists marts cascade")
    linked = write_links(url, key)
    dbt(url, "build")
    return linked
