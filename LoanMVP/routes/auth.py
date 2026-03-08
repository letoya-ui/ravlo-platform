from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from LoanMVP.app import login_manager, mail
from LoanMVP.extensions import csrf, db
from LoanMVP.forms import RegisterForm, ResetPasswordForm, ResetPasswordRequestForm
from LoanMVP.models.user_model import User
from flask_mail import Message as MailMessage


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ============================================================
# TOKEN HELPERS
# ============================================================

def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_reset_token(email: str) -> str:
    return _reset_serializer().dumps(
        email,
        salt=current_app.config["SECURITY_PASSWORD_SALT"],
    )


def verify_reset_token(token: str, expiration_seconds: int = 3600):
    try:
        return _reset_serializer().loads(
            token,
            salt=current_app.config["SECURITY_PASSWORD_SALT"],
            max_age=expiration_seconds,
        )
    except (SignatureExpired, BadSignature):
        return None


# ============================================================
# HELPERS
# ============================================================

def _safe_next_url(default_endpoint: str = "investor.command_center"):
    next_page = (request.args.get("next") or "").strip()
    if next_page.startswith("/"):
        return next_page
    return url_for(default_endpoint)


def _dashboard_for_role(role: str) -> str:
    role = (role or "").strip().lower()

    dashboard_map = {
        "admin": "admin.dashboard",
        "loan_officer": "loan_officer.dashboard",
        "processor": "processor.dashboard",
        "underwriter": "underwriter.dashboard",
        "investor": "investor.command_center",
        "executive": "executive.dashboard",
        "compliance": "compliance.dashboard",
        "property": "property.dashboard",
        "system": "system.dashboard",
        "crm": "crm.dashboard",
        "ai": "ai.dashboard",
        "intelligence": "intelligence.dashboard",
        "partner": "partners.dashboard",
        "borrower": "borrower.create_profile",
    }

    return dashboard_map.get(role, "investor.command_center")


def _full_name_from_user(user: User) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    full_name = f"{first} {last}".strip()

    if full_name:
        return full_name

    return getattr(user, "full_name", None) or getattr(user, "username", None) or "there"


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
@csrf.exempt
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_dashboard_for_role(getattr(current_user, "role", "investor"))))

    if request.method == "GET":
        get_flashed_messages()
        return render_template("auth/login.html", title="Login | Ravlo")

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    remember = bool(request.form.get("remember"))

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    if hasattr(user, "is_active") and user.is_active is False:
        flash("Your account is deactivated. Contact admin for access.", "error")
        return redirect(url_for("auth.login"))

    session.permanent = True
    login_user(user, remember=remember)
    user.last_login = datetime.utcnow()
    db.session.commit()

    flash("Welcome back.", "success")

    next_page = (request.args.get("next") or "").strip()
    if next_page.startswith("/"):
        return redirect(next_page)

    return redirect(url_for(_dashboard_for_role(getattr(user, "role", "investor"))))


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout", methods=["POST", "GET"])
@csrf.exempt
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("auth.login"))


# ============================================================
# REGISTER
# ============================================================

@auth_bp.route("/register", methods=["GET", "POST"])
@csrf.exempt
def register():

    form = RegisterForm()

    if form.validate_on_submit():

        full_name = form.username.data.strip()
        email = form.email.data.lower().strip()
        password = form.password.data
        role = form.role.data

        existing = User.query.filter_by(email=email).first()

        if existing:
            flash("Account already exists. Please login.", "error")
            return redirect(url_for("auth.login"))

        parts = full_name.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""

        user = User(
            username=email,
            email=email,
            first_name=first,
            last_name=last,
            role=role
        )

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        login_user(user)

        flash("Account created successfully.", "success")

        return redirect(url_for(_dashboard_for_role(user.role)))

    # DEBUG so you see validation problems
    if request.method == "POST":
        print("REGISTER ERRORS:", form.errors)

    return render_template(
        "auth/register.html",
        form=form
    )

# ============================================================
# OPTIONAL BORROWER REGISTER
# ============================================================

@auth_bp.route("/register_borrower", methods=["GET", "POST"])
@csrf.exempt
def register_borrower():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not full_name or not email or not password:
            flash("Please complete all fields.", "error")
            return redirect(url_for("auth.register_borrower"))

        if password != confirm_password and confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register_borrower"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("auth.register_borrower"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.", "error")
            return redirect(url_for("auth.login"))

        parts = full_name.split(" ", 1)
        first = parts[0].strip()
        last = parts[1].strip() if len(parts) > 1 else ""

        user = User(
            username=email,
            email=email,
            first_name=first,
            last_name=last,
            role="borrower",
        )

        if hasattr(user, "full_name"):
            user.full_name = full_name

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        session.permanent = True
        login_user(user, remember=True)

        flash("Borrower account created successfully.", "success")
        return redirect(url_for("borrower.create_profile"))

    return render_template("auth/register_borrower.html", title="Register Borrower | Ravlo")


# ============================================================
# FORGOT PASSWORD / RESET REQUEST
# ============================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@auth_bp.route("/reset_password_request", methods=["GET", "POST"])
@csrf.exempt
def forgot_password():
    form = ResetPasswordRequestForm()

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()

        # Do not reveal whether account exists
        if not user:
            flash("If that email exists, a reset link has been sent.", "success")
            return redirect(url_for("auth.login"))

        token = generate_reset_token(user.email)
        reset_link = url_for("auth.reset_password", token=token, _external=True)

        msg = MailMessage(
            subject="Reset your Ravlo password",
            recipients=[user.email],
            body=(
                f"Hi {_full_name_from_user(user)},\n\n"
                f"Click the link below to reset your password. This link expires in 1 hour.\n\n"
                f"{reset_link}\n\n"
                f"If you didn’t request this, you can safely ignore this email.\n"
            ),
        )

        try:
            mail.send(msg)
        except Exception as e:
            print("Mail error:", e)
            flash("Could not send email right now. Please try again.", "error")
            return redirect(url_for("auth.forgot_password"))

        flash("Reset link sent. Check your email.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/forgot_password.html",
        form=form,
        title="Forgot Password | Ravlo",
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
@csrf.exempt
def reset_password(token):
    form = ResetPasswordForm()
    email = verify_reset_token(token, expiration_seconds=3600)

    if not email:
        flash("Reset link is invalid or expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(request.url)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(request.url)

        user.set_password(password)
        db.session.commit()

        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/reset_password.html",
        form=form,
        token=token,
        title="Reset Password | Ravlo",
    )


# ============================================================
# LOGIN MANAGER
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
