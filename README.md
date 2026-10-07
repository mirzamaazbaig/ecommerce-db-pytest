# E-Commerce Database Tests: Python and pytest

Database-level tests for the PostgreSQL schema of a React, Express and PostgreSQL online shop ([application under test](https://github.com/mirzamaazbaig/Ecom)). They check that the database protects itself, that data written through the API stays consistent, and that the migrations behave. 73 tests.

## What it shows

- **Schema contract** (`tests/test_schema.py`): tables, column types, primary keys, unique constraints and every foreign key with its delete rule (`CASCADE` vs `NO ACTION`) are compared with a readable specification, read from `information_schema` and `pg_catalog`.
- **Constraint behaviour** (`tests/test_constraints.py`): invalid rows (NULLs, duplicates, bad foreign keys, out-of-range ratings, negative stock, zero quantities) must be rejected with the right kind of error. Every statement runs in a savepoint that is undone, inside a transaction that is rolled back, so tests leave nothing behind and run in any order.
- **Integrity of application data** (`tests/test_integrity.py`): orders are placed through the API, then SQL checks that totals equal the sum of the lines, that the price stored is the catalogue price rather than the client's, that stock drops by exactly the quantities ordered, that refused orders leave no rows, and that six concurrent buyers cannot oversell.
- **Migrations** (`tests/test_migrations.py`): the application's own scripts run on throw-away databases: a new database builds and migrates, migrating twice is harmless, a re-run does not duplicate seed data, and the constraints migration refuses existing bad data instead of hiding it.
- **Gaps as strict expected failures:** a missing safeguard was first written as the behaviour we want and marked `xfail(strict=True)`. See [`docs/FINDINGS.md`](docs/FINDINGS.md).

## Findings

The first run found a defect and seven missing safeguards. All are fixed in the application ([`docs/FINDINGS.md`](docs/FINDINGS.md)), most importantly:

- deleting a product that customers have ordered returned a server error (now `409`);
- stock, prices, quantities, totals and user roles had no database-level rules, which is how the earlier overselling defect (D1) could put stock below zero.

## Run it

```bash
# 1. Build the application's database and start its API (see the application's README):
#    node db/setup.js && node scripts/migrate.js && node scripts/seedProducts.js && node index.js
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:password@localhost:5432/ecom_db
export API_URL=http://localhost:5000/api          # default
export APP_REPO=/path/to/Ecom                     # needed by the migration tests only
pytest                                            # everything
pytest -m schema                                  # structure only
pytest -m "constraints or migrations"             # no API needed
```

Without the API the integrity tests are skipped; without `APP_REPO` the migration tests are skipped. The HTML report is written to `reports/report.html`.

## Verification

- 73 tests pass three times in a row.
- Mutation checks: putting the unguarded seed back into migration 001 fails the "no duplicate reviews" test; removing the stock constraint from migration 002 fails the build and refuse-bad-data tests.
- Before the fixes, 12 constraint tests and the delete test were expected failures; after migration 002 and the controller fix they turned into failures (strict), the markers were removed, and everything passed.
- The whole application suite (197 tests) passes on a database built with the new migration.

## Structure

```
framework/   config.py  db.py (connect, attempt, scalar)  factories.py  api.py  scratch.py (throw-away databases)
tests/       test_schema  test_constraints  test_integrity  test_migrations
conftest.py  fixtures: conn (rolled-back transaction), shop (admin, products, customers, cleanup)
docs/FINDINGS.md
.github/workflows/db-tests.yml
```
