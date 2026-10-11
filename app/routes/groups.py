"""
Groups Routes
-------------
CRUD for Study Groups + invite link join flow.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, abort
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.group import Group, GroupMembership
from app.models.user import User

groups_bp = Blueprint("groups", __name__, url_prefix="/groups")


# ── Dashboard ─────────────────────────────────────────────────────────────

@groups_bp.route("/")
@login_required
def dashboard():
    memberships = current_user.memberships.all()
    groups = [m.group for m in memberships]
    return render_template("dashboard.html", groups=groups)


# ── Create group ──────────────────────────────────────────────────────────

@groups_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        subject = request.form.get("subject", "").strip()

        if not name:
            flash("Group name is required.", "warning")
            return render_template("groups/create.html")

        group = Group(name=name, description=description, subject=subject, owner_id=current_user.id)
        db.session.add(group)
        db.session.flush()  # get group.id before committing

        # Owner is also a member with role "owner"
        membership = GroupMembership(group_id=group.id, user_id=current_user.id, role="owner")
        db.session.add(membership)
        db.session.commit()

        flash(f"Group '{name}' created! Share the invite link below.", "success")
        return redirect(url_for("groups.detail", group_id=group.id))

    return render_template("groups/create.html")


# ── Group detail ──────────────────────────────────────────────────────────

@groups_bp.route("/<int:group_id>")
@login_required
def detail(group_id):
    group = Group.query.get_or_404(group_id)
    if not group.is_member(current_user):
        abort(403)

    queries = group.queries.order_by(db.text("created_at DESC")).all()
    members = [m.user for m in group.memberships.all()]
    invite_url = url_for("groups.join_via_token", token=group.invite_token, _external=True)
    return render_template(
        "groups/detail.html",
        group=group, queries=queries, members=members,
        invite_url=invite_url
    )


# ── Join via invite token ─────────────────────────────────────────────────

@groups_bp.route("/join/<token>")
@login_required
def join_via_token(token):
    group = Group.query.filter_by(invite_token=token).first_or_404()

    if group.is_member(current_user):
        flash("You're already a member of this group.", "info")
        return redirect(url_for("groups.detail", group_id=group.id))

    membership = GroupMembership(group_id=group.id, user_id=current_user.id, role="member")
    db.session.add(membership)
    db.session.commit()
    flash(f"You've joined '{group.name}'! 🎉", "success")
    return redirect(url_for("groups.detail", group_id=group.id))


# ── Invite by email (sends invite link via email) ─────────────────────────

@groups_bp.route("/<int:group_id>/invite", methods=["POST"])
@login_required
def invite_by_email(group_id):
    from app.services.email_service import _build_mime, _send
    group = Group.query.get_or_404(group_id)
    if not group.is_member(current_user):
        abort(403)

    emails = [e.strip() for e in request.form.get("emails", "").split(",") if e.strip()]
    if not emails:
        flash("Please provide at least one email address.", "warning")
        return redirect(url_for("groups.detail", group_id=group_id))

    invite_url = url_for("groups.join_via_token", token=group.invite_token, _external=True)
    html = f"""
    <h2>You've been invited to join a Study Group 📚</h2>
    <p><strong>{current_user.name}</strong> has invited you to join
       <strong>{group.name}</strong> on StudyGroup.</p>
    <p>
      <a href="{invite_url}"
         style="background:#0ea5e9;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
        Accept Invitation
      </a>
    </p>
    """
    subject = f"[StudyGroup] {current_user.name} invited you to '{group.name}'"
    msg = _build_mime(emails, subject, html)
    _send(msg, emails)
    flash(f"Invitation sent to {', '.join(emails)}.", "success")
    return redirect(url_for("groups.detail", group_id=group_id))


# ── Grant SOS quota (owner / developer only) ─────────────────────────────

@groups_bp.route("/<int:group_id>/grant-sos/<int:user_id>", methods=["POST"])
@login_required
def grant_sos(group_id, user_id):
    """Group owner grants extra SOS sends to a member who has run out."""
    group = Group.query.get_or_404(group_id)

    # Only the group owner can grant extra SOS
    if group.owner_id != current_user.id:
        abort(403)

    target = User.query.get_or_404(user_id)
    if not group.is_member(target):
        abort(404)

    try:
        amount = int(request.form.get("amount", 3))
        amount = max(1, min(amount, 10))   # clamp 1–10
    except (ValueError, TypeError):
        amount = 3

    target.grant_sos(amount)
    from app.extensions import db as _db
    _db.session.commit()

    flash(
        f"✅ Granted {amount} extra SOS use{'s' if amount != 1 else ''} to {target.name}.",
        "success"
    )
    return redirect(url_for("groups.detail", group_id=group_id))
