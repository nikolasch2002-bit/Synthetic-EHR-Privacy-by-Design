---
status: accepted
date: 2026-11-26
decision-makers: Nick Christoforakis
---

# Store the data in PostgreSQL and build the marts with dbt

<!-- Drafted by the assistant from the owner's decision; reviewed and accepted by the owner, 2026-11-26. -->

## Context and Problem Statement

The project needs a database for the normalized `ehr` schema and the analytical marts, and a way to build the marts from the source schema. The governance pack claims role-based access, row-level security and a public layer that sees only suppressed aggregates, and each claim must be proven by a test. Which database and transform tool make those claims provable?

## Decision Drivers

* Access control must be enforced, and testable, where the data lives, not only in the app.
* Each transform needs tests, a known build order and documentation.
* The tools should match what analytics and health data jobs use.
* Everything must run free: locally, in CI and hosted.

## Considered Options

* PostgreSQL + dbt
* PostgreSQL + plain SQL scripts
* DuckDB + dbt

## Decision Outcome

Chosen option: **PostgreSQL + dbt**, because Postgres enforces roles, grants and row-level security inside the database, where a test can connect as each role and check what it sees, and dbt gives build order, tests, docs and lineage without writing them by hand.

### Consequences

* Good, because every access-control claim gets a test that connects as the role it is about.
* Good, because CI can start a fresh Postgres per run from the seed, with no hosted database and no database secrets.
* Good, because dbt's docs and tests support the data dictionary check.
* Bad, because there are two tools to learn instead of one.
* Bad, because dbt drops and recreates tables on every build, which removes policies, grants and triggers attached to them. Every protection on a dbt-built table must therefore be created by dbt in a `post_hook`, in the same step as the table; otherwise a rebuild would leave the table open.

### Confirmation

* CI runs `dbt build` on a fresh Postgres on every push.
* The role tests run after a full rebuild, so a protection that a rebuild removes makes them fail.

## Pros and Cons of the Options

### PostgreSQL + dbt

* Good, because roles, grants, row-level security and views are native.
* Good, because dbt is widely used in analytics engineering.
* Bad, because of the rebuild trap above.

### PostgreSQL + plain SQL scripts

* Good, because there is less to learn and every step is visible.
* Good, because scripts that only add and change avoid the rebuild trap.
* Bad, because build order, tests, docs and lineage must all be written by hand.

### DuckDB + dbt

* Good, because it is a single file with no server: the easiest setup and CI.
* Bad, because DuckDB has no roles, grants or row-level security. Access control would live in app code, and anyone with the file could read everything, which undermines the project's main claim.
