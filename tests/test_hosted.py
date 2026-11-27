"""The real hosted database (Neon): only marts_public is there, and the
hosted app's login can read it and do nothing else.

Runs only where HOSTED_DATABASE_URL and HOSTED_PUBLIC_APP_URL are in .env
(the owner's machine). CI has no hosted database and no hosted secrets, by
design (spec, "Technology stack"), so there these tests are skipped.
Run `python -m publish` first: they check what was published.
"""

from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values
from streamlit.testing.v1 import AppTest

from publish.publish import hosted_contents

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = dotenv_values(ROOT / ".env")
OWNER_URL = SETTINGS.get("HOSTED_DATABASE_URL")
APP_URL = SETTINGS.get("HOSTED_PUBLIC_APP_URL")

pytestmark = pytest.mark.skipif(
    not (OWNER_URL and APP_URL),
    reason="no hosted database settings (only on the owner's machine)",
)


def test_the_hosted_database_holds_only_marts_public():
    with psycopg.connect(OWNER_URL) as c:
        contents = hosted_contents(c)
    assert contents, "nothing published: run `python -m publish`"
    assert {schema for schema, _, _ in contents} == {"marts_public"}
    assert {kind for _, _, kind in contents} == {"r"}  # tables only


def test_the_hosted_login_has_no_power_beyond_logging_in():
    with psycopg.connect(OWNER_URL) as c:
        rights = c.execute(
            "select rolsuper, rolcreaterole, rolcreatedb, rolbypassrls from pg_roles "
            "where rolname = 'public_app'"
        ).fetchone()
        groups = c.execute(
            "select count(*) from pg_auth_members as m inner join pg_roles as u on u.oid = m.member "
            "where u.rolname = 'public_app'"
        ).fetchone()[0]
    assert rights == (False, False, False, False)
    assert groups == 0


def test_the_hosted_login_reads_marts_public_and_cannot_write():
    with psycopg.connect(APP_URL, autocommit=True) as c:
        assert c.execute("select current_user").fetchone()[0] == "public_app"
        assert (
            c.execute("select count(*) from marts_public.public_rule_score").fetchone()[
                0
            ]
            > 0
        )
        for sql in (
            "create table public.probe (id int)",
            "create table marts_public.probe (id int)",
            "delete from marts_public.public_rule_score",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)


def test_the_hosted_app_shows_every_public_page_from_neon(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120)
    app.secrets["database_url"] = APP_URL
    app.run()
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        assert not app.warning, page
