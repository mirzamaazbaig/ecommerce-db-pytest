"""Schema contract: the tables, columns, keys and delete rules the application relies on."""
import pytest

pytestmark = pytest.mark.schema

# table -> {column: data type}
COLUMNS = {
    "users": {"id": "integer", "email": "character varying", "password_hash": "character varying",
              "role": "character varying", "created_at": "timestamp without time zone"},
    "categories": {"id": "integer", "name": "character varying"},
    "products": {"id": "integer", "name": "character varying", "description": "text", "price": "numeric",
                 "stock": "integer", "image_url": "text", "category_id": "integer",
                 "created_at": "timestamp without time zone"},
    "orders": {"id": "integer", "user_id": "integer", "total_amount": "numeric", "status": "character varying",
               "transaction_hash": "text", "created_at": "timestamp without time zone"},
    "order_items": {"id": "integer", "order_id": "integer", "product_id": "integer", "quantity": "integer",
                    "price_at_purchase": "numeric"},
    "reviews": {"id": "integer", "user_id": "integer", "product_id": "integer", "rating": "integer",
                "comment": "text", "created_at": "timestamp without time zone"},
    "wishlist": {"id": "integer", "user_id": "integer", "product_id": "integer",
                 "created_at": "timestamp without time zone"},
}

# (table, column, referenced table, delete rule)
FOREIGN_KEYS = [
    ("products", "category_id", "categories", "NO ACTION"),
    ("orders", "user_id", "users", "NO ACTION"),
    ("order_items", "order_id", "orders", "NO ACTION"),
    ("order_items", "product_id", "products", "NO ACTION"),
    ("reviews", "user_id", "users", "CASCADE"),
    ("reviews", "product_id", "products", "CASCADE"),
    ("wishlist", "user_id", "users", "CASCADE"),
    ("wishlist", "product_id", "products", "CASCADE"),
]

DELETE_RULES = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def test_the_expected_tables_exist(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    assert set(COLUMNS) <= tables


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_columns_and_types(conn, table):
    actual = dict(conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,)).fetchall())
    assert actual == COLUMNS[table]


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_every_table_has_an_integer_primary_key_called_id(conn, table):
    rows = conn.execute("""
        SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary""", (table,)).fetchall()
    assert [r[0] for r in rows] == ["id"]


def test_foreign_keys_and_delete_rules(conn):
    rows = conn.execute("""
        SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, c.confdeltype
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace""").fetchall()
    actual = sorted((t, col, ref, DELETE_RULES[rule]) for t, col, ref, rule in rows)
    assert actual == sorted(FOREIGN_KEYS)


@pytest.mark.parametrize("table,columns", [
    ("users", ["email"]), ("categories", ["name"]), ("wishlist", ["user_id", "product_id"]),
])
def test_unique_constraints(conn, table, columns):
    rows = conn.execute("""
        SELECT array_agg(a.attname ORDER BY a.attnum) FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.contype = 'u' AND c.conrelid = %s::regclass GROUP BY c.oid""", (table,)).fetchall()
    assert columns in [r[0] for r in rows]


def test_the_seed_categories_exist(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM categories")}
    assert {"Electronics", "Clothing", "Books"} <= names
