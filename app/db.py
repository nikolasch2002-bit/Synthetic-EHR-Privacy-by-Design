"""Which mode the app runs in, and its database connection.

Fail closed: the app is in hosted mode unless APP_MODE is "local". Hosted
mode reads as `public_app` only: if the login it was given is anyone else,
it switches to that role first (a role it cannot take raises an error), so
it can never read more than marts_public. Local mode logs in with the local
DATABASE_URL and takes on the role chosen in the role switcher.
"""

import os
from decimal import Decimal

import pandas as pd
import psycopg
from dotenv import load_dotenv

HOSTED, LOCAL = "hosted", "local"
PUBLIC_ROLE = "public_app"
# The roles the local role switcher offers (governance/access-control.md).
LOCAL_ROLES = [
    "clinician_internal_medicine",
    "clinician_cardiology",
    "clinician_nephrology",
    "clinician_emergency",
    "researcher",
    "data_steward",
    PUBLIC_ROLE,
]


class Refused(Exception):
    """The database refused the query for this role."""


def mode() -> str:
    load_dotenv()
    return LOCAL if os.environ.get("APP_MODE") == LOCAL else HOSTED


def hosted_url() -> str:
    """The public_app login: from Streamlit's secrets when deployed, else from .env."""
    try:
        import streamlit as st

        if "database_url" in st.secrets:
            return st.secrets["database_url"]
    except (ImportError, FileNotFoundError):
        pass
    load_dotenv()
    url = os.environ.get("HOSTED_PUBLIC_APP_URL")
    if not url:
        raise RuntimeError(
            "no database_url in secrets and no HOSTED_PUBLIC_APP_URL in .env"
        )
    return url


def connect(role: str) -> psycopg.Connection:
    """A connection that reads as `role`. In hosted mode the role is always public_app."""
    if mode() == HOSTED:
        role, url = PUBLIC_ROLE, hosted_url()
    else:
        if role not in LOCAL_ROLES:
            raise ValueError(f"unknown role {role}")
        load_dotenv()
        url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(url, autocommit=True)
    if conn.execute("select current_user").fetchone()[0] != role:
        conn.execute(f'set role "{role}"')
    return conn


def query(role: str, sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run one query as `role`. Raises Refused if the database says no."""
    with connect(role) as conn:
        try:
            cur = conn.execute(sql, params)
        except psycopg.errors.InsufficientPrivilege as error:
            raise Refused(str(error).splitlines()[0]) from error
        data = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    # Postgres numeric arrives as Decimal; charts and tables want floats.
    for column in data.columns:
        if any(isinstance(v, Decimal) for v in data[column].head(50)):
            data[column] = data[column].astype(float)
    return data
