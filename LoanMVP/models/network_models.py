# LoanMVP/models/network_models.py
"""Ravlo Network: professional networking across the ecosystem (not a
consumer social feed). v1 scope is deliberately narrow -- one group ("Real
Estate"), text posts, text comments, no reactions/likes, no AI-matching.
The point of this slice is to find out whether people actually talk to
each other in a shared group before investing in anything smarter.
"""
from datetime import datetime

from LoanMVP.extensions import db


class NetworkGroup(db.Model):
    __tablename__ = "network_groups"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "NetworkPost", back_populates="group", lazy=True, order_by="NetworkPost.created_at.desc()"
    )

    def __repr__(self):
        return f"<NetworkGroup {self.slug}>"


class NetworkPost(db.Model):
    __tablename__ = "network_posts"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("network_groups.id", name="fk_post_group_id"), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_post_author_id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("NetworkGroup", back_populates="posts")
    author = db.relationship("User", backref=db.backref("network_posts", lazy=True))
    comments = db.relationship(
        "NetworkComment", back_populates="post", lazy=True, order_by="NetworkComment.created_at.asc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<NetworkPost {self.id} - group={self.group_id}>"


class NetworkComment(db.Model):
    __tablename__ = "network_comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("network_posts.id", name="fk_comment_post_id"), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_comment_author_id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("NetworkPost", back_populates="comments")
    author = db.relationship("User", backref=db.backref("network_comments", lazy=True))

    def __repr__(self):
        return f"<NetworkComment {self.id} - post={self.post_id}>"
