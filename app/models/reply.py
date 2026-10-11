"""
Reply Model
-----------
Threaded responses to a Query. Mirrors Query's attachment options
(text, Drive link, voice note) so any member can answer fully.
"""

from datetime import datetime, timezone
from app.extensions import db


class Reply(db.Model):
    __tablename__ = "replies"

    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(db.Integer, db.ForeignKey("queries.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Support parent_id for nested replies (2-level threading)
    parent_reply_id = db.Column(db.Integer, db.ForeignKey("replies.id"), nullable=True)

    body = db.Column(db.Text, nullable=False)
    drive_link = db.Column(db.String(1024), nullable=True)
    voice_note_path = db.Column(db.String(512), nullable=True)

    # The author of this reply can mark it as the accepted solution
    is_accepted_answer = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    query = db.relationship("Query", back_populates="replies")
    author = db.relationship("User", back_populates="replies")
    children = db.relationship(
        "Reply",
        backref=db.backref("parent", remote_side=[id]),
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<Reply #{self.id} on Query #{self.query_id}>"
