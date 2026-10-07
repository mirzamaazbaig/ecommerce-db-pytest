"""The database itself must reject invalid data, whatever the application does.

Each statement runs in a savepoint that is undone, so nothing is stored.
The last section covers the safeguards added by migration 002 (see docs/FINDINGS.md). While they were missing,
these tests were written as expected failures (`xfail`, strict), so the build would turn red the moment a gap
was closed and the marker had to be removed. That is what happened; they are plain tests now.
"""
import psycopg
import pytest
from psycopg import errors

from framework import db, factories as f

pytestmark = pytest.mark.constraints


def rejected_with(conn, kind, sql, params=()):
    error = db.attempt(conn, sql, params)
    assert error is not None, "the database accepted invalid data"
    assert isinstance(error, kind), f"rejected, but with {type(error).__name__}: {error}"


# ---- safeguards that exist ---------------------------------------------------------------------------------

def test_a_valid_order_with_a_line_is_accepted(conn):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user, 20)
    assert f.order_line(conn, order, product, quantity=2, price=10)


def test_email_must_be_present(conn):
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO users (email, password_hash) VALUES (NULL, 'x')")


def test_password_hash_must_be_present(conn):
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO users (email, password_hash) VALUES ('a@example.com', NULL)")


def test_email_must_be_unique(conn):
    f.user(conn)
    email = conn.execute("SELECT email FROM users ORDER BY id DESC LIMIT 1").fetchone()[0]
    rejected_with(conn, errors.UniqueViolation, "INSERT INTO users (email, password_hash) VALUES (%s, 'x')", (email,))


def test_a_product_needs_a_name_and_a_price(conn):
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO products (name, price) VALUES (NULL, 1)")
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO products (name, price) VALUES ('x', NULL)")


def test_a_product_needs_an_existing_category(conn):
    rejected_with(conn, errors.ForeignKeyViolation,
                  "INSERT INTO products (name, price, category_id) VALUES ('x', 1, 99999)")


def test_an_order_needs_an_existing_user(conn):
    rejected_with(conn, errors.ForeignKeyViolation, "INSERT INTO orders (user_id, total_amount) VALUES (99999999, 1)")


def test_an_order_line_needs_an_existing_order_and_product(conn):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user)
    rejected_with(conn, errors.ForeignKeyViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (99999999, %s, 1, 1)", (product,))
    rejected_with(conn, errors.ForeignKeyViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, 99999999, 1, 1)", (order,))


def test_an_order_line_needs_a_quantity_and_a_price(conn):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user)
    rejected_with(conn, errors.NotNullViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, NULL, 1)", (order, product))
    rejected_with(conn, errors.NotNullViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, 1, NULL)", (order, product))


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_a_review_rating_must_be_1_to_5(conn, rating):
    user, product = f.user(conn), f.product(conn)
    rejected_with(conn, errors.CheckViolation,
                  "INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, %s, 'x')", (user, product, rating))


@pytest.mark.parametrize("rating", [1, 3, 5])
def test_ratings_inside_the_range_are_accepted(conn, rating):
    user, product = f.user(conn), f.product(conn)
    assert db.attempt(conn, "INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, %s, 'x')",
                      (user, product, rating)) is None


def test_a_product_can_be_wishlisted_once_per_user(conn):
    user, product = f.user(conn), f.product(conn)
    conn.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user, product))
    rejected_with(conn, errors.UniqueViolation, "INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user, product))


def test_category_names_are_unique(conn):
    rejected_with(conn, errors.UniqueViolation, "INSERT INTO categories (name) VALUES ('Books')")


# ---- delete rules --------------------------------------------------------------------------------------------

def test_deleting_a_product_removes_its_reviews_and_wishlist_entries(conn):
    user, product = f.user(conn), f.product(conn)
    conn.execute("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, 5, 'x')", (user, product))
    conn.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user, product))
    conn.execute("DELETE FROM products WHERE id = %s", (product,))
    assert db.scalar(conn, "SELECT count(*) FROM reviews WHERE product_id = %s", (product,)) == 0
    assert db.scalar(conn, "SELECT count(*) FROM wishlist WHERE product_id = %s", (product,)) == 0


def test_a_product_that_has_been_ordered_cannot_be_deleted(conn):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user)
    f.order_line(conn, order, product)
    rejected_with(conn, errors.ForeignKeyViolation, "DELETE FROM products WHERE id = %s", (product,))


def test_a_user_with_orders_cannot_be_deleted(conn):
    user = f.user(conn)
    f.order(conn, user)
    rejected_with(conn, errors.ForeignKeyViolation, "DELETE FROM users WHERE id = %s", (user,))


def test_deleting_a_user_removes_their_reviews_and_wishlist(conn):
    user, product = f.user(conn), f.product(conn)
    conn.execute("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, 4, 'x')", (user, product))
    conn.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user, product))
    conn.execute("DELETE FROM users WHERE id = %s", (user,))
    assert db.scalar(conn, "SELECT count(*) FROM reviews WHERE user_id = %s", (user,)) == 0
    assert db.scalar(conn, "SELECT count(*) FROM wishlist WHERE user_id = %s", (user,)) == 0


# ---- safeguards added by migration 002 (were missing, see docs/FINDINGS.md) ---------------------------------

def test_stock_cannot_be_negative(conn):
    rejected_with(conn, errors.CheckViolation, "INSERT INTO products (name, price, stock) VALUES ('x', 1, -1)")


def test_stock_cannot_be_null(conn):
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO products (name, price, stock) VALUES ('x', 1, NULL)")


def test_a_price_cannot_be_negative(conn):
    rejected_with(conn, errors.CheckViolation, "INSERT INTO products (name, price) VALUES ('x', -0.01)")


@pytest.mark.parametrize("quantity", [0, -1])
def test_an_order_line_quantity_must_be_positive(conn, quantity):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user)
    rejected_with(conn, errors.CheckViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, %s, 1)",
                  (order, product, quantity))


def test_an_order_line_price_cannot_be_negative(conn):
    user, product = f.user(conn), f.product(conn)
    order = f.order(conn, user)
    rejected_with(conn, errors.CheckViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, 1, -1)",
                  (order, product))


def test_an_order_line_must_belong_to_an_order_and_a_product(conn):
    rejected_with(conn, errors.NotNullViolation,
                  "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (NULL, NULL, 1, 1)")


def test_an_order_total_cannot_be_negative(conn):
    user = f.user(conn)
    rejected_with(conn, errors.CheckViolation, "INSERT INTO orders (user_id, total_amount) VALUES (%s, -5)", (user,))


def test_an_order_must_belong_to_a_user(conn):
    rejected_with(conn, errors.NotNullViolation, "INSERT INTO orders (user_id, total_amount) VALUES (NULL, 5)")


@pytest.mark.parametrize("role", ["superuser", "", "ADMIN"])
def test_a_user_role_must_be_user_or_admin(conn, role):
    rejected_with(conn, errors.CheckViolation,
                  "INSERT INTO users (email, password_hash, role) VALUES ('role@example.com', 'x', %s)", (role,))
