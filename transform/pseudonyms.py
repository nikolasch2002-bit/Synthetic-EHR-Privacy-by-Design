"""Keyed pseudonyms: HMAC-SHA-256 of the internal patient ID, with a key kept outside the database.

Why keyed, and not a plain hash: patient IDs are small integers, so anyone
could hash 1 to 1,000,000 and reverse a plain hash in seconds. With a secret
key, only someone holding the key can compute, and so re-link, a pseudonym.

Why here, in Python, and not in SQL: computing it in the database would put
the key in the SQL text, and from there in dbt's compiled files and logs
(docs/lessons-learned.md). So the key never reaches the database or dbt.
This step writes only the link, patient_id -> pseudonym, to `ehr_link`,
which only the data steward will read (from week 7). dbt joins on it.
"""

import hashlib
import hmac
import os

import psycopg

KEY_HEX_LENGTH = 64  # 32 bytes, the size of the SHA-256 output
PREFIX = "SYN-P-"  # invented identifiers start with SYN- (CLAUDE.md)

LINK_SQL = """
create schema if not exists ehr_link;
drop table if exists ehr_link.patient_pseudonym;
create table ehr_link.patient_pseudonym (
    patient_id integer primary key references ehr.patient,
    pseudonym text not null unique check (pseudonym ~ '^SYN-P-[0-9a-f]{16}$')
);
-- Only the steward reads the link (it is what re-linking uses); etl writes it.
grant usage on schema ehr_link to data_steward, etl;
grant select on ehr_link.patient_pseudonym to data_steward;
grant select, insert, update, delete on ehr_link.patient_pseudonym to etl;
"""


def pseudonym_key() -> bytes:
    """PSEUDONYM_KEY from the environment: 64 hex characters. Never printed."""
    value = os.environ.get("PSEUDONYM_KEY", "")
    if len(value) != KEY_HEX_LENGTH:
        raise RuntimeError(f"PSEUDONYM_KEY must be {KEY_HEX_LENGTH} hex characters")
    return bytes.fromhex(value)


def pseudonym(patient_id: int, key: bytes) -> str:
    """The patient's pseudonym. 16 hex characters (64 bits) keep collisions
    negligible for any population this project makes; a unique constraint
    on the link table would catch one anyway."""
    # "patient:" separates this use of the key from any other it might get.
    digest = hmac.new(key, f"patient:{patient_id}".encode(), hashlib.sha256).hexdigest()
    return PREFIX + digest[:16]


def write_links(url: str, key: bytes) -> int:
    """Rebuild ehr_link.patient_pseudonym for every patient. Returns the row count."""
    with psycopg.connect(url) as conn:
        conn.execute(LINK_SQL)
        ids = [
            row[0]
            for row in conn.execute("select patient_id from ehr.patient order by 1")
        ]
        with (
            conn.cursor() as cur,
            cur.copy("copy ehr_link.patient_pseudonym from stdin") as copy,
        ):
            for patient_id in ids:
                copy.write_row((patient_id, pseudonym(patient_id, key)))
        return len(ids)
