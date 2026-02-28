from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app,  get_flashed_messages
from flask_login import login_user, logout_user, login_required, current_user
from LoanMVP.models.user_model import User
from LoanMVP.extensions import db
from LoanMVP.forms import LoginForm, ResetPasswordRequestForm, ResetPasswordForm, RegisterForm
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message
from LoanMVP.app import mail, login_manager
from datetime import datetime
from LoanMVP.utils.decorators import role_required   # ✅ import custom decorator

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

serializer = URLSafeTimedSerializer("super-secret-key")

# ------------------------------------------------
# 🔐 Token Helpers
# ------------------------------------------------
def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

def generate_reset_token(email: str) -> str:
    return _reset_serializer().dumps(
        email,
        salt=current_app.config["SECURITY_PASSWORD_SALT"]
    )

def verify_reset_token(token: str, expiration_seconds: int = 3600):
    try:
        return _reset_serializer().loads(
            token,
            salt=current_app.config["SECURITY_PASSWORD_SALT"],
            max_age=expiration_seconds
        )
    except (SignatureExpired, BadSignature):
        return None


# ------------------------------------------------
# 🟩 Login
# ------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # clears stale "welcome" / old messages
        get_flashed_messages()
        return render_template("auth/login.html", title="Login | Ravlo")

    # POST continues as normal...
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("⚠️ Please enter both email and password.", "warning")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash("🚫 Your account is deactivated. Contact admin for access.", "danger")
                return redirect(url_for("auth.login"))

            # ✅ Log in user and update timestamp
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()

            display_name = user.full_name or user.email
            flash(f"👋 Welcome back, {display_name}!", "success")

            # ✅ 1. Check if user tried to access a protected page before login
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)

            # ✅ 2. Role-based redirect (explicit control)
            if user.role.lower() == "admin":
                return redirect(url_for("admin.dashboard"))
            elif user.role.lower() == "loan_officer":
                return redirect(url_for("loan_officer.dashboard"))
            elif user.role.lower() == "processor":
                return redirect(url_for("processor.dashboard"))
            elif user.role.lower() == "underwriter":
                return redirect(url_for("underwriter.dashboard"))
            elif user.role.lower() == "borrower":
                return redirect(url_for("borrower.dashboard"))
            elif user.role.lower() == "executive":
                return redirect(url_for("executive.dashboard"))
            elif user.role.lower() == "compliance":
                return redirect(url_for("compliance.dashboard"))
            elif user.role.lower() == "property":
                return redirect(url_for("property.dashboard"))
            elif user.role.lower() == "system":
                return redirect(url_for("system.dashboard"))
            elif user.role.lower() == "crm":
                return redirect(url_for("crm.dashboard"))
            elif user.role.lower() == "ai":
                return redirect(url_for("ai.dashboard"))
            elif user.role.lower() == "intelligence":
                return redirect(url_for("intelligence.dashboard"))
            else:
                # fallback if role doesn't have a dashboard
                flash("✅ Logged in successfully — redirected to home.", "info")
                return redirect(url_for("index"))

        # ❌ Wrong credentials
        flash("❌ Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html", title="Login | LoanMVP")

# ------------------------------------------------
# 🟥 Logout
# ------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))

# ------------------------------------------------
# 🔁 Password Reset Request
# ------------------------------------------------
@auth_bp.route("/reset_password_request", methods=["GET", "POST"])
def reset_password_request():
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = generate_reset_token(user.email)
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            print(f" Password reset link: {reset_link}")
            flash("Password reset instructions have been sent to your email.", "info")
            return redirect(url_for("auth.login"))
        flash("No account found with that email.", "warning")

    return render_template("auth/reset_password_request.html", form=form)


# ----------------------------
# 📧 Forgot password (request link)
# ----------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()

        # Don't reveal whether user exists (more secure, less abuse)
        if not user:
            flash("📧 If that email exists, a reset link has been sent.", "info")
            return redirect(url_for("auth.login"))

        token = generate_reset_token(user.email)
        reset_link = url_for("auth.reset_password", token=token, _external=True)

        msg = Message(
            subject="Reset your Ravlo password",
            recipients=[user.email],
            body=(
                f"Hi {user.full_name or 'there'},\n\n"
                f"Click the link below to reset your password (expires in 1 hour):\n\n"
                f"{reset_link}\n\n"
                f"If you didn’t request this, ignore this email.\n"
            ),
        )

        try:
            mail.send(msg)
        except Exception as e:
            print("Mail error:", e)
            flash("⚠️ Could not send email right now. Please try again.", "danger")
            return redirect(url_for("auth.forgot_password"))

        flash("📧 Reset link sent. Check your email.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


# ----------------------------
# 🔑 Reset password (set new password)
# ----------------------------
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token, expiration_seconds=3600)
    if not email:
        flash("❌ Reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("⚠️ Account not found.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if len(password) < 8:
            flash("⚠️ Password must be at least 8 characters.", "warning")
            return redirect(request.url)

        if password != confirm:
            flash("⚠️ Passwords do not match.", "warning")
            return redirect(request.url)

        user.set_password(password)
        db.session.commit()

        flash("✅ Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
# ------------------------------------------------
# 🆕 Register
# ------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
       if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
       if existing_user:
           flash("Account already exists. Please log in.", "info")
           return redirect(url_for("auth.login"))

        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Auto-login
        login_user(user, remember=True)

        # ⭐ Borrowers go to onboarding
        if user.role.lower() == "borrower":
            return redirect(url_for("borrower.create_profile"))

        # ⭐ Everyone else goes to login (then dashboard)
        flash("🎉 Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)

@auth_bp.route("/register_borrower", methods=["GET", "POST"])
def register_borrower():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

        if not full_name or not email or not password:
            flash("Please complete all fields.", "warning")
            return redirect(url_for("auth.register_borrower"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            username=email,
            email=email,
            full_name=full_name,
            role="borrower",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        return redirect(url_for("borrower.create_profile"))

    return render_template("auth/register_borrower.html")


# ----------------------------
# ⚙️ LOGIN MANAGER LOADER
# ----------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

