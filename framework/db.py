"""Database access for the tests."""
import psycopg

from framework.config import DATABASE_URL


class _Accepted(Exception):
    """Raised on purpose to roll back a statement that the database accepted."""


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, autocommit=autocommit)


def attempt(conn: psycopg.Connection, sql: str, params=()):
    """Run a statement in a savepoint and always undo it.

    Returns None if the database accepted the statement, or the psycopg error if it rejected it.
    The test can then assert on the exact kind of rejection (NotNullViolation, CheckViolation, ...).
    """
    try:
        with conn.transaction():
            conn.execute(sql, params)
            raise _Accepted
    except _Accepted:
        return None
    except psycopg.Error as error:
        return error


def scalar(conn: psycopg.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None
