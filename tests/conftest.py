"""Shared fixtures for the database tests: one test database, loaded once.

The tests use their own database (`<name>_test`, next to the one in
DATABASE_URL), so they never touch the full local load. Without a database
they skip locally, but fail in CI: there a missing prerequisite must fail.
"""

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from generator.config import load_config
from generator.output import write_dataset
from loader.load import load

# Enough patients for the marts and the questions to have something to count.
DB_TEST_POPULATION = 600


@pytest.fixture(scope="session")
def url() -> str:
    load_dotenv()
    base = os.environ.get("DATABASE_URL")
    if not base:
        if os.environ.get("CI"):
            pytest.fail("DATABASE_URL is not set in CI")
        pytest.skip("no DATABASE_URL: start the database (README) to run these tests")
    name = base.rsplit("/", 1)[1].split("?")[0]
    test_name = f"{name}_test"
    with psycopg.connect(base, autocommit=True) as conn:
        exists = conn.execute(
            "select 1 from pg_database where datname = %s", (test_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'create database "{test_name}"')
    return base.rsplit("/", 1)[0] + "/" + test_name


@pytest.fixture(scope="session")
def dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("data")
    write_dataset(load_config(), out, DB_TEST_POPULATION)
    return out


@pytest.fixture(scope="session")
def loaded(url, dataset) -> dict[str, int]:
    return load(dataset, url)


@pytest.fixture
def conn(url, loaded):
    with psycopg.connect(url) as c:
        yield c
        c.rollback()  # every test leaves the loaded data as it was
