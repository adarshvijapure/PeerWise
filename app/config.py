"""
Configuration
-------------
Load settings from environment variables (via .env).
Never commit real secrets to source control.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Flask core ────────────────────────────────────────────────────────
    SECRET_KEY = os.environ["SECRET_KEY"]
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # ── SQLAlchemy ────────────────────────────────────────────────────────
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///studygroup.db")
    # Render returns "postgres://" but SQLAlchemy 1.4+ requires "postgresql://"
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Google OAuth ──────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

    # ── Email (Gmail SMTP SSL) ────────────────────────────────────────────
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 465))
    MAIL_USERNAME = os.environ["MAIL_USERNAME"]         # sender Gmail address
    MAIL_PASSWORD = os.environ["MAIL_PASSWORD"]         # Gmail App Password
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", os.environ["MAIL_USERNAME"])

    # ── App URL (used in email links) ─────────────────────────────────────
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    # ── APScheduler ───────────────────────────────────────────────────────
    SCHEDULER_API_ENABLED = False       # disable REST API for scheduler in prod

    # ── Uploads ───────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024   # 50 MB max upload per request


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True   # log SQL queries


class ProductionConfig(Config):
    DEBUG = False
