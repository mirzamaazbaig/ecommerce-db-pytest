"""Valid parent rows, created inside the test's transaction (rolled back afterwards)."""
import uuid


def user(conn, role="user") -> int:
    return conn.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', %s) RETURNING id",
        (f"db_{uuid.uuid4().hex[:10]}@example.com", role),
    ).fetchone()[0]


def product(conn, price=10, stock=5) -> int:
    return conn.execute(
        "INSERT INTO products (name, price, stock, category_id) VALUES (%s, %s, %s, 1) RETURNING id",
        (f"db product {uuid.uuid4().hex[:8]}", price, stock),
    ).fetchone()[0]


def order(conn, user_id, total=10) -> int:
    return conn.execute(
        "INSERT INTO orders (user_id, total_amount) VALUES (%s, %s) RETURNING id", (user_id, total)
    ).fetchone()[0]


def order_line(conn, order_id, product_id, quantity=1, price=10) -> int:
    return conn.execute(
        "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s, %s, %s, %s) RETURNING id",
        (order_id, product_id, quantity, price),
    ).fetchone()[0]
