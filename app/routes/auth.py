"""
Google OAuth Authentication Routes
------------------------------------
Implements Gmail-only login using the Authlib OAuth2 client.

Flow:
  1. GET /auth/login       → redirect to Google consent screen
  2. GET /auth/callback    → exchange code for tokens, upsert User, set session
  3. GET /auth/logout      → clear session
"""

import json
from datetime import datetime, timezone

from flask import Blueprint, redirect, url_for, session, flash, current_app
from flask_login import login_user, logout_user, current_user

from app.extensions import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ── Authlib OAuth client (registered in create_app) ───────────────────────
from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_oauth(app):
    """Call this inside create_app() after oauth.init_app(app)."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile https://www.googleapis.com/auth/drive.file",
            # drive.file scope: only files created/opened by this app
        },
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    )


# ── Routes ────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    """Redirect unauthenticated user to Google's OAuth consent page."""
    if current_user.is_authenticated:
        return redirect(url_for("groups.dashboard"))

    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/callback")
def callback():
    """
    Google redirects here after user grants consent.
    Exchange the auth code for an access token, fetch the user's profile,
    then upsert a User record and log them in.
    """
    try:
        token = oauth.google.authorize_access_token()
    except Exception as exc:
        current_app.logger.error("OAuth token exchange failed: %s", exc)
        flash("Authentication failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    user_info = token.get("userinfo")
    if not user_info:
        flash("Could not retrieve your Google profile.", "danger")
        return redirect(url_for("auth.login"))

    # ── Only allow Gmail / Google Workspace accounts ──────────────────────
    email: str = user_info.get("email", "")
    if not email:
        flash("No email address returned by Google.", "danger")
        return redirect(url_for("auth.login"))

    # Upsert user ─────────────────────────────────────────────────────────
    user = User.query.filter_by(google_id=user_info["sub"]).first()
    if user is None:
        user = User(google_id=user_info["sub"], email=email)
        db.session.add(user)

    user.name = user_info.get("name", email)
    user.avatar_url = user_info.get("picture")
    user.access_token = token.get("access_token")
    user.refresh_token = token.get("refresh_token")

    expires_at = token.get("expires_at")
    if expires_at:
        user.token_expiry = datetime.fromtimestamp(expires_at, tz=timezone.utc)

    user.last_seen = datetime.now(timezone.utc)
    db.session.commit()

    login_user(user, remember=True)
    flash(f"Welcome, {user.name}! 👋", "success")

    next_page = session.pop("next_url", None)
    return redirect(next_page or url_for("groups.dashboard"))


@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))
