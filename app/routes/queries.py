"""
Queries Routes
--------------
Create / view / toggle queries. Handles:
  - Text body
  - Google Drive link attachment
  - Voice note upload (WebM blob from browser)
  - is_urgent flag + SOS rate-limit enforcement
  - tagged_expert_email selection
  - Email routing via EmailService
"""

import os
import uuid
import logging

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, abort, jsonify, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.group import Group, GroupMembership
from app.models.query import Query
from app.services.email_service import EmailService
from app.services.drive_service import DriveService

logger = logging.getLogger(__name__)
queries_bp = Blueprint("queries", __name__, url_prefix="/queries")

ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "mp4", "wav"}


def _save_voice_note(file_storage) -> str | None:
    """Save a voice note blob to the static/audio directory. Returns relative path."""
    filename = f"{uuid.uuid4().hex}.webm"
    audio_dir = os.path.join(current_app.root_path, "static", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    dest = os.path.join(audio_dir, filename)
    file_storage.save(dest)
    return f"audio/{filename}"


# ── Create Query ──────────────────────────────────────────────────────────

@queries_bp.route("/new/<int:group_id>", methods=["GET", "POST"])
@login_required
def create(group_id):
    group = Group.query.get_or_404(group_id)
    if not group.is_member(current_user):
        abort(403)

    members = [m.user for m in group.memberships.all() if m.user_id != current_user.id]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        drive_link = request.form.get("drive_link", "").strip() or None
        is_urgent = bool(request.form.get("is_urgent"))
        tagged_expert_email = request.form.get("tagged_expert_email", "").strip() or None

        if not title or not body:
            flash("Title and description are required.", "warning")
            return render_template("queries/create.html", group=group, members=members)

        # ── SOS rate-limit guard ──────────────────────────────────────────
        if is_urgent and current_user.get_sos_remaining() <= 0:
            flash(
                "⚠️ You've used all 3 SOS sends this week. "
                "Your query will be sent in the daily digest instead.",
                "warning"
            )
            is_urgent = False

        # ── Voice note handling ───────────────────────────────────────────
        voice_note_path = None
        voice_file = request.files.get("voice_note")
        if voice_file and voice_file.filename:
            try:
                voice_note_path = _save_voice_note(voice_file)
            except Exception as exc:
                logger.error("Voice note save failed: %s", exc)
                flash("Voice note could not be saved. Continuing without it.", "warning")

        # ── Drive file upload (optional) ──────────────────────────────────
        uploaded_file = request.files.get("drive_upload")
        if uploaded_file and uploaded_file.filename and not drive_link:
            try:
                drive = DriveService(current_user)
                drive_link = drive.upload_file(uploaded_file, folder_name=f"StudyGroup – {group.name}")
            except Exception as exc:
                logger.error("Drive upload failed: %s", exc)
                flash("File upload to Drive failed. You can paste a Drive link manually.", "warning")

        # ── Create and persist query ──────────────────────────────────────
        query = Query(
            group_id=group.id,
            author_id=current_user.id,
            title=title,
            body=body,
            drive_link=drive_link,
            voice_note_path=voice_note_path,
            is_urgent=is_urgent,
            tagged_expert_email=tagged_expert_email,
        )
        db.session.add(query)
        db.session.flush()  # get query.id

        # ── Route notification ────────────────────────────────────────────
        notification_mode = EmailService.route_query_notification(query, group, current_user)
        query.notification_mode = notification_mode
        db.session.commit()

        mode_labels = {
            "digest": "📬 Added to today's digest.",
            "urgent_broadcast": "🚨 Urgent email sent to all members!",
            "direct_tag": "✉️ Expert notified directly.",
        }
        flash(f"Query posted! {mode_labels.get(notification_mode, '')}", "success")
        return redirect(url_for("queries.detail", query_id=query.id))

    return render_template("queries/create.html", group=group, members=members)


# ── Query Detail ──────────────────────────────────────────────────────────

@queries_bp.route("/<int:query_id>")
@login_required
def detail(query_id):
    query = Query.query.get_or_404(query_id)
    if not query.group.is_member(current_user):
        abort(403)

    top_level_replies = query.replies.filter_by(parent_reply_id=None).all()
    return render_template(
        "queries/detail.html",
        query=query,
        replies=top_level_replies,
        group=query.group
    )


# ── Toggle Status ─────────────────────────────────────────────────────────

@queries_bp.route("/<int:query_id>/toggle-status", methods=["POST"])
@login_required
def toggle_status(query_id):
    query = Query.query.get_or_404(query_id)
    if query.author_id != current_user.id and query.group.owner_id != current_user.id:
        abort(403)

    query.toggle_status()
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": query.status})

    flash(f"Query marked as '{query.status}'.", "info")
    return redirect(url_for("queries.detail", query_id=query_id))


# ── SOS remaining (AJAX) ──────────────────────────────────────────────────

@queries_bp.route("/sos-remaining")
@login_required
def sos_remaining():
    return jsonify({"remaining": current_user.get_sos_remaining()})
