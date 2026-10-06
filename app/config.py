import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantforge.db")
APP_SECRET = os.getenv("APP_SECRET", "dev-secret-change-me")
