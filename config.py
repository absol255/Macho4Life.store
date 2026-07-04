import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv("")


def _normalize_database_url(url):
    if not url:
        return None
    # Heroku/Neon/Vercel often use postgres://; SQLAlchemy needs postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    # Serverless hosts usually require SSL to managed Postgres
    if "sslmode=" not in url and "localhost" not in url and "127.0.0.1" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Vercel serves HTTPS; secure cookies are required for sessions to stick
    SESSION_COOKIE_SECURE = bool(os.getenv("VERCEL"))
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
