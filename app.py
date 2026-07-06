from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Admin
from decimal import Decimal
import os
import time
import click
import json

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

app.config.from_object(Config)

if os.getenv("VERCEL"):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def init_db():
    with app.app_context():
        db.create_all()


def ensure_tables():
    """Create tables if missing. Returns an error string or None."""
    try:
        db.create_all()
        return None
    except Exception as exc:
        app.logger.exception("ensure_tables failed")
        return str(exc)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


app.json_encoder = DecimalEncoder


def maybe_bootstrap_admin():
    """Optional: set BOOTSTRAP_ADMIN_USER + BOOTSTRAP_ADMIN_PASSWORD in Vercel once."""
    user = os.getenv("BOOTSTRAP_ADMIN_USER")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not user or not password:
        return
    try:
        if Admin.query.count() > 0:
            return
        admin = Admin(username=user.strip()[:64])
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Bootstrapped admin user: %s", user)
    except Exception:
        app.logger.exception("bootstrap admin failed")
        db.session.rollback()

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Admin, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Login required"}), 401
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/otherminiwebsites")
def test():
    return render_template("otherminiwebsites.html")

def _config_error():
    if not app.config.get("SECRET_KEY"):
        return "SECRET_KEY is not set on the server"
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        return "DATABASE_URL is not set on the server"
    return None


@app.route("/api/health")
def api_health():
    err = _config_error()
    if err:
        return jsonify({"ok": False, "error": err}), 503
    try:
        db.session.execute(db.text("SELECT 1"))
        table_err = ensure_tables()
        maybe_bootstrap_admin()
        admin_count = Admin.query.count()
        payload = {
            "ok": table_err is None,
            "db": True,
            "tables_ok": table_err is None,
            "admin_count": admin_count,
        }
        if table_err:
            payload["error"] = table_err
        elif admin_count == 0:
            payload["hint"] = (
                "No admin users. Run: flask --app app create-admin USER PASS "
                "with production DATABASE_URL, or set BOOTSTRAP_ADMIN_USER and "
                "BOOTSTRAP_ADMIN_PASSWORD in Vercel temporarily."
            )
        status = 503 if table_err else 200
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin(username, password):
    """Create a admin (run once): flask create-admin user pass"""
    init_db()
    if Admin.query.filter_by(username=username).first():
        click.echo("Admin already exists.")
        return
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo("Admin created: " + username)


try:
    init_db()
except Exception:
    pass
