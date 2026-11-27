"""The app's hosted/local split (spec, "Security and compliance deliverables").

- Hosted mode, the default: no role switcher and no patient timeline appear,
  and every query runs as public_app, whatever login the app is given.
- The secrets template lists only the public_app login.
- Local mode: the role switcher, and the database decides what each role sees.
"""

import tomllib
from pathlib import Path
from urllib.parse import urlparse

import pytest
from streamlit.testing.v1 import AppTest

from app import db
from app.local_views import PAGES as LOCAL_PAGES
from app.public_views import PAGES as PUBLIC_PAGES

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app" / "streamlit_app.py")


@pytest.fixture
def hosted(built, monkeypatch) -> AppTest:
    """The app in hosted mode, given the test database's admin login as its
    secret: the worst case, a login that could read everything."""
    monkeypatch.delenv("APP_MODE", raising=False)
    app = AppTest.from_file(APP, default_timeout=120)
    app.secrets["database_url"] = built
    return app.run()


@pytest.fixture
def local(built, monkeypatch) -> AppTest:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", built)
    return AppTest.from_file(APP, default_timeout=120).run()


@pytest.mark.parametrize("value", [None, "", "LOCAL", "true", "hosted"])
def test_the_app_is_hosted_unless_told_local_exactly(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("APP_MODE", raising=False)
    else:
        monkeypatch.setenv("APP_MODE", value)
    assert db.mode() == db.HOSTED


def test_hosted_mode_has_no_role_switcher_and_no_timeline(hosted):
    assert not hosted.exception
    assert [s.label for s in hosted.sidebar.selectbox] == []
    pages = hosted.sidebar.radio[0].options
    assert pages == list(PUBLIC_PAGES)
    assert not set(pages) & set(LOCAL_PAGES)
    for page in pages:
        hosted.sidebar.radio[0].set_value(page).run()
        assert not hosted.exception, page
        assert not hosted.warning, page  # public_app may read everything it is shown


def test_hosted_mode_reads_as_public_app_even_with_a_stronger_login(built, monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("HOSTED_PUBLIC_APP_URL", built)  # the admin login, on purpose
    for asked in ("data_steward", "researcher", "clinician_cardiology"):
        with db.connect(asked) as conn:
            assert conn.execute("select current_user").fetchone()[0] == "public_app"
    with pytest.raises(db.Refused):
        db.query("data_steward", "select count(*) from ehr.patient")


def test_the_secrets_template_holds_only_the_public_app_login():
    secrets = tomllib.loads(
        (ROOT / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")
    )
    assert list(secrets) == ["database_url"]
    assert urlparse(secrets["database_url"]).username == "public_app"


def test_local_mode_has_the_role_switcher_and_the_timeline(local):
    assert not local.exception
    assert local.sidebar.selectbox[0].label == "Role"
    assert local.sidebar.selectbox[0].options == db.LOCAL_ROLES
    assert "Patient timeline" in local.sidebar.radio[0].options


@pytest.mark.parametrize(
    "role, refused",
    [
        ("researcher", True),
        ("public_app", True),
        ("data_steward", False),
        ("clinician_cardiology", False),
    ],
)
def test_the_timeline_is_refused_or_shown_by_the_database(local, role, refused):
    local.sidebar.selectbox[0].set_value(role).run()
    local.sidebar.radio[0].set_value("Patient timeline").run()
    assert not local.exception
    assert bool(local.warning) == refused


def test_a_clinicians_timeline_lists_only_its_own_patients(local, built):
    local.sidebar.selectbox[0].set_value("clinician_nephrology").run()
    local.sidebar.radio[0].set_value("Patient timeline").run()
    patients = local.main.selectbox[0].options
    mrns = {p.split()[0] for p in patients}
    own = db.query(
        "data_steward",
        "select i.mrn from ehr_identity.patient_identity as i where exists ("
        "select 1 from ehr.encounter as e inner join ehr.department as d using (department_id) "
        "where e.patient_id = i.patient_id and d.code = 'nephrology')",
    )["mrn"]
    assert mrns and mrns <= set(own)


def test_the_hosted_apps_requirements_match_the_lock_file():
    from importlib.metadata import version

    for line in (
        (ROOT / "app" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    ):
        if not line or line.startswith("#"):
            continue
        name, pinned = line.split("==")
        assert version(name.split("[")[0]) == pinned, name


def test_streamlit_sends_no_usage_statistics():
    config = tomllib.loads(
        (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    )
    assert config["browser"]["gatherUsageStats"] is False
