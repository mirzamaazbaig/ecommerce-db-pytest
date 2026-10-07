import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ecom_db")
API_URL = os.environ.get("API_URL", "http://localhost:5000/api").rstrip("/")
PASSWORD = "TestPass123!"

# Checkout of the application (the Ecom repository). Needed only by the migration tests.
APP_REPO = os.environ.get("APP_REPO")
