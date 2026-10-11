"""
User Model
----------
Stores Google OAuth profile data per authenticated user.
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)
    avatar_url = db.Column(db.String(512), nullable=True)

    # OAuth tokens (stored encrypted in production)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    # SOS / Urgent query rate-limiting: tracks how many urgent queries
    # this user has sent in the current ISO week.
    sos_count_this_week = db.Column(db.Integer, default=0, nullable=False)
    sos_week_reset_date = db.Column(db.Date, nullable=True)   # Monday of the tracked week

    # Extra SOS quota granted by a group owner/admin (added on top of default 3/week).
    # Resets together with sos_count_this_week each Monday.
    sos_quota_extra = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    memberships = db.relationship("GroupMembership", back_populates="user", lazy="dynamic")
    queries = db.relationship("Query", back_populates="author", lazy="dynamic")
    replies = db.relationship("Reply", back_populates="author", lazy="dynamic")

    @property
    def sos_weekly_limit(self):
        """Total SOS allowed this week: base 3 + any extra granted by a group owner."""
        return 3 + (self.sos_quota_extra or 0)

    def get_sos_remaining(self):
        """Return how many SOS sends the user still has this week."""
        import datetime
        today = datetime.date.today()
        week_monday = today - datetime.timedelta(days=today.weekday())
        if self.sos_week_reset_date != week_monday:
            # New week — reset both counters
            self.sos_count_this_week = 0
            self.sos_quota_extra = 0
            self.sos_week_reset_date = week_monday
        return max(0, self.sos_weekly_limit - self.sos_count_this_week)

    def consume_sos(self):
        """Decrement remaining SOS uses for this week. Returns False if limit reached."""
        remaining = self.get_sos_remaining()
        if remaining <= 0:
            return False
        self.sos_count_this_week += 1
        return True

    def grant_sos(self, amount: int = 3):
        """Add `amount` extra SOS uses to this user's quota for the current week."""
        self.sos_quota_extra = (self.sos_quota_extra or 0) + amount

    def __repr__(self):
        return f"<User {self.email}>"
