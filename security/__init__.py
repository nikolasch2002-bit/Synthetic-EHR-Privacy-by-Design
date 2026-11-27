"""Roles, grants, row-level security and the re-linking audit (spec, "Security
and compliance deliverables"). The SQL is in this folder; these helpers run it."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROLES_SQL = (HERE / "roles.sql").read_text(encoding="utf-8")
EHR_ACCESS_SQL = (HERE / "ehr_access.sql").read_text(encoding="utf-8")


def apply_roles(conn) -> None:
    """Create the roles and the persistent security objects (idempotent)."""
    conn.execute(ROLES_SQL)


def apply_ehr_access(conn) -> None:
    """Grants and row-level security on the freshly loaded source schemas."""
    conn.execute(EHR_ACCESS_SQL)
