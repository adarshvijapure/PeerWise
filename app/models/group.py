"""
Group & GroupMembership Models
-------------------------------
Study groups and their member associations.
"""

from datetime import datetime, timezone
import secrets
from app.extensions import db


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)
    subject = db.Column(db.String(128), nullable=True)   # e.g., "Algorithms", "Organic Chemistry"

    # Invite system: a unique token lets anyone with the link join.
    invite_token = db.Column(
        db.String(64), unique=True, nullable=False,
        default=lambda: secrets.token_urlsafe(32)
    )

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    memberships = db.relationship("GroupMembership", back_populates="group", lazy="dynamic", cascade="all, delete-orphan")
    queries = db.relationship("Query", back_populates="group", lazy="dynamic", cascade="all, delete-orphan")

    def is_member(self, user):
        return self.memberships.filter_by(user_id=user.id).first() is not None

    def get_member_emails(self, exclude_user_id=None):
        """Return a list of email addresses for all members, optionally excluding one."""
        q = self.memberships
        if exclude_user_id:
            q = q.filter(GroupMembership.user_id != exclude_user_id)
        return [m.user.email for m in q.all()]

    def __repr__(self):
        return f"<Group '{self.name}'>"


class GroupMembership(db.Model):
    __tablename__ = "group_memberships"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(32), default="member")  # "owner" | "member"
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Notification preference: opt-out of daily digest
    digest_enabled = db.Column(db.Boolean, default=True, nullable=False)

    group = db.relationship("Group", back_populates="memberships")
    user = db.relationship("User", back_populates="memberships")

    __table_args__ = (
        db.UniqueConstraint("group_id", "user_id", name="uq_group_user"),
    )

    def __repr__(self):
        return f"<Membership user={self.user_id} group={self.group_id}>"
