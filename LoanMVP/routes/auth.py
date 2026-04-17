from datetime import datetime
import secrets
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
from werkzeug.security import generate_password_hash

from LoanMVP.app import login_manager, mail
from LoanMVP.extensions import csrf, db
from LoanMVP.forms import RegisterForm, ResetPasswordForm, ResetPasswordRequestForm, LoginForm
from LoanMVP.services.subscriptions import sync_features_with_subscription
from LoanMVP.utils.blocking_helpers import is_user_blocked, get_user_block_message
from LoanMVP.models.user_model import User
from LoanMVP.models.admin import AccessRequest, UserInvite, LicenseApplication, Company
from LoanMVP.models.investor_models import InvestorProfile
from flask_mail import Message as MailMessage


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Roles that must request admin approval before activation
RESTRICTED_STAFF_ROLES = {
    "loan_officer",
    "processor",
    "underwriter",
}


def _single_admin_mode_enabled() -> bool:
    return False


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


def _workspace_executive_roles() -> set[str]:
    return {"executive", "platform_admin", "master_admin", "lending_admin"}


def _can_bypass_single_admin_lock(user) -> bool:
    if not user:
        return False

    email = (getattr(user, "email", "") or "").strip().lower()
    if email == _owner_admin_email():
        return True

    role = (getattr(user, "role", "") or "").strip().lower()
    return role in _workspace_executive_roles()


# Accounts that should always land on the executive dashboard regardless
# of their stored role.  Keep addresses lower-cased.
_EXECUTIVE_DASHBOARD_EMAILS: set[str] = {
    "letoya@ravlohq.com",
    "jamaine.caughman@ravlohq.com",
}


def _is_executive_dashboard_user(user) -> bool:
    if not user:
        return False

    email = (getattr(user, "email", "") or "").strip().lower()
    if email in _EXECUTIVE_DASHBOARD_EMAILS:
        return True

    role = (getattr(user, "role", "") or "").strip().lower()
    return role == "executive"


def _owner_admin_exists() -> bool:
    owner_email = _owner_admin_email()
    if not owner_email:
        return False
    return (
        db.session.query(User.id)
        .filter(func.lower(User.email) == owner_email)
        .first()
        is not None
    )


def _workspace_recovery_mode() -> bool:
    return db.session.query(User.id).first() is None


def _registration_blocked() -> bool:
    return False


def _auth_page_context() -> dict:
    return {
        "recovery_mode": _workspace_recovery_mode(),
        "owner_admin_email": _owner_admin_email(),
    }


def _default_investor_company_id() -> int | None:
    company = Company.query.filter(
        func.lower(Company.name) == "caughman mason loan service"
    ).first()
    return getattr(company, "id", None)


def _ravlo_company() -> Company:
    company = Company.query.filter(
        (func.lower(Company.name) == "ravlo")
        | (func.lower(func.coalesce(Company.email_domain, "")) == "ravlohq.com")
    ).first()

    if company:
        return company

    company = Company(
        name="Ravlo",
        email_domain="ravlohq.com",
        is_active=True,
        subscription_tier="enterprise",
    )
    db.session.add(company)
    db.session.flush()
    return company


def _default_ravlo_company_id() -> int | None:
    return getattr(_ravlo_company(), "id", None)


def _resolve_registration_company_id(role: str, explicit_company_id=None):
    role = (role or "").strip().lower()
    if explicit_company_id:
        return explicit_company_id
    if role == "investor":
        return _default_investor_company_id()
    if role in _workspace_executive_roles():
        return _default_ravlo_company_id()
    return None
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

# VIP user routing — specific users get their own personalized dashboard on
# login, overriding role-based dispatch. Keys must be normalized (lowercased,
# stripped). Values are Flask endpoint strings registered on the app.
# Add a new VIP by creating their blueprint/endpoint first, then adding a
# mapping here.
VIP_USER_DASHBOARDS = {
    "nyrealtorelena@gmail.com": "elena.dashboard",
}


def _vip_dashboard_endpoint(user) -> str | None:
    email = (getattr(user, "email", "") or "").strip().lower()
    return VIP_USER_DASHBOARDS.get(email)


def _safe_next_url(default_endpoint: str = "investor.command_center"):
    next_page = (request.args.get("next") or "").strip()
    if next_page.startswith("/"):
        return next_page
    return url_for(default_endpoint)


def _dashboard_for_role(role: str) -> str:
    role = (role or "").strip().lower()

    admin_roles = {"admin", "platform_admin", "master_admin", "lending_admin"}
    if role in admin_roles:
        return "admin.dashboard"

    dashboard_map = {
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

    return dashboard_map.get(role, "marketing.homepage")

def _full_name_from_user(user: User) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    full_name = f"{first} {last}".strip()

    if full_name:
        return full_name

    return getattr(user, "full_name", None) or getattr(user, "username", None) or "there"


def _parse_name_parts(full_name: str, first_name: str, last_name: str):
    full_name = (full_name or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    if full_name and not first_name:
        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else last_name

    full_name = full_name or f"{first_name} {last_name}".strip()
    return first_name, last_name, full_name


# ============================================================
# LOGIN
# ============================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form, **_auth_page_context())

        if (
            _single_admin_mode_enabled()
            and _owner_admin_exists()
            and not _can_bypass_single_admin_lock(user)
        ):
            flash("This workspace is locked to the owner admin and executive leadership accounts.", "warning")
            return render_template("auth/login.html", form=form, **_auth_page_context())

        # ⭐ STEP 3: Sync subscription → features
        sync_features_with_subscription(user.id)

        if is_user_blocked(user):
            flash(get_user_block_message(user), "danger")
            return render_template("auth/login.html", form=form, **_auth_page_context())

        # Continue login
        login_user(user)
        next_page = request.args.get("next")
        return redirect(url_for("auth.post_login_redirect", next=next_page))

    return render_template("auth/login.html", form=form, **_auth_page_context())



@auth_bp.route("/register/invite/<token>", methods=["GET", "POST"])
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
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not full_name and not first_name:
            flash("Please enter your name.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register_from_invite.html", invite=invite)

        first_name, last_name, full_name = _parse_name_parts(full_name, first_name, last_name)

        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            username=full_name or None,
            email=invite.email,
            role=invite.role,
            company_id=_resolve_registration_company_id(invite.role, invite.company_id),
            password_hash=generate_password_hash(password),
            is_active=True,
            invite_accepted=True,
            onboarding_complete=False,
        )

        db.session.add(user)

        invite.status = "accepted"
        invite.accepted_at = datetime.utcnow()

        db.session.commit()

        login_user(user)
        flash("Invite accepted. Complete your profile to continue.", "success")
        return redirect(url_for("auth.complete_profile"))

    return render_template("auth/register_from_invite.html", invite=invite)


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout", methods=["POST"])
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
def register():
    recovery_mode = _workspace_recovery_mode()

    if _registration_blocked():
        flash("Self-serve registration is disabled for this workspace.", "warning")
        return redirect(url_for("auth.login"))

    form = RegisterForm()

    if form.validate_on_submit():
        full_name = (form.full_name.data or "").strip()
        email = (form.email.data or "").strip().lower()
        owner_email = _owner_admin_email()
        role = (form.role.data or "").strip().lower()

        if recovery_mode:
            if owner_email and email != owner_email:
                flash(
                    f"Recovery mode is active. Register the owner admin account using {owner_email}.",
                    "warning",
                )
                return render_template(
                    "auth/register.html",
                    form=form,
                    recovery_mode=recovery_mode,
                    owner_admin_email=owner_email,
                )
            role = "admin"

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template(
                "auth/register.html",
                form=form,
                recovery_mode=recovery_mode,
                owner_admin_email=owner_email,
            )

        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            username=full_name or None,
            email=email,
            role=role,
            company_id=_resolve_registration_company_id(role),
            is_active=True,
        )

        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        login_user(user)

        if recovery_mode:
            flash("Owner admin account restored. You can now invite or create users again.", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Welcome to Ravlo. Let's set up your profile.", "info")

        if role == "investor":
            return redirect(url_for("investor.create_profile"))

        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "POST":
        flash("Please correct the errors in the form.", "danger")

    return render_template(
        "auth/register.html",
        form=form,
        recovery_mode=recovery_mode,
        owner_admin_email=_owner_admin_email(),
    )


@auth_bp.route("/restore-owner-admin", methods=["GET", "POST"])
def restore_owner_admin():
    if not _workspace_recovery_mode():
        flash("Owner admin recovery is only available when the workspace needs to be restored.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        return redirect(url_for("auth.register"))

    return render_template(
        "auth/restore_owner_admin.html",
        owner_admin_email=_owner_admin_email(),
    )


@auth_bp.route("/post-login-redirect")
@login_required
def post_login_redirect():
    role = (current_user.role or "").strip().lower()

    if current_user.invite_accepted and not current_user.onboarding_complete:
        return redirect(url_for("auth.complete_profile"))

    vip_endpoint = _vip_dashboard_endpoint(current_user)
    if vip_endpoint:
        return redirect(url_for(vip_endpoint))

    if _is_executive_dashboard_user(current_user):
        return redirect(url_for("executive.dashboard"))

    if role == "admin" and current_user.company_id:
        return redirect(url_for("admin.company_dashboard", company_id=current_user.company_id))

    if role in ["admin", "platform_admin", "master_admin", "lending_admin"]:
        return redirect(url_for("admin.dashboard"))

    # 👇 only allow next for non-admin users
    next_page = (request.args.get("next") or "").strip()
    if next_page.startswith("/"):
        return redirect(next_page)

    return redirect(url_for(_dashboard_for_role(role)))

# ============================================================
# OPTIONAL BORROWER REGISTER
# ============================================================

@auth_bp.route("/register_borrower", methods=["GET", "POST"])
def register_borrower():
    if _registration_blocked():
        flash("Borrower registration is disabled for this workspace.", "warning")
        return redirect(url_for("auth.login"))

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
        "auth/forgot_password_form.html",
        form=form,
        title="Forgot Password | Ravlo",
    )
    

@auth_bp.route("/request-access", methods=["GET", "POST"])
def request_access():
    if _registration_blocked():
        flash("Access requests are disabled while single-admin mode is active.", "warning")
        return redirect(url_for("auth.login"))

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

        auto_approve_beta = bool(
            current_app.config.get("BETA_ACCESS_AUTO_APPROVE", False)
            and not current_app.config.get("STRIPE_BILLING_ENABLED", False)
        )

        req = AccessRequest(
            company_name=company_name or None,
            contact_name=contact_name,
            email=email,
            phone=phone or None,
            request_type="company_setup",
            requested_role=requested_role,
            status="approved" if auto_approve_beta else "pending",
            notes=notes or None,
        )

        db.session.add(req)
        if auto_approve_beta:
            existing_user = User.query.filter(func.lower(User.email) == email).first()
            if not existing_user:
                generated_password = secrets.token_urlsafe(12)
                name_parts = contact_name.split(None, 1)
                first_name = name_parts[0] if name_parts else contact_name
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                beta_user = User(
                    first_name=first_name or None,
                    last_name=last_name or None,
                    username=contact_name or email,
                    email=email,
                    role=requested_role,
                    is_active=True,
                    invite_accepted=True,
                )
                beta_user.set_password(generated_password)
                db.session.add(beta_user)

        db.session.commit()

        if auto_approve_beta:
            token = generate_reset_token(email)
            flash(
                "Beta access approved! Please set your password to get started.",
                "success",
            )
            return redirect(url_for("auth.reset_password", token=token))

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


@auth_bp.route("/accept-invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    invite = UserInvite.query.filter_by(token=token).first_or_404()

    if invite.status == "accepted":
        flash("This invite has already been used.", "info")
        return redirect(url_for("auth.login"))

    if invite.is_expired():
        flash("This invite has expired.", "warning")
        return redirect(url_for("auth.login"))

    existing_user = User.query.filter_by(email=invite.email).first()

    if request.method == "POST":
        first_name = (request.form.get("first_name") or invite.first_name or "").strip()
        last_name = (request.form.get("last_name") or invite.last_name or "").strip()
        password = (request.form.get("password") or "").strip()

        if not first_name:
            flash("First name is required.", "warning")
            return render_template("auth/accept_invite.html", invite=invite)

        if not last_name:
            flash("Last name is required.", "warning")
            return render_template("auth/accept_invite.html", invite=invite)

        if not password:
            flash("Password is required.", "warning")
            return render_template("auth/accept_invite.html", invite=invite)

        if existing_user:
            user = existing_user

            if not user.password_hash:
                user.password_hash = generate_password_hash(password)

            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            if not user.username:
                user.username = f"{first_name} {last_name}".strip() or user.email
            user.company_id = _resolve_registration_company_id(invite.role, invite.company_id)
            user.role = invite.role
            user.invite_accepted = True
            user.is_active = True
            user.onboarding_complete = bool(user.first_name and user.last_name)
        else:
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=f"{first_name} {last_name}".strip() or invite.email,
                email=invite.email,
                password_hash=generate_password_hash(password),
                role=invite.role,
                company_id=_resolve_registration_company_id(invite.role, invite.company_id),
                is_active=True,
                invite_accepted=True,
                onboarding_complete=False,
            )
            db.session.add(user)
            db.session.flush()

        invite.status = "accepted"
        invite.accepted_at = datetime.utcnow()

        app_row = LicenseApplication.query.filter_by(email=invite.email).order_by(
            LicenseApplication.created_at.desc()
        ).first()
        if app_row:
            app_row.status = "onboarded"

        db.session.commit()

        login_user(user)
        flash("Invite accepted. Complete your profile to continue.", "success")
        return redirect(url_for("auth.complete_profile"))

    return render_template("auth/accept_invite.html", invite=invite)

@auth_bp.route("/complete-profile", methods=["GET", "POST"])
@login_required
def complete_profile():
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()

        if not first_name:
            flash("First name is required.", "warning")
            return render_template("auth/complete_profile.html", user=current_user)

        if not last_name:
            flash("Last name is required.", "warning")
            return render_template("auth/complete_profile.html", user=current_user)

        current_user.first_name = first_name
        current_user.last_name = last_name
        if not current_user.username:
            current_user.username = f"{first_name} {last_name}".strip() or current_user.email
        current_user.onboarding_complete = True

        db.session.commit()

        flash("Profile completed successfully.", "success")

        role = (current_user.role or "").strip().lower()
        if role == "investor":
            return redirect(url_for("investor.create_profile"))
        if role == "borrower":
            return redirect(url_for("borrower.create_profile"))

        return redirect(url_for(_dashboard_for_role(role)))

    if current_user.invite_accepted and current_user.onboarding_complete:
        return redirect(url_for(_dashboard_for_role(current_user.role)))

    return render_template("auth/complete_profile.html", user=current_user)
