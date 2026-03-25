import os


class Config:
    """Hlavní konfigurace Flask aplikace a připojení k databázi."""

    DEBUG = True

    # Session klíč pro Flask login session.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Výchozí admin účet pro db_setup.py (lze přepsat přes ENV).
    ADMIN_DEFAULT_USERNAME = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

    # Připojení k MySQL.
    DB_HOST = os.getenv("DB_HOST", "dbs.spskladno.cz")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "student28")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "spsnet")
    DB_NAME = os.getenv("DB_NAME", "vyuka28")
