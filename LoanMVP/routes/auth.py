from datetime import datetime
from sqlalchemy import func
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
from LoanMVP.forms import RegisterForm, ResetPasswordForm, ResetPasswordRequestForm, LoginForm
from utils.subscriptions import sync_features_with_subscription

from LoanMVP.models.user_model import User
from LoanMVP.models.admin import UserInvite
from LoanMVP.models.investor_models import InvestorProfile
from flask_mail import Message as MailMessage


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Roles that must request admin approval before activation
RESTRICTED_STAFF_ROLES = {
    "loan_officer",
    "processor",
    "underwriter",
}
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
    form = LoginForm()

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        # ⭐ STEP 3: Sync subscription → features
        sync_features_with_subscription(user.id)

        # Continue login
        login_user(user)
        return redirect(url_for("auth.post_login_redirect"))

    return render_template("auth/login.html", form=form)



@auth_bp.route("/register/invite/<token>", methods=["GET", "POST"])
@csrf.exempt
def register_from_invite(token):
    invite = UserInvite.query.filter_by(token=token).first_or_404()

    if invite.status != "pending":
        flash("This invite is no longer active.", "warning")
        return redirect(url_for("auth.login"))

    if invite.is_expired():
        invite.status = "expired"
        db.session.commit()
        flash("This invite link has expired.", "warning")
        return redirect(url_for("auth.login"))

    existing_user = User.query.filter_by(email=invite.email).first()
    if existing_user:
        flash("An account already exists for this email. Please log in.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not full_name:
            flash("Please enter your full name.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            username=full_name or None,
            email=invite.email,
            role=invite.role,
            company_id=invite.company_id,
            password_hash=generate_password_hash(password),
            is_active=True,
            invite_accepted=True,
        )

        db.session.add(user)

        invite.status = "accepted"
        invite.accepted_at = datetime.utcnow()

        db.session.commit()

        flash("Registration complete. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register_from_invite.html", invite=invite)


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
        role = (form.role.data or "").strip().lower()
        full_name = (form.full_name.data or "").strip()
        email = (form.email.data or "").strip().lower()

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template("auth/register.html", form=form)

        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            username=full_name or None,
            email=email,
            role=role,
            is_active=True,
        )

        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        login_user(user)

        flash("Welcome to Ravlo. Let's set up your profile.", "info")

        if role == "investor":
            return redirect(url_for("investor.create_profile"))

        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "POST":
        flash("Please correct the errors in the form.", "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/post-login-redirect")
@login_required
def post_login_redirect():
    if current_user.role == "investor":
        profile = InvestorProfile.query.filter_by(user_id=current_user.id).first()

        if not profile:
            flash("Please complete your investor profile first.", "info")
            return redirect(url_for("investor.create_profile"))

    return redirect(url_for(_dashboard_for_role(current_user.role)))

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

        parts = full_name.split(None, 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""

        user = User(
            username=full_name or email,
            email=email,
            first_name=first or None,
            last_name=last or None,
            role="borrower",
            is_active=True,
        )

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

    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first()

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
            flash("Could not send email right now. Please try again.", "danger")
            return redirect(url_for("auth.forgot_password"))

        flash("Reset link sent. Check your email.", "success")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        print("FORGOT PASSWORD FORM ERRORS:", form.errors)

    return render_template(
        "auth/forgot_password.html",
        form=form,
        title="Forgot Password | Ravlo",
    )
    

@auth_bp.route("/request-access", methods=["GET", "POST"])
def request_access():
    requested_role = (request.args.get("requested_role") or request.form.get("requested_role") or "").strip().lower()

    if requested_role == "loan officer":
        requested_role = "loan_officer"

    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        contact_name = (request.form.get("contact_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        requested_role = (request.form.get("requested_role") or "").strip().lower()

        if requested_role == "loan officer":
            requested_role = "loan_officer"

        if requested_role not in RESTRICTED_STAFF_ROLES:
            flash("Invalid restricted role selection.", "danger")
            return redirect(url_for("auth.request_access"))

        if not contact_name or not email:
            flash("Please provide your name and email.", "warning")
            return redirect(url_for("auth.request_access", requested_role=requested_role))

        existing = AccessRequest.query.filter(
            AccessRequest.email.ilike(email),
            AccessRequest.requested_role == requested_role,
            AccessRequest.status.in_(["pending", "approved"])
        ).first()

        if existing:
            flash("An access request already exists for this email and role.", "info")
            return redirect(url_for("auth.login"))

        req = AccessRequest(
            company_name=company_name or None,
            contact_name=contact_name,
            email=email,
            phone=phone or None,
            request_type="company_setup",
            requested_role=requested_role,
            status="pending",
            notes=notes or None,
        )

        db.session.add(req)
        db.session.commit()

        flash("Your access request has been submitted. An admin will review it.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/request_access.html",
        requested_role=requested_role
    )
# ============================================================
# RESET PASSWORD
# ============================================================


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
