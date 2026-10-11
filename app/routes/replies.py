"""
Replies Routes
--------------
Post threaded replies to a Query.
Supports text, Drive link, and voice note attachments.
Marks a reply as the accepted answer.
"""

import os
import uuid
import logging

from flask import (
    Blueprint, redirect, url_for, request,
    flash, abort, jsonify, current_app
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.query import Query
from app.models.reply import Reply
from app.services.drive_service import DriveService

logger = logging.getLogger(__name__)
replies_bp = Blueprint("replies", __name__, url_prefix="/replies")


def _save_voice_note(file_storage) -> str | None:
    filename = f"{uuid.uuid4().hex}.webm"
    audio_dir = os.path.join(current_app.root_path, "static", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    file_storage.save(os.path.join(audio_dir, filename))
    return f"audio/{filename}"


@replies_bp.route("/new/<int:query_id>", methods=["POST"])
@login_required
def create(query_id):
    query = Query.query.get_or_404(query_id)
    if not query.group.is_member(current_user):
        abort(403)

    body = request.form.get("body", "").strip()
    drive_link = request.form.get("drive_link", "").strip() or None
    parent_reply_id = request.form.get("parent_reply_id", type=int)

    if not body:
        flash("Reply body cannot be empty.", "warning")
        return redirect(url_for("queries.detail", query_id=query_id))

    voice_note_path = None
    voice_file = request.files.get("voice_note")
    if voice_file and voice_file.filename:
        try:
            voice_note_path = _save_voice_note(voice_file)
        except Exception as exc:
            logger.error("Voice note error: %s", exc)
            flash("Voice note could not be saved.", "warning")

    uploaded_file = request.files.get("drive_upload")
    if uploaded_file and uploaded_file.filename and not drive_link:
        try:
            drive = DriveService(current_user)
            drive_link = drive.upload_file(uploaded_file)
        except Exception as exc:
            logger.error("Drive upload failed: %s", exc)
            flash("File upload failed. Paste a Drive link instead.", "warning")

    reply = Reply(
        query_id=query.id,
        author_id=current_user.id,
        body=body,
        drive_link=drive_link,
        voice_note_path=voice_note_path,
        parent_reply_id=parent_reply_id,
    )
    db.session.add(reply)
    db.session.commit()
    flash("Reply posted! ✅", "success")
    return redirect(url_for("queries.detail", query_id=query_id))


@replies_bp.route("/<int:reply_id>/accept", methods=["POST"])
@login_required
def accept_answer(reply_id):
    reply = Reply.query.get_or_404(reply_id)
    query = reply.query
    if query.author_id != current_user.id:
        abort(403)

    # Clear any previous accepted answers for this query
    Reply.query.filter_by(query_id=query.id, is_accepted_answer=True).update(
        {"is_accepted_answer": False}
    )
    reply.is_accepted_answer = True
    query.status = Query.STATUS_RESOLVED
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"accepted": True})

    flash("Answer accepted and query marked as resolved! ✅", "success")
    return redirect(url_for("queries.detail", query_id=query.id))
