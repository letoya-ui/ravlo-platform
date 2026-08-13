# LoanMVP/routes/network_routes.py
"""Ravlo Network: professional networking across the ecosystem. v1 scope
was one seeded group ("real-estate"), text posts, text comments -- no
reactions, no AI-matching. v2 adds structured product/service listings
(title/category/price/photo), a search box, and a lightweight in-network
profile page for members who've actually posted. See
LoanMVP/models/network_models.py for the narrow-scope rationale.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from LoanMVP.extensions import db
from LoanMVP.models.network_models import NetworkComment, NetworkPost
from LoanMVP.models.user_model import User
from LoanMVP.services.network_service import (
    get_or_create_group,
    resolve_professional_label,
    resolve_profile_bio,
    resolve_profile_url,
)

network_bp = Blueprint("network", __name__, url_prefix="/network")

# v1: exactly one group exists. Adding a second ecosystem's group later is
# a new entry here, not new routes/templates.
_SEEDED_GROUPS = {
    "real-estate": ("Real Estate", "Realtors, lenders, investors, contractors, insurance, and property managers."),
}

# Listing categories match who's actually in the seeded real-estate group,
# not a generic freelance-marketplace taxonomy -- same set shown as the
# "ideas" grid on an empty feed.
LISTING_CATEGORIES = [
    ("interior_designers", "Interior Designers"),
    ("contractors", "Contractors"),
    ("stagers", "Stagers"),
    ("inspectors", "Inspectors"),
    ("lenders", "Lenders"),
    ("agents", "Agents"),
    ("vendors", "Vendors"),
    ("architects", "Architects"),
]
_LISTING_CATEGORY_KEYS = {key for key, _ in LISTING_CATEGORIES}
_LISTING_TYPES = {"update", "product", "service"}
_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _ensure_seeded_group(slug):
    if slug not in _SEEDED_GROUPS:
        abort(404)
    name, description = _SEEDED_GROUPS[slug]
    return get_or_create_group(slug, name=name, description=description)


def _post_meta(post):
    return {
        "post": post,
        "author_label": resolve_professional_label(post.author),
        "author_profile_url": resolve_profile_url(post.author),
        "comment_count": len(post.comments),
    }


def _save_post_image(post_id, file_storage):
    filename = secure_filename(file_storage.filename or "")
    ext = Path(filename).suffix.lower()
    if not filename or ext not in _ALLOWED_IMAGE_EXTENSIONS:
        return None

    upload_dir = Path("static/uploads/network") / str(post_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    file_storage.save(filepath)
    return f"/static/uploads/network/{post_id}/{filename}"


@network_bp.get("/<slug>")
def feed(slug):
    group = _ensure_seeded_group(slug)

    group_has_any_posts = NetworkPost.query.filter_by(group_id=group.id).first() is not None

    query = NetworkPost.query.filter_by(group_id=group.id)

    search_query = (request.args.get("q") or "").strip()
    if search_query:
        like_q = f"%{search_query}%"
        query = query.filter(
            db.or_(
                NetworkPost.title.ilike(like_q),
                NetworkPost.body.ilike(like_q),
                NetworkPost.category.ilike(like_q),
            )
        )

    category = (request.args.get("category") or "").strip()
    if category not in _LISTING_CATEGORY_KEYS:
        category = ""
    if category:
        query = query.filter(NetworkPost.category == category)

    posts = query.order_by(NetworkPost.created_at.desc()).all()
    posts_with_meta = [_post_meta(post) for post in posts]

    return render_template(
        "network/feed.html", group=group, posts_with_meta=posts_with_meta,
        categories=LISTING_CATEGORIES, search_query=search_query, active_category=category,
        group_has_any_posts=group_has_any_posts,
        page_title=f"{group.name} Network | Ravlo", page_key="network",
    )


@network_bp.post("/<slug>/posts")
@login_required
def create_post(slug):
    group = _ensure_seeded_group(slug)

    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Write something before posting.", "error")
        return redirect(url_for("network.feed", slug=slug))

    listing_type = (request.form.get("listing_type") or "update").strip().lower()
    if listing_type not in _LISTING_TYPES:
        listing_type = "update"

    title = (request.form.get("title") or "").strip() or None
    category = (request.form.get("category") or "").strip() or None
    if category not in _LISTING_CATEGORY_KEYS:
        category = None
    price_label = (request.form.get("price_label") or "").strip() or None

    post = NetworkPost(
        group_id=group.id, author_user_id=current_user.id, body=body,
        listing_type=listing_type, title=title, category=category, price_label=price_label,
    )
    db.session.add(post)
    db.session.flush()

    image = request.files.get("image")
    if image and image.filename:
        try:
            image_url = _save_post_image(post.id, image)
        except Exception as exc:
            current_app.logger.warning("[network] image upload failed: %s", exc)
            image_url = None
        if image_url:
            post.image_url = image_url
        else:
            flash("That image type isn't supported (use PNG, JPG, or WEBP). Post saved without it.", "warning")

    db.session.commit()

    return redirect(url_for("network.feed", slug=slug))


@network_bp.get("/<slug>/posts/<int:post_id>")
def post_detail(slug, post_id):
    group = _ensure_seeded_group(slug)
    post = NetworkPost.query.filter_by(id=post_id, group_id=group.id).first_or_404()

    comments_with_meta = [
        {
            "comment": comment,
            "author_label": resolve_professional_label(comment.author),
            "author_profile_url": resolve_profile_url(comment.author),
        }
        for comment in post.comments
    ]

    return render_template(
        "network/post_detail.html",
        group=group,
        post=post,
        author_label=resolve_professional_label(post.author),
        author_profile_url=resolve_profile_url(post.author),
        comments_with_meta=comments_with_meta,
        page_title=f"{group.name} Network | Ravlo", page_key="network",
    )


@network_bp.post("/<slug>/posts/<int:post_id>/comments")
@login_required
def create_comment(slug, post_id):
    group = _ensure_seeded_group(slug)
    post = NetworkPost.query.filter_by(id=post_id, group_id=group.id).first_or_404()

    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Write a comment before submitting.", "error")
        return redirect(url_for("network.post_detail", slug=slug, post_id=post_id))

    comment = NetworkComment(post_id=post.id, author_user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()

    return redirect(url_for("network.post_detail", slug=slug, post_id=post_id))


@network_bp.get("/<slug>/professionals/<int:user_id>")
def professional_profile(slug, user_id):
    group = _ensure_seeded_group(slug)
    member = User.query.get_or_404(user_id)

    posts = (
        NetworkPost.query.filter_by(group_id=group.id, author_user_id=member.id)
        .order_by(NetworkPost.created_at.desc())
        .all()
    )
    # Only members who've actually posted in this group get a profile page
    # -- keeps this from becoming an arbitrary user directory.
    if not posts:
        abort(404)

    return render_template(
        "network/professional_profile.html",
        group=group,
        member=member,
        author_label=resolve_professional_label(member),
        bio=resolve_profile_bio(member),
        full_profile_url=resolve_profile_url(member),
        posts_with_meta=[_post_meta(post) for post in posts],
        page_title=f"{member.full_name or member.email} | {group.name} Network",
        page_key="network",
    )
