"""Data written by the application through the API stays consistent. The checks are SQL queries on the stored rows."""
import concurrent.futures

import pytest

from framework import api, db

pytestmark = pytest.mark.integrity


def rows(sql, params=()):
    with db.connect(autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()


def one(sql, params=()):
    return rows(sql, params)[0][0]


def test_an_order_total_equals_the_sum_of_its_lines(shop):
    a, b = shop.product(price=12.5, stock=10), shop.product(price=7.99, stock=10)
    customer = shop.customer()
    assert api.order(customer, (a, 3), (b, 2)).status_code == 201

    result = rows("""SELECT o.total_amount, sum(i.quantity * i.price_at_purchase), count(*)
                     FROM orders o JOIN order_items i ON i.order_id = o.id WHERE o.user_id = %s GROUP BY o.id""",
                  (customer.id,))
    total, line_sum, lines = result[0]
    assert (float(total), float(line_sum), lines) == (53.48, 53.48, 2)


def test_each_line_stores_the_catalogue_price_not_the_client_price(shop):
    product = shop.product(price=40, stock=5)
    customer = shop.customer()
    api.order(customer, (product, 1))  # the client sends a price of 1
    assert float(one("SELECT i.price_at_purchase FROM order_items i JOIN orders o ON o.id = i.order_id "
                     "WHERE o.user_id = %s", (customer.id,))) == 40


def test_a_later_price_change_does_not_change_stored_orders(shop):
    product = shop.product(price=30, stock=5)
    customer = shop.customer()
    api.order(customer, (product, 1))
    with db.connect(autocommit=True) as conn:
        conn.execute("UPDATE products SET price = 99 WHERE id = %s", (product["id"],))
    assert float(one("SELECT i.price_at_purchase FROM order_items i WHERE i.product_id = %s", (product["id"],))) == 30


def test_stock_drops_by_exactly_the_quantities_ordered(shop):
    product = shop.product(stock=20)
    for quantity in (3, 4, 5):
        assert api.order(shop.customer(), (product, quantity)).status_code == 201
    assert one("SELECT stock FROM products WHERE id = %s", (product["id"],)) == 8
    assert one("SELECT sum(quantity) FROM order_items WHERE product_id = %s", (product["id"],)) == 12


def test_a_refused_order_leaves_no_rows_behind(shop):
    product = shop.product(stock=2)
    customer = shop.customer()
    assert api.order(customer, (product, 5)).status_code == 409
    assert one("SELECT count(*) FROM orders WHERE user_id = %s", (customer.id,)) == 0
    assert one("SELECT stock FROM products WHERE id = %s", (product["id"],)) == 2


def test_a_half_valid_order_is_stored_completely_or_not_at_all(shop):
    ok, short = shop.product(stock=10), shop.product(stock=1)
    customer = shop.customer()
    assert api.order(customer, (ok, 2), (short, 3)).status_code == 409
    assert one("SELECT count(*) FROM orders WHERE user_id = %s", (customer.id,)) == 0
    assert one("SELECT stock FROM products WHERE id = %s", (ok["id"],)) == 10


def test_concurrent_orders_never_oversell(shop):
    product = shop.product(stock=10)
    customers = [shop.customer() for _ in range(6)]
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        codes = list(pool.map(lambda c: api.order(c, (product, 4)).status_code, customers))
    assert sorted(codes) == [201, 201, 409, 409, 409, 409]
    assert one("SELECT stock FROM products WHERE id = %s", (product["id"],)) == 2
    assert one("SELECT sum(quantity) FROM order_items WHERE product_id = %s", (product["id"],)) == 8


def test_order_lines_always_point_at_an_order_and_a_product():
    assert one("SELECT count(*) FROM order_items WHERE order_id IS NULL OR product_id IS NULL") == 0


def test_no_product_has_negative_or_missing_stock():
    assert one("SELECT count(*) FROM products WHERE stock IS NULL OR stock < 0") == 0


def test_no_order_line_has_a_zero_or_negative_quantity():
    assert one("SELECT count(*) FROM order_items WHERE quantity <= 0") == 0


def test_every_review_rating_is_between_1_and_5():
    assert one("SELECT count(*) FROM reviews WHERE rating NOT BETWEEN 1 AND 5") == 0


def test_no_product_is_wishlisted_twice_by_the_same_user():
    assert one("SELECT count(*) FROM (SELECT 1 FROM wishlist GROUP BY user_id, product_id HAVING count(*) > 1) d") == 0


def test_a_registered_password_is_stored_as_a_bcrypt_hash(shop):
    customer = shop.customer()
    stored = one("SELECT password_hash FROM users WHERE id = %s", (customer.id,))
    assert stored.startswith("$2") and len(stored) == 60 and "TestPass123!" not in stored


def test_deleting_a_product_that_has_been_ordered_is_a_clear_conflict_not_a_server_error(shop):
    product = shop.product(stock=5)
    api.order(shop.customer(), (product, 1))
    res = shop.admin.request("DELETE", f"products/{product['id']}")
    assert res.status_code == 409
