import pytest

from framework import api, db


@pytest.fixture
def conn():
    """One transaction per test, always rolled back: tests leave no data behind and cannot disturb each other."""
    connection = db.connect()
    yield connection
    connection.rollback()
    connection.close()


@pytest.fixture(scope="session")
def api_up():
    if not api.available():
        pytest.skip("the API is not running (set API_URL)")


@pytest.fixture
def shop(api_up):
    """An admin and a place to create products and customers; everything is removed afterwards."""
    admin = api.register_admin()
    created = {"products": [], "users": [admin.id]}

    class Shop:
        pass

    Shop.admin = admin

    class Shop(Shop):
        def product(self, **kw):
            product = api.create_product(admin, **kw)
            created["products"].append(product["id"])
            return product

        def customer(self):
            customer = api.register()
            created["users"].append(customer.id)
            return customer

    yield Shop()
    with db.connect(autocommit=True) as conn:
        for pid in created["products"]:
            conn.execute("DELETE FROM order_items WHERE product_id = %s", (pid,))
            conn.execute("DELETE FROM products WHERE id = %s", (pid,))
        conn.execute("DELETE FROM orders WHERE user_id = ANY(%s) AND NOT EXISTS "
                     "(SELECT 1 FROM order_items i WHERE i.order_id = orders.id)", (created["users"],))
        conn.execute("DELETE FROM users WHERE id = ANY(%s) AND NOT EXISTS "
                     "(SELECT 1 FROM orders o WHERE o.user_id = users.id)", (created["users"],))
