"""
Email Service
-------------
Central routing gateway for all outbound emails.

Decision tree for every new Query
──────────────────────────────────
             ┌─ tagged_expert_email set? ──YES──► direct_tag_email()
             │
  new query ─┤
             │
             └─ is_urgent == True? ─────YES──► urgent_broadcast_email()
                       │
                       NO
                       │
                       └──────────────────────► queue_for_digest()

The APScheduler job `send_daily_digest` runs once per day and flushes
all pending DigestQueue entries grouped by group_id.
"""

import smtplib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from contextlib import contextmanager

from flask import current_app

from app.extensions import db
from app.models.digest_queue import DigestQueue

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def _smtp_connection():
    """Yield an authenticated SMTP-SSL connection, auto-closed on exit."""
    cfg = current_app.config
    server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"])
    try:
        server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        yield server
    finally:
        server.quit()


def _build_mime(
    to_addresses: list[str],
    subject: str,
    html_body: str,
    cc: list[str] | None = None,
) -> MIMEMultipart:
    cfg = current_app.config
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_DEFAULT_SENDER"]
    msg["To"] = ", ".join(to_addresses)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _send(msg: MIMEMultipart, recipients: list[str]):
    try:
        with _smtp_connection() as server:
            server.sendmail(
                current_app.config["MAIL_DEFAULT_SENDER"],
                recipients,
                msg.as_string()
            )
        logger.info("Email sent to %s | Subject: %s", recipients, msg["Subject"])
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending to %s: %s", recipients, exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# HTML Templates (inline – swap for Jinja templates in production)
# ─────────────────────────────────────────────────────────────────────────────

def _render_query_card(query, group) -> str:
    drive_html = (
        f'<p>📎 <a href="{query.drive_link}">Attached Drive File</a></p>'
        if query.drive_link else ""
    )
    voice_html = (
        f'<p>🎙️ Voice note attached (open the app to listen)</p>'
        if query.voice_note_path else ""
    )
    return f"""
    <div style="border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:12px 0;background:#f8fafc;">
        <h3 style="margin:0 0 8px;color:#1e293b;">{query.title}</h3>
        <p style="color:#475569;">{query.body}</p>
        {drive_html}
        {voice_html}
        <p style="font-size:12px;color:#94a3b8;">
            Posted by <strong>{query.author.name}</strong> in <strong>{group.name}</strong>
            &nbsp;|&nbsp; {query.created_at.strftime("%d %b %Y, %H:%M")} UTC
        </p>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class EmailService:

    @staticmethod
    def route_query_notification(query, group, author_user):
        """
        Main gateway: inspect the query flags and dispatch to the correct
        notification path. Returns the notification_mode string.
        """
        # Path 1: @Expert direct tag takes highest priority
        if query.tagged_expert_email:
            EmailService.direct_tag_email(query, group)
            return "direct_tag"

        # Path 2: SOS / Urgent broadcast
        if query.is_urgent:
            # Rate-limit enforcement is done in the route before saving,
            # but we do a final guard here.
            if not author_user.consume_sos():
                logger.warning(
                    "SOS quota exceeded for user %s – falling back to digest.",
                    author_user.email
                )
                EmailService.queue_for_digest(query, group)
                return "digest"
            db.session.commit()  # persist sos_count update
            EmailService.urgent_broadcast_email(query, group, author_user)
            return "urgent_broadcast"

        # Path 3: Default – queue for daily digest
        EmailService.queue_for_digest(query, group)
        return "digest"

    # ── Path 1: Direct @Expert email ─────────────────────────────────────

    @staticmethod
    def direct_tag_email(query, group):
        expert_email = query.tagged_expert_email
        subject = f"[StudyGroup] You've been tagged as Expert | {query.title}"
        html = f"""
        <h2 style="color:#4f46e5;">You've been tagged as an Expert! 🎓</h2>
        <p>A member of <strong>{group.name}</strong> needs your specific expertise:</p>
        {_render_query_card(query, group)}
        <p>
          <a href="{current_app.config['APP_BASE_URL']}/queries/{query.id}"
             style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
            View & Answer
          </a>
        </p>
        <hr>
        <p style="font-size:12px;color:#94a3b8;">StudyGroup – focused academic collaboration</p>
        """
        msg = _build_mime([expert_email], subject, html)
        _send(msg, [expert_email])
        logger.info("Direct tag email sent to %s for query #%s", expert_email, query.id)

    # ── Path 2: Urgent broadcast ──────────────────────────────────────────

    @staticmethod
    def urgent_broadcast_email(query, group, author_user):
        recipients = group.get_member_emails(exclude_user_id=author_user.id)
        if not recipients:
            logger.info("No recipients for urgent broadcast on query #%s", query.id)
            return

        subject = f"🚨 [URGENT] {query.title} | {group.name}"
        html = f"""
        <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:12px 16px;border-radius:6px;margin-bottom:16px;">
          <strong style="color:#b91c1c;">⚡ SOS / Urgent Query</strong>
          <p style="margin:4px 0;color:#7f1d1d;">
            {author_user.name} needs immediate help. Please respond as soon as possible.
          </p>
        </div>
        {_render_query_card(query, group)}
        <p>
          <a href="{current_app.config['APP_BASE_URL']}/queries/{query.id}"
             style="background:#ef4444;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
            Help Now 🚨
          </a>
        </p>
        <hr>
        <p style="font-size:12px;color:#94a3b8;">StudyGroup – focused academic collaboration</p>
        """
        msg = _build_mime(recipients, subject, html)
        _send(msg, recipients)
        logger.info(
            "Urgent broadcast sent to %d members for query #%s",
            len(recipients), query.id
        )

    # ── Path 3: Queue for daily digest ───────────────────────────────────

    @staticmethod
    def queue_for_digest(query, group):
        """Add query to DigestQueue if not already queued."""
        existing = DigestQueue.query.filter_by(query_id=query.id).first()
        if existing:
            return  # already queued
        entry = DigestQueue(query_id=query.id, group_id=group.id)
        db.session.add(entry)
        db.session.commit()
        logger.info("Query #%s added to digest queue for group #%s", query.id, group.id)

    # ── Scheduled: Send Daily Digest ─────────────────────────────────────

    @staticmethod
    def send_daily_digest():
        """
        APScheduler job: runs daily (e.g., 07:00 UTC).
        Groups pending DigestQueue entries by group and sends one email per group.
        """
        from app.models.group import Group
        from collections import defaultdict

        pending = DigestQueue.query.filter_by(sent=False).all()
        if not pending:
            logger.info("Daily digest: no pending queries.")
            return

        # Group by group_id
        by_group: dict[int, list[DigestQueue]] = defaultdict(list)
        for entry in pending:
            by_group[entry.group_id].append(entry)

        for group_id, entries in by_group.items():
            group = Group.query.get(group_id)
            if not group:
                continue

            recipients = group.get_member_emails()
            if not recipients:
                continue

            queries_html = "".join(
                _render_query_card(e.query, group) for e in entries
            )
            subject = f"📚 Daily Study Digest | {group.name} | {datetime.now(timezone.utc).strftime('%d %b %Y')}"
            html = f"""
            <h2 style="color:#4f46e5;">Your Daily Study Digest 📚</h2>
            <p>Here are the new queries posted in <strong>{group.name}</strong> today:</p>
            {queries_html}
            <p>
              <a href="{current_app.config['APP_BASE_URL']}/groups/{group_id}"
                 style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
                Open StudyGroup
              </a>
            </p>
            <hr>
            <p style="font-size:12px;color:#94a3b8;">
              You received this because you are a member of {group.name}. 
              To unsubscribe from digests, update your notification settings in-app.
            </p>
            """
            try:
                msg = _build_mime(recipients, subject, html)
                _send(msg, recipients)
                # Mark entries as sent
                for entry in entries:
                    entry.sent = True
                    entry.sent_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(
                    "Digest sent to group #%s (%d queries, %d recipients)",
                    group_id, len(entries), len(recipients)
                )
            except Exception as exc:
                logger.error("Digest failed for group #%s: %s", group_id, exc)
