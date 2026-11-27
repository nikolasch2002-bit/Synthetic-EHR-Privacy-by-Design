"""Publish: copy the marts_public tables, and nothing else, to the hosted database.

The hosted database is the only place data leaves this machine (spec,
"Architecture", boundary 5), so it gets only the suppressed aggregates. The
script refuses to run if the target already holds anything outside
marts_public: it never decides on its own that something there may be
deleted. After it runs, `hosted_contents` lists what is there, for the test.
"""

import psycopg

SCHEMA = "marts_public"
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

# Every table, view, materialized view, sequence and foreign table outside
# the system schemas: "what is in this database".
CONTENTS_SQL = """
select n.nspname, c.relname, c.relkind
from pg_class as c
inner join pg_namespace as n on n.oid = c.relnamespace
where c.relkind in ('r', 'p', 'v', 'm', 'S', 'f')
    and n.nspname <> all(%s)
    and n.nspname not like 'pg_temp%%'
    and n.nspname not like 'pg_toast%%'
order by 1, 2
"""


class PublishRefused(Exception):
    pass


def hosted_contents(conn) -> list[tuple[str, str, str]]:
    """(schema, name, kind) of every relation outside the system schemas."""
    return conn.execute(CONTENTS_SQL, (list(SYSTEM_SCHEMAS),)).fetchall()


def source_tables(conn) -> list[str]:
    rows = conn.execute(
        "select table_name from information_schema.tables "
        "where table_schema = %s and table_type = 'BASE TABLE' order by 1",
        (SCHEMA,),
    ).fetchall()
    return [r[0] for r in rows]


def column_definitions(conn, table: str) -> str:
    rows = conn.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = %s and table_name = %s order by ordinal_position",
        (SCHEMA, table),
    ).fetchall()
    return ", ".join(f'"{name}" {kind}' for name, kind in rows)


def publish(source_url: str, target_url: str) -> dict[str, int]:
    """Replace marts_public in the target with the source's. Returns rows per table."""
    with psycopg.connect(source_url) as source, psycopg.connect(target_url) as target:
        foreign = [r for r in hosted_contents(target) if r[0] != SCHEMA]
        if foreign:
            raise PublishRefused(
                f"the target holds {len(foreign)} object(s) outside {SCHEMA}; remove them first"
            )
        target.execute(f"drop schema if exists {SCHEMA} cascade")
        target.execute(f"create schema {SCHEMA}")
        counts = {}
        for table in source_tables(source):
            target.execute(
                f"create table {SCHEMA}.{table} ({column_definitions(source, table)})"
            )
            with (
                source.cursor() as out_cur,
                out_cur.copy(f"copy {SCHEMA}.{table} to stdout") as out_copy,
                target.cursor() as in_cur,
                in_cur.copy(f"copy {SCHEMA}.{table} from stdin") as in_copy,
            ):
                for chunk in out_copy:
                    in_copy.write(chunk)
            counts[table] = target.execute(
                f"select count(*) from {SCHEMA}.{table}"
            ).fetchone()[0]
        # The hosted app logs in as public_app: let it read, and nothing more.
        has_role = target.execute(
            "select 1 from pg_roles where rolname = 'public_app'"
        ).fetchone()
        if has_role:
            target.execute(f"grant usage on schema {SCHEMA} to public_app")
            target.execute(
                f"grant select on all tables in schema {SCHEMA} to public_app"
            )
    return counts
