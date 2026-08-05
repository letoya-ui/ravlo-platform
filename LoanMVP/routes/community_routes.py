# LoanMVP/routes/community_routes.py
"""Ravlo Community: professional networking across the ecosystem. v1
scope is one seeded group ("real-estate"), text posts, text comments --
no reactions, no AI-matching yet. See LoanMVP/models/community_models.py
for why.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.models.community_models import CommunityComment, CommunityPost
from LoanMVP.services.community_service import get_or_create_group, resolve_professional_label

community_bp = Blueprint("community", __name__, url_prefix="/community")

# v1: exactly one group exists. Adding a second ecosystem's group later is
# a new entry here, not new routes/templates.
_SEEDED_GROUPS = {
    "real-estate": ("Real Estate", "Realtors, lenders, investors, contractors, insurance, and property managers."),
}


def _ensure_seeded_group(slug):
    if slug not in _SEEDED_GROUPS:
        abort(404)
    name, description = _SEEDED_GROUPS[slug]
    return get_or_create_group(slug, name=name, description=description)


@community_bp.get("/<slug>")
def feed(slug):
    group = _ensure_seeded_group(slug)
    posts = (
        CommunityPost.query.filter_by(group_id=group.id)
        .order_by(CommunityPost.created_at.desc())
        .all()
    )

    posts_with_meta = [
        {
            "post": post,
            "author_label": resolve_professional_label(post.author),
            "comment_count": len(post.comments),
        }
        for post in posts
    ]

    return render_template("community/feed.html", group=group, posts_with_meta=posts_with_meta)


@community_bp.post("/<slug>/posts")
@login_required
def create_post(slug):
    group = _ensure_seeded_group(slug)

    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Write something before posting.", "error")
        return redirect(url_for("community.feed", slug=slug))

    post = CommunityPost(group_id=group.id, author_user_id=current_user.id, body=body)
    db.session.add(post)
    db.session.commit()

    return redirect(url_for("community.feed", slug=slug))


@community_bp.get("/<slug>/posts/<int:post_id>")
def post_detail(slug, post_id):
    group = _ensure_seeded_group(slug)
    post = CommunityPost.query.filter_by(id=post_id, group_id=group.id).first_or_404()

    comments_with_meta = [
        {"comment": comment, "author_label": resolve_professional_label(comment.author)}
        for comment in post.comments
    ]

    return render_template(
        "community/post_detail.html",
        group=group,
        post=post,
        author_label=resolve_professional_label(post.author),
        comments_with_meta=comments_with_meta,
    )


@community_bp.post("/<slug>/posts/<int:post_id>/comments")
@login_required
def create_comment(slug, post_id):
    group = _ensure_seeded_group(slug)
    post = CommunityPost.query.filter_by(id=post_id, group_id=group.id).first_or_404()

    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Write a comment before submitting.", "error")
        return redirect(url_for("community.post_detail", slug=slug, post_id=post_id))

    comment = CommunityComment(post_id=post.id, author_user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()

    return redirect(url_for("community.post_detail", slug=slug, post_id=post_id))
