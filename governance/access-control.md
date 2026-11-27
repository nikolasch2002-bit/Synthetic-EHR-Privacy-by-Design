# Access control

> Built as if the data were real patients' data. Drafted by the assistant, 2026-11-27, from the owner's choices for week 7; for the owner's review.

Who may read what, enforced **inside the database** (PostgreSQL roles, grants and row-level security), so no application code can show more than its role allows. A test (`tests/test_access.py`) takes on each role and checks the matrix below cell by cell.

## Roles

| Role | Who | Why |
| --- | --- | --- |
| `clinician_<dept>` | A clinician of one department: `internal_medicine`, `cardiology`, `nephrology`, `emergency` | Treats patients, so needs their identifiable record, but only of patients they treat |
| `researcher` | An analyst | Needs the data for analysis, not who it is about: the pseudonymized marts only |
| `data_steward` | The person accountable for the data | Reads everything, and is the only one who can re-link a pseudonym to a person, which is logged |
| `public_app` | The public (hosted) app | Only suppressed aggregates |
| `etl` | The loading and build jobs | Writes every layer; cannot read the audit log |

The roles have no login (`nologin`). A person or app logs in as its own user, made a member of one role. The tests take on a role with `SET ROLE`, which gives exactly that role's privileges.

## Matrix

Cells: **all**: every row; **own patients**: only patients with at least one visit in the role's department, with their full record; **read, insert**: may read and add rows, never change or delete them; **none**: refused.

| Role | `ehr` | `ehr_identity` | `ehr_link` | `marts` | `ml` | `marts_public` | `security.relink_log` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `clinician_<dept>` | own patients | own patients | none | none | none | none | none |
| `researcher` | none | none | none | all | all | all | none |
| `data_steward` | all | all | all | all | all | all | read, insert |
| `public_app` | none | none | none | none | none | all | none |
| `etl` | all | all | all | all | all | all | none |

## How each cell is enforced

- **Grants decide which schemas and tables a role can touch.** Anything not granted is refused.
- **Row-level security decides which rows a clinician sees.** `security.care_relation` lists each clinician role with the patients it treats (a visit in its department), rebuilt with every load. A clinician reads only its own rows of it, and every patient-level table's policy asks "is there a care relation for this patient?". Rows keyed to a visit or an order (diagnoses, lab results) are visible when their parent row is. There is no function a clinician could call to ask about another department's patients.
- **Where the protections are made.** The source tables are rebuilt by the loader, so their grants and policies are made by the loader in the same transaction (`security/ehr_access.sql`). The marts are rebuilt by dbt, so each table's grant is made in its own `post_hook`, and the schema grants once, before any model runs (`dbt/macros/grant_read.sql`). The roles and the audit log belong to no rebuilt table, so a script creates them first (`security/roles.sql`). A protection is never added afterwards by a separate step, which would leave a rebuilt table open until it ran.

## Re-linking and its audit

Only `data_steward` can turn a pseudonym back into a person, with `security.relink(pseudonym)`. Each call adds a row to `security.relink_log`: when, which role, which pseudonym. The function runs as its caller (`security invoker`), so the log records who really did it, and any other role is refused. The steward can read the log and add to it (through the function), but cannot update or delete it. `etl` cannot read it at all.

## Small-cell suppression

`marts_public` holds aggregates only. Any count below **k = 10** is published as empty (`null`), with `is_suppressed = true`, and so is a rate computed from such a count. Zero is suppressed too. No totals or margins are published, so a hidden count cannot be worked out by subtracting the others (primary suppression only, by the owner's choice; complementary suppression is not done).

## Known limits

- Roles are cluster-wide in PostgreSQL: the same roles serve the local database and its `_test` database.
- With real data, re-linking would also need a stated purpose per lookup, and review of the log by someone other than the steward.
- The admin user that owns the tables (`ehr_admin`) is not limited by any of this: it is the database owner, used only by the build.
