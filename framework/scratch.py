"""A throw-away database built with the application's own scripts, for testing migrations."""
import os
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
from urllib.parse import urlsplit, urlunsplit

from framework.config import APP_REPO, DATABASE_URL


def _url_for(dbname: str) -> str:
    parts = urlsplit(DATABASE_URL)
    return urlunsplit(parts._replace(path=f"/{dbname}"))


def _admin():
    return psycopg.connect(_url_for("postgres"), autocommit=True)


def node(script: str, url: str) -> subprocess.CompletedProcess:
    """Run one of the application's scripts (db/setup.js, scripts/migrate.js, ...) against `url`."""
    env = {"DATABASE_URL": url, "PATH": os.environ["PATH"], "NODE_ENV": "test"}
    return subprocess.run(["node", script], cwd=Path(APP_REPO) / "server", env=env,
                          capture_output=True, text=True, timeout=60)


def migration_sql(name: str) -> str:
    return (Path(APP_REPO) / "server" / "db" / "migrations" / name).read_text()


@contextmanager
def database():
    """Yield (url, connect) for a new empty database that is dropped afterwards."""
    name = f"ecom_scratch_{uuid.uuid4().hex[:8]}"
    with _admin() as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = _url_for(name)
    try:
        yield url
    finally:
        with _admin() as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
