"""
DigestQueue Model
-----------------
Holds references to queries that should be included in the next
Daily Digest email. The scheduler reads and clears this table daily.
"""

from datetime import datetime, timezone
from app.extensions import db


class DigestQueue(db.Model):
    __tablename__ = "digest_queue"

    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(db.Integer, db.ForeignKey("queries.id"), nullable=False, unique=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    queued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Set to True once the scheduler has sent the digest containing this query
    sent = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    query = db.relationship("Query")
    group = db.relationship("Group")

    def __repr__(self):
        return f"<DigestQueue query={self.query_id} group={self.group_id} sent={self.sent}>"
