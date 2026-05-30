"""Mobile API Blueprint - JWT-authenticated endpoints for Ravlo mobile apps."""

import os
import jwt
import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from LoanMVP.extensions import csrf, db

mobile_api = Blueprint('mobile_api', __name__, url_prefix='/mobile')
csrf.exempt(mobile_api)

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _get_secret():
    return (
        os.environ.get('JWT_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
        or 'ravlo-jwt-secret-2025'
    )


def _encode_token(user_id: int) -> str:
    payload = {
        'sub': user_id,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30),
    }
    return jwt.encode(payload, _get_secret(), algorithm='HS256')


def _decode_token(token: str) -> dict:
    return jwt.decode(token, _get_secret(), algorithms=['HS256'])


LOAN_ROLES = ('loan_officer', 'processor', 'underwriter', 'admin')
ADMIN_ROLES = ('admin', 'platform_admin', 'master_admin', 'lending_admin', 'executive')


def require_auth(f):
    """Decorator that validates Bearer JWT and injects current_user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        token = auth_header.split(' ', 1)[1]
        try:
            payload = _decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        try:
            from LoanMVP.models import User
            user = User.query.get(payload['sub'])
        except Exception:
            return jsonify({'error': 'Could not load user'}), 500

        if user is None:
            return jsonify({'error': 'User not found'}), 401

        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator that enforces admin/owner-only access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(request.current_user, 'role', '') not in ADMIN_ROLES:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def _serialize_user(user) -> dict:
    first = getattr(user, 'first_name', '') or ''
    last = getattr(user, 'last_name', '') or ''
    return {
        'id': getattr(user, 'id', None),
        'email': getattr(user, 'email', ''),
        'first_name': first,
        'last_name': last,
        'full_name': f'{first} {last}'.strip(),
        'role': getattr(user, 'role', 'borrower'),
        'subscription': getattr(user, 'subscription', 'free'),
        'university_tier': getattr(user, 'university_tier', None),
        'onboarding_complete': getattr(user, 'onboarding_complete', False),
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@mobile_api.route('/auth/login', methods=['POST'])
def login():
    """Validate email/password and return JWT + user object."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        from LoanMVP.models import User
        user = User.query.filter_by(email=email).first()
    except Exception as exc:
        current_app.logger.error('mobile login db error: %s', exc)
        return jsonify({'error': 'Database error'}), 500

    if user is None:
        return jsonify({'error': 'Invalid email or password'}), 401

    try:
        check_fn = getattr(user, 'check_password', None)
        if check_fn is not None:
            valid = check_fn(password)
        else:
            from werkzeug.security import check_password_hash
            stored = getattr(user, 'password_hash', None) or getattr(user, 'password', '')
            valid = check_password_hash(stored, password)
    except Exception as exc:
        current_app.logger.error('mobile login password check error: %s', exc)
        return jsonify({'error': 'Authentication error'}), 500

    if not valid:
        return jsonify({'error': 'Invalid email or password'}), 401

    token = _encode_token(user.id)
    return jsonify({'token': token, 'user': _serialize_user(user)}), 200


@mobile_api.route('/auth/me', methods=['GET'])
@require_auth
def me():
    """Return the authenticated user's profile."""
    return jsonify({'user': _serialize_user(request.current_user)}), 200


@mobile_api.route('/auth/refresh', methods=['POST'])
@require_auth
def refresh():
    """Issue a fresh token for the authenticated user."""
    token = _encode_token(request.current_user.id)
    return jsonify({'token': token}), 200


# ---------------------------------------------------------------------------
# Lending routes
# ---------------------------------------------------------------------------

def _serialize_loan(loan) -> dict:
    borrower = getattr(loan, 'borrower', None)
    borrower_name = ''
    if borrower is not None:
        b_first = getattr(borrower, 'first_name', '') or ''
        b_last = getattr(borrower, 'last_name', '') or ''
        borrower_name = f'{b_first} {b_last}'.strip()
    else:
        borrower_name = getattr(loan, 'borrower_name', '') or ''

    return {
        'id': getattr(loan, 'id', None),
        'borrower_name': borrower_name,
        'loan_amount': float(getattr(loan, 'loan_amount', 0) or 0),
        'loan_type': getattr(loan, 'loan_type', '') or '',
        'status': getattr(loan, 'status', '') or '',
        'ltv': float(getattr(loan, 'ltv', 0) or 0),
        'interest_rate': float(getattr(loan, 'interest_rate', 0) or 0),
        'property_address': getattr(loan, 'property_address', '') or '',
        'created_at': str(getattr(loan, 'created_at', '') or ''),
        'updated_at': str(getattr(loan, 'updated_at', '') or ''),
    }


@mobile_api.route('/lending/loans', methods=['GET'])
@require_auth
def list_loans():
    """Return loans filtered by the requesting user's role."""
    user = request.current_user
    role = getattr(user, 'role', 'borrower')

    try:
        from LoanMVP.models import Loan
    except ImportError:
        return jsonify({'loans': [], 'total': 0}), 200

    try:
        if role == 'borrower':
            borrower_id_col = getattr(Loan, 'borrower_id', None)
            if borrower_id_col is not None:
                loans = Loan.query.filter_by(borrower_id=user.id).all()
            else:
                loans = Loan.query.all()
        elif role in ('loan_officer', 'processor', 'underwriter', 'admin'):
            loans = Loan.query.all()
        else:
            loans = Loan.query.all()
    except Exception as exc:
        current_app.logger.error('list_loans error: %s', exc)
        return jsonify({'error': 'Could not retrieve loans'}), 500

    return jsonify({'loans': [_serialize_loan(l) for l in loans], 'total': len(loans)}), 200


@mobile_api.route('/lending/loans/<int:loan_id>', methods=['GET'])
@require_auth
def loan_detail(loan_id):
    try:
        from LoanMVP.models import Loan
    except ImportError:
        return jsonify({'error': 'Loan model not available'}), 404

    try:
        loan = Loan.query.get(loan_id)
    except Exception as exc:
        current_app.logger.error('loan_detail error: %s', exc)
        return jsonify({'error': 'Database error'}), 500

    if loan is None:
        return jsonify({'error': 'Loan not found'}), 404

    return jsonify({'loan': _serialize_loan(loan)}), 200


@mobile_api.route('/lending/pipeline/summary', methods=['GET'])
@require_auth
def pipeline_summary():
    try:
        from LoanMVP.models import Loan
        from sqlalchemy import func
        from LoanMVP.extensions import db
    except ImportError:
        return jsonify({'total': 0, 'active': 0, 'closed': 0, 'volume': 0.0}), 200

    try:
        total = Loan.query.count()
        active_statuses = ('submitted', 'processing', 'underwriting', 'approved', 'in_review')
        closed_statuses = ('closed', 'funded', 'denied', 'cancelled')
        active = Loan.query.filter(Loan.status.in_(active_statuses)).count()
        closed = Loan.query.filter(Loan.status.in_(closed_statuses)).count()
        volume_result = db.session.query(func.sum(Loan.loan_amount)).scalar()
        volume = float(volume_result or 0)
    except Exception as exc:
        current_app.logger.error('pipeline_summary error: %s', exc)
        return jsonify({'total': 0, 'active': 0, 'closed': 0, 'volume': 0.0}), 200

    return jsonify({'total': total, 'active': active, 'closed': closed, 'volume': volume}), 200


# ---------------------------------------------------------------------------
# Investor routes
# ---------------------------------------------------------------------------

def _serialize_deal(deal) -> dict:
    return {
        'id': getattr(deal, 'id', None),
        'name': getattr(deal, 'name', '') or getattr(deal, 'title', '') or '',
        'amount': float(getattr(deal, 'amount', 0) or getattr(deal, 'investment_amount', 0) or 0),
        'return_rate': float(getattr(deal, 'return_rate', 0) or getattr(deal, 'expected_return', 0) or 0),
        'status': getattr(deal, 'status', '') or '',
        'asset_class': getattr(deal, 'asset_class', '') or getattr(deal, 'deal_type', '') or '',
        'description': getattr(deal, 'description', '') or '',
        'created_at': str(getattr(deal, 'created_at', '') or ''),
    }


@mobile_api.route('/investor/dashboard', methods=['GET'])
@require_auth
def investor_dashboard():
    user = request.current_user

    try:
        from LoanMVP.models import Deal
        from sqlalchemy import func
        from LoanMVP.extensions import db
    except ImportError:
        return jsonify({'total_invested': 0.0, 'active_deals': 0, 'total_deals': 0, 'avg_return': 0.0}), 200

    try:
        investor_id_col = getattr(Deal, 'investor_id', None)
        if investor_id_col is not None:
            base_query = Deal.query.filter_by(investor_id=user.id)
        else:
            base_query = Deal.query

        total_deals = base_query.count()
        active_deals = base_query.filter(Deal.status.in_(['active', 'open', 'funded'])).count()
        total_invested_result = db.session.query(func.sum(Deal.amount)).filter(
            Deal.investor_id == user.id if investor_id_col is not None else True
        ).scalar()
        total_invested = float(total_invested_result or 0)
        avg_return_result = db.session.query(func.avg(Deal.return_rate)).filter(
            Deal.investor_id == user.id if investor_id_col is not None else True
        ).scalar()
        avg_return = float(avg_return_result or 0)
    except Exception as exc:
        current_app.logger.error('investor_dashboard error: %s', exc)
        return jsonify({'total_invested': 0.0, 'active_deals': 0, 'total_deals': 0, 'avg_return': 0.0}), 200

    return jsonify({
        'total_invested': total_invested,
        'active_deals': active_deals,
        'total_deals': total_deals,
        'avg_return': avg_return,
    }), 200


@mobile_api.route('/investor/deals', methods=['GET'])
@require_auth
def investor_deals():
    user = request.current_user

    try:
        from LoanMVP.models import Deal
    except ImportError:
        return jsonify({'deals': [], 'total': 0}), 200

    try:
        investor_id_col = getattr(Deal, 'investor_id', None)
        if investor_id_col is not None:
            deals = Deal.query.filter_by(investor_id=user.id).all()
        else:
            deals = Deal.query.all()
    except Exception as exc:
        current_app.logger.error('investor_deals error: %s', exc)
        return jsonify({'error': 'Could not retrieve deals'}), 500

    return jsonify({'deals': [_serialize_deal(d) for d in deals], 'total': len(deals)}), 200


@mobile_api.route('/investor/deals/<int:deal_id>', methods=['GET'])
@require_auth
def deal_detail(deal_id):
    try:
        from LoanMVP.models import Deal
    except ImportError:
        return jsonify({'error': 'Deal model not available'}), 404

    try:
        deal = Deal.query.get(deal_id)
    except Exception as exc:
        current_app.logger.error('deal_detail error: %s', exc)
        return jsonify({'error': 'Database error'}), 500

    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404

    return jsonify({'deal': _serialize_deal(deal)}), 200


# ---------------------------------------------------------------------------
# Partner routes
# ---------------------------------------------------------------------------

def _serialize_referral(referral) -> dict:
    return {
        'id': getattr(referral, 'id', None),
        'name': getattr(referral, 'name', '') or getattr(referral, 'referral_name', '') or '',
        'email': getattr(referral, 'email', '') or '',
        'status': getattr(referral, 'status', '') or '',
        'created_at': str(getattr(referral, 'created_at', '') or ''),
        'converted_at': str(getattr(referral, 'converted_at', '') or ''),
    }


@mobile_api.route('/partner/referrals', methods=['GET'])
@require_auth
def partner_referrals():
    user = request.current_user

    try:
        from LoanMVP.models import Referral
    except ImportError:
        return jsonify({'referrals': [], 'total': 0, 'pending': 0, 'converted': 0}), 200

    try:
        partner_id_col = getattr(Referral, 'partner_id', None)
        if partner_id_col is not None:
            referrals = Referral.query.filter_by(partner_id=user.id).all()
        else:
            referrals = Referral.query.all()
        pending = sum(1 for r in referrals if getattr(r, 'status', '') in ('pending', 'submitted', 'new'))
        converted = sum(1 for r in referrals if getattr(r, 'status', '') in ('converted', 'closed', 'funded'))
    except Exception as exc:
        current_app.logger.error('partner_referrals error: %s', exc)
        return jsonify({'referrals': [], 'total': 0, 'pending': 0, 'converted': 0}), 200

    return jsonify({
        'referrals': [_serialize_referral(r) for r in referrals],
        'total': len(referrals),
        'pending': pending,
        'converted': converted,
    }), 200


# ---------------------------------------------------------------------------
# Academy routes
# ---------------------------------------------------------------------------

def _serialize_course(course) -> dict:
    return {
        'id': getattr(course, 'id', None),
        'title': getattr(course, 'title', '') or '',
        'description': getattr(course, 'description', '') or '',
        'duration': getattr(course, 'duration', '') or '',
        'level': getattr(course, 'level', '') or getattr(course, 'difficulty', '') or 'Beginner',
        'category': getattr(course, 'category', '') or '',
        'thumbnail_url': getattr(course, 'thumbnail_url', '') or '',
        'is_published': getattr(course, 'is_published', True),
    }


def _serialize_progress(progress) -> dict:
    return {
        'id': getattr(progress, 'id', None),
        'course_id': getattr(progress, 'course_id', None),
        'completed': getattr(progress, 'completed', False),
        'percent_complete': float(getattr(progress, 'percent_complete', 0) or 0),
        'last_accessed': str(getattr(progress, 'last_accessed', '') or ''),
    }


@mobile_api.route('/academy/courses', methods=['GET'])
@require_auth
def list_courses():
    try:
        from LoanMVP.models import Course
    except ImportError:
        return jsonify({'courses': [], 'total': 0}), 200

    try:
        is_published_col = getattr(Course, 'is_published', None)
        if is_published_col is not None:
            courses = Course.query.filter_by(is_published=True).all()
        else:
            courses = Course.query.all()
    except Exception as exc:
        current_app.logger.error('list_courses error: %s', exc)
        return jsonify({'courses': [], 'total': 0}), 200

    return jsonify({'courses': [_serialize_course(c) for c in courses], 'total': len(courses)}), 200


@mobile_api.route('/academy/courses/<int:course_id>', methods=['GET'])
@require_auth
def course_detail(course_id):
    try:
        from LoanMVP.models import Course
    except ImportError:
        return jsonify({'error': 'Course model not available'}), 404

    try:
        course = Course.query.get(course_id)
    except Exception as exc:
        current_app.logger.error('course_detail error: %s', exc)
        return jsonify({'error': 'Database error'}), 500

    if course is None:
        return jsonify({'error': 'Course not found'}), 404

    return jsonify({'course': _serialize_course(course)}), 200


@mobile_api.route('/academy/progress', methods=['GET'])
@require_auth
def get_progress():
    user = request.current_user

    try:
        from LoanMVP.models import CourseProgress
    except ImportError:
        return jsonify({'progress': [], 'courses_completed': 0, 'completion_rate': 0.0}), 200

    try:
        user_id_col = getattr(CourseProgress, 'user_id', None)
        if user_id_col is not None:
            progress_list = CourseProgress.query.filter_by(user_id=user.id).all()
        else:
            progress_list = CourseProgress.query.all()

        courses_completed = sum(1 for p in progress_list if getattr(p, 'completed', False))
        total = len(progress_list)
        completion_rate = (courses_completed / total * 100) if total > 0 else 0.0
    except Exception as exc:
        current_app.logger.error('get_progress error: %s', exc)
        return jsonify({'progress': [], 'courses_completed': 0, 'completion_rate': 0.0}), 200

    return jsonify({
        'progress': [_serialize_progress(p) for p in progress_list],
        'courses_completed': courses_completed,
        'completion_rate': completion_rate,
    }), 200


@mobile_api.route('/academy/progress/<int:course_id>', methods=['POST'])
@require_auth
def update_progress(course_id):
    user = request.current_user
    data = request.get_json(silent=True) or {}
    percent_complete = float(data.get('percent_complete', 0) or 0)
    completed = bool(data.get('completed', percent_complete >= 100))

    try:
        from LoanMVP.models import CourseProgress
        from LoanMVP.extensions import db
        import datetime as dt
    except ImportError:
        return jsonify({'error': 'Progress model not available'}), 500

    try:
        user_id_col = getattr(CourseProgress, 'user_id', None)
        if user_id_col is not None:
            progress = CourseProgress.query.filter_by(user_id=user.id, course_id=course_id).first()
        else:
            progress = None

        if progress is None:
            progress = CourseProgress()
            if getattr(CourseProgress, 'user_id', None) is not None:
                progress.user_id = user.id
            if getattr(CourseProgress, 'course_id', None) is not None:
                progress.course_id = course_id
            db.session.add(progress)

        if getattr(CourseProgress, 'percent_complete', None) is not None:
            progress.percent_complete = percent_complete
        if getattr(CourseProgress, 'completed', None) is not None:
            progress.completed = completed
        if getattr(CourseProgress, 'last_accessed', None) is not None:
            progress.last_accessed = dt.datetime.utcnow()

        db.session.commit()
    except Exception as exc:
        current_app.logger.error('update_progress error: %s', exc)
        try:
            from LoanMVP.extensions import db
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'error': 'Could not update progress'}), 500

    return jsonify({'progress': _serialize_progress(progress)}), 200


# ---------------------------------------------------------------------------
# Ravlo AI chat route
# ---------------------------------------------------------------------------

@mobile_api.route('/ai/chat', methods=['POST'])
@require_auth
def ai_chat():
    """Chat with Ravlo AI, the intelligent lending assistant."""
    user = request.current_user
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        import anthropic
    except ImportError:
        return jsonify({'error': 'AI service not available'}), 500

    first_name = getattr(user, 'first_name', '') or 'there'
    role = getattr(user, 'role', 'borrower')

    system_prompt = (
        f"You are Ravlo AI, an intelligent assistant for the Ravlo lending and real estate platform. "
        f"You are speaking with {first_name}, whose role is {role}. "
        f"You specialize in real estate lending, loan origination, underwriting guidelines, "
        f"investment analysis, and mortgage products. "
        f"Be concise, professional, and friendly. "
        f"Always provide actionable, accurate information. "
        f"If you don't know something, say so clearly rather than guessing."
    )

    messages = []
    for entry in history:
        entry_role = entry.get('role', '')
        entry_content = entry.get('content', '')
        if entry_role in ('user', 'assistant') and entry_content:
            messages.append({'role': entry_role, 'content': entry_content})
    messages.append({'role': 'user', 'content': message})

    try:
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        response = client.messages.create(
            model='claude-opus-4-7',
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text if response.content else ''
    except Exception as exc:
        current_app.logger.error('ai_chat error: %s', exc)
        return jsonify({'error': 'Ravlo AI is temporarily unavailable. Please try again.'}), 500

    return jsonify({'reply': reply, 'role': 'assistant'}), 200


# ---------------------------------------------------------------------------
# Push notification registration
# ---------------------------------------------------------------------------

@mobile_api.route('/notifications/register', methods=['POST'])
@require_auth
def register_push_token(current_user=None):
    current_user = request.current_user
    body = request.get_json() or {}
    push_token = body.get('push_token', '')
    platform = body.get('platform', '')
    app_name = body.get('app', '')

    if not push_token:
        return jsonify({'error': 'push_token required'}), 400

    try:
        if hasattr(current_user, 'push_token'):
            current_user.push_token = push_token
            from LoanMVP.extensions import db
            db.session.commit()
        else:
            current_app.logger.info(
                f"Push token registered: user={current_user.id} app={app_name} platform={platform}"
            )
    except Exception as e:
        current_app.logger.error(f"Push token registration error: {e}")

    return jsonify({'success': True, 'message': 'Push token registered'})


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/documents/upload', methods=['POST'])
@require_auth
def upload_document(current_user=None):
    current_user = request.current_user
    if current_user.role not in LOAN_ROLES:
        return jsonify({'error': 'Forbidden'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    loan_id = request.form.get('loan_id')
    doc_type = request.form.get('doc_type', 'general')

    if not file.filename:
        return jsonify({'error': 'Empty file'}), 400

    try:
        import boto3
        from werkzeug.utils import secure_filename
        import uuid

        filename = secure_filename(file.filename)
        key = f"loan_docs/{loan_id}/{uuid.uuid4()}_{filename}"

        s3_bucket = os.environ.get('S3_BUCKET_NAME', os.environ.get('AWS_S3_BUCKET'))

        if s3_bucket:
            s3 = boto3.client('s3')
            s3.upload_fileobj(file, s3_bucket, key, ExtraArgs={'ContentType': file.content_type})
            file_url = f"https://{s3_bucket}.s3.amazonaws.com/{key}"
        else:
            upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'mobile', str(loan_id))
            os.makedirs(upload_dir, exist_ok=True)
            local_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{filename}")
            file.save(local_path)
            file_url = f"/uploads/mobile/{loan_id}/{os.path.basename(local_path)}"

        try:
            from LoanMVP.models.document_models import LoanDocument
            from LoanMVP.extensions import db
            doc = LoanDocument(
                loan_id=int(loan_id) if loan_id else None,
                uploaded_by=current_user.id,
                doc_type=doc_type,
                filename=filename,
                file_url=file_url,
                source='mobile',
            )
            db.session.add(doc)
            db.session.commit()
            doc_id = doc.id
        except Exception:
            doc_id = None

        return jsonify({
            'success': True,
            'document': {
                'id': doc_id,
                'filename': filename,
                'doc_type': doc_type,
                'file_url': file_url,
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Admin / Owner routes
# ---------------------------------------------------------------------------

@mobile_api.route('/admin/overview', methods=['GET'])
@require_auth
@require_admin
def admin_overview():
    """Platform-wide stats mirroring the executive dashboard."""
    import datetime as dt
    from LoanMVP.extensions import db
    from sqlalchemy import func

    user_stats = {'total': 0, 'active': 0, 'blocked': 0, 'recent_signups': 0, 'subscriptions': {}, 'roles': {}}
    try:
        from LoanMVP.models import User
        user_stats['total'] = User.query.count()
        user_stats['active'] = User.query.filter_by(is_active=True).count()
        user_stats['blocked'] = User.query.filter_by(is_blocked=True).count()
        thirty_days_ago = dt.datetime.utcnow() - dt.timedelta(days=30)
        user_stats['recent_signups'] = User.query.filter(User.created_at >= thirty_days_ago).count()
        for row in db.session.query(User.subscription, func.count(User.id)).group_by(User.subscription).all():
            user_stats['subscriptions'][row[0] or 'free'] = row[1]
        for row in db.session.query(User.role, func.count(User.id)).group_by(User.role).all():
            user_stats['roles'][row[0] or 'unknown'] = row[1]
    except Exception as exc:
        current_app.logger.error('admin_overview user stats: %s', exc)

    loan_stats = {'total': 0, 'active': 0, 'volume': 0.0}
    try:
        from LoanMVP.models import Loan
        loan_stats['total'] = Loan.query.count()
        loan_stats['active'] = Loan.query.filter(
            Loan.status.in_(('submitted', 'processing', 'underwriting', 'approved', 'in_review'))
        ).count()
        vol = db.session.query(func.sum(Loan.loan_amount)).scalar()
        loan_stats['volume'] = float(vol or 0)
    except Exception as exc:
        current_app.logger.error('admin_overview loan stats: %s', exc)

    company_count = 0
    try:
        from LoanMVP.models import Company
        company_count = Company.query.count()
    except Exception as exc:
        current_app.logger.error('admin_overview company stats: %s', exc)

    request_stats = {'pending': 0, 'approved': 0, 'total': 0}
    try:
        from LoanMVP.models import AccessRequest
        request_stats['total'] = AccessRequest.query.count()
        request_stats['pending'] = AccessRequest.query.filter_by(status='pending').count()
        request_stats['approved'] = AccessRequest.query.filter_by(status='approved').count()
    except Exception as exc:
        current_app.logger.error('admin_overview access request stats: %s', exc)

    pending_invites = 0
    try:
        from LoanMVP.models import UserInvite
        pending_invites = UserInvite.query.filter_by(status='pending').count()
    except Exception as exc:
        current_app.logger.error('admin_overview invite stats: %s', exc)

    doc_count = 0
    try:
        from LoanMVP.models.document_models import LoanDocument
        doc_count = LoanDocument.query.count()
    except Exception as exc:
        current_app.logger.error('admin_overview doc stats: %s', exc)

    return jsonify({
        'users': user_stats,
        'loans': loan_stats,
        'companies': company_count,
        'documents': doc_count,
        'access_requests': request_stats,
        'pending_invites': pending_invites,
    }), 200


@mobile_api.route('/admin/users', methods=['GET'])
@require_auth
@require_admin
def admin_users():
    """Paginated, searchable user list for admin/owner."""
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 25))))
    search = (request.args.get('search') or '').strip()
    role_filter = (request.args.get('role') or '').strip()

    try:
        from LoanMVP.models import User
        query = User.query
        if search:
            like = f'%{search}%'
            query = query.filter(
                (User.email.ilike(like)) |
                (User.first_name.ilike(like)) |
                (User.last_name.ilike(like))
            )
        if role_filter:
            query = query.filter_by(role=role_filter)

        total = query.count()
        users = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        def _s(u):
            first = getattr(u, 'first_name', '') or ''
            last = getattr(u, 'last_name', '') or ''
            return {
                'id': u.id,
                'full_name': f'{first} {last}'.strip() or u.email,
                'email': u.email,
                'role': getattr(u, 'role', '') or '',
                'subscription': getattr(u, 'subscription', '') or 'free',
                'is_active': getattr(u, 'is_active', True),
                'is_blocked': getattr(u, 'is_blocked', False),
                'created_at': str(getattr(u, 'created_at', '') or ''),
                'last_login': str(getattr(u, 'last_login', '') or ''),
                'onboarding_complete': getattr(u, 'onboarding_complete', False),
            }

        return jsonify({
            'users': [_s(u) for u in users],
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
        }), 200
    except Exception as exc:
        current_app.logger.error('admin_users error: %s', exc)
        return jsonify({'error': 'Could not retrieve users'}), 500


@mobile_api.route('/admin/activity', methods=['GET'])
@require_auth
@require_admin
def admin_activity():
    """Recent platform activity: signups, access requests, leads."""
    recent_users = []
    try:
        from LoanMVP.models import User
        for u in User.query.order_by(User.created_at.desc()).limit(10).all():
            first = getattr(u, 'first_name', '') or ''
            last = getattr(u, 'last_name', '') or ''
            recent_users.append({
                'id': u.id,
                'name': f'{first} {last}'.strip() or u.email,
                'email': u.email,
                'role': getattr(u, 'role', '') or '',
                'subscription': getattr(u, 'subscription', '') or 'free',
                'created_at': str(getattr(u, 'created_at', '') or ''),
            })
    except Exception as exc:
        current_app.logger.error('admin_activity users: %s', exc)

    recent_requests = []
    try:
        from LoanMVP.models import AccessRequest
        for r in AccessRequest.query.order_by(AccessRequest.created_at.desc()).limit(10).all():
            recent_requests.append({
                'id': r.id,
                'name': getattr(r, 'contact_name', '') or getattr(r, 'name', '') or '',
                'email': getattr(r, 'email', '') or '',
                'company': getattr(r, 'company_name', '') or '',
                'status': getattr(r, 'status', '') or '',
                'created_at': str(getattr(r, 'created_at', '') or ''),
            })
    except Exception as exc:
        current_app.logger.error('admin_activity requests: %s', exc)

    recent_leads = []
    try:
        from LoanMVP.models import Lead
        for lead in Lead.query.order_by(Lead.created_at.desc()).limit(5).all():
            recent_leads.append({
                'id': lead.id,
                'name': getattr(lead, 'name', '') or getattr(lead, 'full_name', '') or '',
                'email': getattr(lead, 'email', '') or '',
                'status': getattr(lead, 'status', '') or '',
                'created_at': str(getattr(lead, 'created_at', '') or ''),
            })
    except Exception as exc:
        current_app.logger.error('admin_activity leads: %s', exc)

    return jsonify({
        'recent_users': recent_users,
        'recent_requests': recent_requests,
        'recent_leads': recent_leads,
    }), 200


# ---------------------------------------------------------------------------
# Loan Officer / LO-role dashboard
# ---------------------------------------------------------------------------

LO_ROLES = ('loan_officer', 'processor', 'underwriter', 'admin', 'platform_admin',
             'master_admin', 'lending_admin', 'executive')


@mobile_api.route('/lending/dashboard', methods=['GET'])
@require_auth
def lo_dashboard():
    user = request.current_user
    uid = user.id
    today = datetime.datetime.utcnow().date()
    data = {}

    try:
        from LoanMVP.models.crm_models import Lead
        lead_counts = {}
        for status in ('New', 'Active', 'Contacted', 'Pending', 'Closed'):
            lead_counts[status.lower()] = Lead.query.filter_by(assigned_to=uid, status=status).count()
        lead_counts['total'] = Lead.query.filter_by(assigned_to=uid).count()
        data['leads'] = lead_counts
    except Exception as exc:
        current_app.logger.error('lo_dashboard leads: %s', exc)
        data['leads'] = {}

    try:
        from LoanMVP.models.crm_models import Task
        data['tasks'] = {
            'due_today': Task.query.filter_by(assigned_to=uid, completed=False).filter(Task.due_date == today).count(),
            'overdue': Task.query.filter_by(assigned_to=uid, completed=False).filter(Task.due_date < today).count(),
            'total_open': Task.query.filter_by(assigned_to=uid, completed=False).count(),
        }
    except Exception as exc:
        current_app.logger.error('lo_dashboard tasks: %s', exc)
        data['tasks'] = {}

    try:
        from LoanMVP.models.crm_models import Message
        data['messages'] = {
            'unread': Message.query.filter_by(receiver_id=uid, is_read=False).count(),
        }
    except Exception as exc:
        current_app.logger.error('lo_dashboard messages: %s', exc)
        data['messages'] = {}

    try:
        from LoanMVP.models.loan_models import LoanApplication
        loans = LoanApplication.query.filter_by(assigned_to=uid).all()
        volume = sum(getattr(l, 'loan_amount', 0) or 0 for l in loans)
        active = sum(1 for l in loans if getattr(l, 'status', '') in ('Active', 'Processing', 'In Review'))
        data['pipeline'] = {'total': len(loans), 'active': active, 'volume': volume}
    except Exception as exc:
        current_app.logger.error('lo_dashboard pipeline: %s', exc)
        data['pipeline'] = {}

    return jsonify(data), 200


# ---------------------------------------------------------------------------
# Leads endpoints
# ---------------------------------------------------------------------------

LEAD_STATUSES = ['New', 'Contacted', 'Active', 'Pending', 'Qualified', 'Closed', 'Unqualified']


@mobile_api.route('/lending/leads', methods=['GET'])
@require_auth
def lo_leads():
    user = request.current_user
    uid = user.id
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    try:
        from LoanMVP.models.crm_models import Lead
        q = Lead.query.filter_by(assigned_to=uid)
        if status_filter and status_filter != 'All':
            q = q.filter(Lead.status == status_filter)
        if search:
            like = f'%{search}%'
            q = q.filter(
                db.or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.phone.ilike(like))
            )
        q = q.order_by(Lead.created_at.desc())
        paginated = q.paginate(page=page, per_page=per_page, error_out=False)
        items = []
        for lead in paginated.items:
            items.append({
                'id': lead.id,
                'name': getattr(lead, 'name', '') or '',
                'email': getattr(lead, 'email', '') or '',
                'phone': getattr(lead, 'phone', '') or '',
                'status': getattr(lead, 'status', 'New') or 'New',
                'created_at': str(getattr(lead, 'created_at', '') or ''),
                'updated_at': str(getattr(lead, 'updated_at', '') or ''),
            })
        return jsonify({'leads': items, 'total': paginated.total, 'pages': paginated.pages, 'page': page}), 200
    except Exception as exc:
        current_app.logger.error('lo_leads: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/leads/<int:lead_id>', methods=['GET'])
@require_auth
def lo_lead_detail(lead_id):
    try:
        from LoanMVP.models.crm_models import Lead, CRMNote
        from LoanMVP.models.loan_models import BorrowerProfile
        lead = Lead.query.get_or_404(lead_id)
        notes = []
        for n in CRMNote.query.filter_by(lead_id=lead_id).order_by(CRMNote.created_at.desc()).limit(20).all():
            notes.append({
                'id': n.id,
                'content': n.content,
                'created_at': str(n.created_at),
                'user_id': n.user_id,
            })
        borrowers = []
        for b in getattr(lead, 'borrowers', []):
            borrowers.append({
                'id': b.id,
                'full_name': getattr(b, 'full_name', '') or '',
                'email': getattr(b, 'email', '') or '',
                'loan_type': getattr(b, 'loan_type', '') or '',
                'loan_amount': getattr(b, 'loan_amount', 0) or 0,
                'status': getattr(b, 'status', '') or '',
            })
        return jsonify({
            'id': lead.id,
            'name': getattr(lead, 'name', '') or '',
            'email': getattr(lead, 'email', '') or '',
            'phone': getattr(lead, 'phone', '') or '',
            'message': getattr(lead, 'message', '') or '',
            'status': getattr(lead, 'status', 'New') or 'New',
            'created_at': str(getattr(lead, 'created_at', '') or ''),
            'updated_at': str(getattr(lead, 'updated_at', '') or ''),
            'notes': notes,
            'borrowers': borrowers,
        }), 200
    except Exception as exc:
        current_app.logger.error('lo_lead_detail: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/leads/<int:lead_id>/status', methods=['POST'])
@require_auth
def lo_lead_status(lead_id):
    try:
        from LoanMVP.models.crm_models import Lead
        from LoanMVP.extensions import db as _db
        data = request.get_json(force=True) or {}
        new_status = data.get('status', '')
        if new_status not in LEAD_STATUSES:
            return jsonify({'error': 'Invalid status'}), 400
        lead = Lead.query.get_or_404(lead_id)
        lead.status = new_status
        _db.session.commit()
        return jsonify({'ok': True, 'status': new_status}), 200
    except Exception as exc:
        current_app.logger.error('lo_lead_status: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/leads/<int:lead_id>/note', methods=['POST'])
@require_auth
def lo_lead_note(lead_id):
    try:
        from LoanMVP.models.crm_models import CRMNote
        from LoanMVP.extensions import db as _db
        data = request.get_json(force=True) or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'error': 'Content required'}), 400
        note = CRMNote(lead_id=lead_id, user_id=request.current_user.id, content=content)
        _db.session.add(note)
        _db.session.commit()
        return jsonify({'ok': True, 'note': {'id': note.id, 'content': note.content, 'created_at': str(note.created_at)}}), 201
    except Exception as exc:
        current_app.logger.error('lo_lead_note: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Borrowers
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/borrowers', methods=['GET'])
@require_auth
def lo_borrowers():
    user = request.current_user
    uid = user.id
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()

    try:
        from LoanMVP.models.loan_models import BorrowerProfile
        q = BorrowerProfile.query.filter(
            db.or_(BorrowerProfile.assigned_to == uid, BorrowerProfile.assigned_officer_id == uid)
        )
        if search:
            like = f'%{search}%'
            q = q.filter(
                db.or_(BorrowerProfile.full_name.ilike(like), BorrowerProfile.email.ilike(like))
            )
        q = q.order_by(BorrowerProfile.id.desc())
        paginated = q.paginate(page=page, per_page=per_page, error_out=False)
        items = []
        for b in paginated.items:
            items.append({
                'id': b.id,
                'full_name': getattr(b, 'full_name', '') or '',
                'email': getattr(b, 'email', '') or '',
                'phone': getattr(b, 'phone', '') or '',
                'loan_type': getattr(b, 'loan_type', '') or '',
                'loan_amount': getattr(b, 'loan_amount', 0) or 0,
                'status': getattr(b, 'status', '') or '',
                'credit_score': getattr(b, 'credit_score', None),
            })
        return jsonify({'borrowers': items, 'total': paginated.total, 'pages': paginated.pages, 'page': page}), 200
    except Exception as exc:
        current_app.logger.error('lo_borrowers: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/tasks', methods=['GET'])
@require_auth
def lo_tasks():
    user = request.current_user
    uid = user.id
    today = datetime.datetime.utcnow().date()

    try:
        from LoanMVP.models.crm_models import Task
        tasks = Task.query.filter_by(assigned_to=uid, completed=False).order_by(Task.due_date.asc().nullslast()).all()
        overdue, due_today, upcoming = [], [], []
        for t in tasks:
            item = {
                'id': t.id,
                'title': getattr(t, 'title', '') or '',
                'description': getattr(t, 'description', '') or '',
                'due_date': str(t.due_date) if t.due_date else None,
                'priority': getattr(t, 'priority', 'Normal') or 'Normal',
                'status': getattr(t, 'status', 'Pending') or 'Pending',
            }
            if t.due_date is None:
                upcoming.append(item)
            elif t.due_date < today:
                overdue.append(item)
            elif t.due_date == today:
                due_today.append(item)
            else:
                upcoming.append(item)
        return jsonify({'overdue': overdue, 'due_today': due_today, 'upcoming': upcoming}), 200
    except Exception as exc:
        current_app.logger.error('lo_tasks: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/tasks/<int:task_id>/complete', methods=['POST'])
@require_auth
def lo_task_complete(task_id):
    try:
        from LoanMVP.models.crm_models import Task
        from LoanMVP.extensions import db as _db
        task = Task.query.get_or_404(task_id)
        task.completed = True
        task.status = 'Completed'
        _db.session.commit()
        return jsonify({'ok': True}), 200
    except Exception as exc:
        current_app.logger.error('lo_task_complete: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/messages', methods=['GET'])
@require_auth
def lo_messages():
    user = request.current_user
    uid = user.id

    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.models import User
        from sqlalchemy import func as sql_func

        all_msgs = Message.query.filter(
            db.or_(Message.sender_id == uid, Message.receiver_id == uid)
        ).order_by(Message.created_at.desc()).all()

        seen_partners = {}
        conversations = []
        for msg in all_msgs:
            partner_id = msg.receiver_id if msg.sender_id == uid else msg.sender_id
            if partner_id not in seen_partners:
                seen_partners[partner_id] = True
                partner = User.query.get(partner_id)
                unread = Message.query.filter_by(sender_id=partner_id, receiver_id=uid, is_read=False).count()
                first = getattr(partner, 'first_name', '') or ''
                last = getattr(partner, 'last_name', '') or ''
                conversations.append({
                    'partner_id': partner_id,
                    'partner_name': f'{first} {last}'.strip() or 'Unknown',
                    'partner_role': getattr(partner, 'role', '') or '',
                    'last_message': msg.content[:100],
                    'last_message_at': str(msg.created_at),
                    'unread': unread,
                    'is_mine': msg.sender_id == uid,
                })
        return jsonify({'conversations': conversations}), 200
    except Exception as exc:
        current_app.logger.error('lo_messages: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/messages/<int:other_user_id>/thread', methods=['GET'])
@require_auth
def lo_message_thread(other_user_id):
    user = request.current_user
    uid = user.id

    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.extensions import db as _db
        msgs = Message.query.filter(
            db.or_(
                db.and_(Message.sender_id == uid, Message.receiver_id == other_user_id),
                db.and_(Message.sender_id == other_user_id, Message.receiver_id == uid),
            )
        ).order_by(Message.created_at.asc()).all()

        for m in msgs:
            if m.receiver_id == uid and not m.is_read:
                m.is_read = True
        _db.session.commit()

        thread = []
        for m in msgs:
            thread.append({
                'id': m.id,
                'sender_id': m.sender_id,
                'is_mine': m.sender_id == uid,
                'content': m.content,
                'created_at': str(m.created_at),
                'is_read': m.is_read,
            })
        return jsonify({'thread': thread, 'other_user_id': other_user_id}), 200
    except Exception as exc:
        current_app.logger.error('lo_message_thread: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/messages/send', methods=['POST'])
@require_auth
def lo_message_send():
    user = request.current_user
    uid = user.id

    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.extensions import db as _db
        data = request.get_json(force=True) or {}
        receiver_id = data.get('receiver_id')
        content = (data.get('content') or '').strip()
        if not receiver_id or not content:
            return jsonify({'error': 'receiver_id and content required'}), 400
        msg = Message(
            sender_id=uid,
            receiver_id=int(receiver_id),
            content=content,
            sender_role=getattr(user, 'role', ''),
        )
        _db.session.add(msg)
        _db.session.commit()
        return jsonify({'ok': True, 'message': {'id': msg.id, 'content': msg.content, 'created_at': str(msg.created_at)}}), 201
    except Exception as exc:
        current_app.logger.error('lo_message_send: %s', exc)
        return jsonify({'error': str(exc)}), 500
