"""
Query Model
-----------
The core "doubt" entity. Supports text, Google Drive attachment links,
voice note paths, urgency flags, and @Expert tagging.
"""

from datetime import datetime, timezone
from app.extensions import db


class Query(db.Model):
    __tablename__ = "queries"

    # ── Primary key & foreign keys ──────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # ── Content ─────────────────────────────────────────────────────────────
    title = db.Column(db.String(512), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # Google Drive sharing link (PDF, PPT, etc.)
    drive_link = db.Column(db.String(1024), nullable=True)

    # Relative server path to stored voice note (e.g., "audio/<uuid>.webm")
    voice_note_path = db.Column(db.String(512), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────────
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    status = db.Column(
        db.Enum("open", "resolved", name="query_status"),
        nullable=False,
        default="open"
    )

    # ── Notification routing flags ────────────────────────────────────────
    # SOS / Urgent mode: bypasses digest, instant email to all members
    is_urgent = db.Column(db.Boolean, default=False, nullable=False)

    # @Expert tag: email address of the specific member to notify directly
    tagged_expert_email = db.Column(db.String(256), nullable=True)

    # Tracks which email path was taken for audit / UI display
    # Values: "digest" | "urgent_broadcast" | "direct_tag"
    notification_mode = db.Column(db.String(32), nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ─────────────────────────────────────────────────────
    group = db.relationship("Group", back_populates="queries")
    author = db.relationship("User", back_populates="queries")
    replies = db.relationship(
        "Reply", back_populates="query",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="Reply.created_at"
    )

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    def toggle_status(self):
        if self.status == self.STATUS_OPEN:
            self.status = self.STATUS_RESOLVED
        else:
            self.status = self.STATUS_OPEN

    def __repr__(self):
        return f"<Query #{self.id} '{self.title[:40]}' [{self.status}]>"
