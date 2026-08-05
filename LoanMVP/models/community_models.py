# LoanMVP/models/community_models.py
"""Ravlo Community: professional networking across the ecosystem (not a
consumer social feed). v1 scope is deliberately narrow -- one group ("Real
Estate"), text posts, text comments, no reactions/likes, no AI-matching.
The point of this slice is to find out whether people actually talk to
each other in a shared group before investing in anything smarter.
"""
from datetime import datetime

from LoanMVP.extensions import db


class CommunityGroup(db.Model):
    __tablename__ = "community_groups"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "CommunityPost", back_populates="group", lazy=True, order_by="CommunityPost.created_at.desc()"
    )

    def __repr__(self):
        return f"<CommunityGroup {self.slug}>"


class CommunityPost(db.Model):
    __tablename__ = "community_posts"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("community_groups.id", name="fk_post_group_id"), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_post_author_id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("CommunityGroup", back_populates="posts")
    author = db.relationship("User", backref=db.backref("community_posts", lazy=True))
    comments = db.relationship(
        "CommunityComment", back_populates="post", lazy=True, order_by="CommunityComment.created_at.asc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<CommunityPost {self.id} - group={self.group_id}>"


class CommunityComment(db.Model):
    __tablename__ = "community_comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("community_posts.id", name="fk_comment_post_id"), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_comment_author_id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("CommunityPost", back_populates="comments")
    author = db.relationship("User", backref=db.backref("community_comments", lazy=True))

    def __repr__(self):
        return f"<CommunityComment {self.id} - post={self.post_id}>"
