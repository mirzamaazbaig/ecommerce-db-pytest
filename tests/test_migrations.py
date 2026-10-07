"""The application's setup and migration scripts, run on throw-away databases."""
import psycopg
import pytest
from psycopg import errors

from framework import scratch
from framework.config import APP_REPO

pytestmark = [
    pytest.mark.migrations,
    pytest.mark.skipif(not APP_REPO, reason="APP_REPO (checkout of the application) is not set"),
]


def build(url, *, seed=True):
    assert scratch.node("db/setup.js", url).returncode == 0
    if seed:
        assert scratch.node("scripts/seedProducts.js", url).returncode == 0


def query(url, sql, params=()):
    with psycopg.connect(url, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def test_a_new_database_can_be_built_and_migrated():
    with scratch.database() as url:
        build(url)
        result = scratch.node("scripts/migrate.js", url)
        assert result.returncode == 0, result.stderr
        constraints = {r[0] for r in query(url, "SELECT conname FROM pg_constraint WHERE contype = 'c'")}
        assert {"products_stock_nonnegative", "order_items_quantity_positive", "users_role_known"} <= constraints


def test_running_the_migrations_twice_is_harmless():
    with scratch.database() as url:
        build(url)
        assert scratch.node("scripts/migrate.js", url).returncode == 0
        again = scratch.node("scripts/migrate.js", url)
        assert again.returncode == 0, again.stderr


def test_setup_can_run_twice_without_duplicating_the_categories():
    with scratch.database() as url:
        build(url, seed=False)
        assert scratch.node("db/setup.js", url).returncode == 0
        assert query(url, "SELECT count(*) FROM categories")[0][0] == 3


def test_migrating_again_does_not_add_the_dummy_reviews_again():
    with scratch.database() as url:
        build(url)
        query(url, "INSERT INTO users (email, password_hash) SELECT 'm' || g || '@example.com', 'x' FROM generate_series(1, 3) g")
        assert scratch.node("scripts/migrate.js", url).returncode == 0
        first = query(url, "SELECT count(*) FROM reviews")[0][0]
        assert first > 0, "the seed should have added reviews for the existing users"
        assert scratch.node("scripts/migrate.js", url).returncode == 0
        assert query(url, "SELECT count(*) FROM reviews")[0][0] == first


def test_the_constraints_migration_refuses_existing_bad_data_instead_of_hiding_it():
    with scratch.database() as url:
        build(url)
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(scratch.migration_sql("001_add_modern_features.sql"))
            conn.execute("INSERT INTO products (name, price, stock, category_id) VALUES ('bad', 1, -5, 1)")
            with pytest.raises(errors.CheckViolation):
                conn.execute(scratch.migration_sql("002_add_integrity_constraints.sql"))
