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
    secret = os.environ.get('JWT_SECRET_KEY') or os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY (or SECRET_KEY) environment variable must be set. "
            "A hardcoded fallback is not permitted — mobile tokens would be forgeable."
        )
    return secret


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

    university_tier = getattr(user, 'university_tier', None)

    # Load course enrollments from unlock table (chosen course = first entry with no payment)
    chosen_course = None
    unlocked_courses: list[str] = []
    try:
        from LoanMVP.models.training_models import UserCourseUnlock
        unlocks = UserCourseUnlock.query.filter_by(user_id=getattr(user, 'id', None)).order_by(UserCourseUnlock.id).all()
        all_course_ids = [u.course_id for u in unlocks]
        # First unlock with no Stripe payment = the subscription-included chosen course
        for u in unlocks:
            if not u.stripe_payment_id:
                chosen_course = u.course_id
                break
        unlocked_courses = all_course_ids
    except Exception:
        pass

    # Fall back to legacy tier mapping if no unlock record exists
    if not chosen_course and university_tier:
        _TIER_TO_COURSE = {
            'lending': 'mortgage',
            'starter': 'residential',
            'pro': 'residential',
            'elite': 'residential',
        }
        chosen_course = _TIER_TO_COURSE.get(university_tier)

    return {
        'id': getattr(user, 'id', None),
        'email': getattr(user, 'email', ''),
        'first_name': first,
        'last_name': last,
        'full_name': f'{first} {last}'.strip(),
        'role': getattr(user, 'role', 'borrower'),
        'subscription': getattr(user, 'subscription', 'free'),
        'university_tier': university_tier,
        'chosen_course': chosen_course,
        'unlocked_courses': unlocked_courses,
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
    results = getattr(deal, 'results_json', None) or {}
    roi = getattr(deal, 'estimated_roi_percent', None)
    if roi is None and isinstance(results, dict):
        roi = results.get('roi_percent') or results.get('roi') or 0
    profit = getattr(deal, 'estimated_profit', None)
    if profit is None and isinstance(results, dict):
        profit = results.get('estimated_profit') or results.get('profit') or 0
    return {
        'id': getattr(deal, 'id', None),
        'title': getattr(deal, 'title', '') or getattr(deal, 'address', '') or 'Untitled Deal',
        'address': getattr(deal, 'address', '') or '',
        'city': getattr(deal, 'city', '') or '',
        'state': getattr(deal, 'state', '') or '',
        'strategy': getattr(deal, 'strategy', '') or '',
        'purchase_price': float(getattr(deal, 'purchase_price', 0) or 0),
        'arv': float(getattr(deal, 'arv', 0) or 0),
        'rehab_cost': float(getattr(deal, 'rehab_cost', 0) or 0),
        'estimated_rent': float(getattr(deal, 'estimated_rent', 0) or 0),
        'deal_score': getattr(deal, 'deal_score', None),
        'roi_percent': float(roi or 0),
        'estimated_profit': float(profit or 0),
        'status': getattr(deal, 'status', 'active') or 'active',
        'submitted_for_funding': getattr(deal, 'submitted_for_funding', False) or False,
        'reveal_is_public': getattr(deal, 'reveal_is_public', False) or False,
        'notes': getattr(deal, 'notes', '') or '',
        'created_at': str(getattr(deal, 'created_at', '') or ''),
        'updated_at': str(getattr(deal, 'updated_at', '') or ''),
    }


@mobile_api.route('/investor/dashboard', methods=['GET'])
@require_auth
def investor_dashboard():
    user = request.current_user

    try:
        from LoanMVP.models import Deal
        from sqlalchemy import func as sql_func
    except ImportError:
        return jsonify({'total_deals': 0, 'active_deals': 0, 'funded_deals': 0,
                        'avg_roi': 0.0, 'avg_deal_score': 0.0, 'recent_deals': []}), 200

    try:
        base = Deal.query.filter_by(user_id=user.id)
        total_deals = base.count()
        active_deals = base.filter(Deal.status == 'active').count()
        funded_deals = base.filter(Deal.submitted_for_funding == True).count()

        all_deals = base.order_by(Deal.created_at.desc()).all()
        scores = [d.deal_score for d in all_deals if d.deal_score is not None]
        rois = [d.estimated_roi_percent for d in all_deals if d.estimated_roi_percent != 0]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        avg_roi = round(sum(rois) / len(rois), 2) if rois else 0.0

        strategy_breakdown: dict = {}
        for d in all_deals:
            s = getattr(d, 'strategy', '') or 'Unknown'
            strategy_breakdown[s] = strategy_breakdown.get(s, 0) + 1

        recent = [_serialize_deal(d) for d in all_deals[:5]]
    except Exception as exc:
        current_app.logger.error('investor_dashboard error: %s', exc)
        return jsonify({'total_deals': 0, 'active_deals': 0, 'funded_deals': 0,
                        'avg_roi': 0.0, 'avg_deal_score': 0.0, 'recent_deals': []}), 200

    return jsonify({
        'total_deals': total_deals,
        'active_deals': active_deals,
        'funded_deals': funded_deals,
        'avg_roi': avg_roi,
        'avg_deal_score': avg_score,
        'strategy_breakdown': strategy_breakdown,
        'recent_deals': recent,
    }), 200


@mobile_api.route('/investor/deals', methods=['GET'])
@require_auth
def investor_deals():
    user = request.current_user
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    status_filter = request.args.get('status', '').strip()
    strategy_filter = request.args.get('strategy', '').strip()

    try:
        from LoanMVP.models import Deal
    except ImportError:
        return jsonify({'deals': [], 'total': 0}), 200

    try:
        q = Deal.query.filter_by(user_id=user.id)
        if status_filter and status_filter != 'All':
            q = q.filter(Deal.status == status_filter)
        if strategy_filter and strategy_filter != 'All':
            q = q.filter(Deal.strategy == strategy_filter)
        q = q.order_by(Deal.created_at.desc())
        paginated = q.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'deals': [_serialize_deal(d) for d in paginated.items],
                        'total': paginated.total, 'pages': paginated.pages}), 200
    except Exception as exc:
        current_app.logger.error('investor_deals error: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/investor/opportunities', methods=['GET'])
@require_auth
def investor_opportunities():
    try:
        from LoanMVP.models import Deal
        deals = Deal.query.filter_by(reveal_is_public=True).order_by(Deal.deal_score.desc().nullslast()).limit(20).all()
        return jsonify({'opportunities': [_serialize_deal(d) for d in deals]}), 200
    except Exception as exc:
        current_app.logger.error('investor_opportunities error: %s', exc)
        return jsonify({'opportunities': []}), 200


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
# Investor — portfolio & investments
# ---------------------------------------------------------------------------

@mobile_api.route('/investor/portfolio', methods=['GET'])
@require_auth
def investor_portfolio():
    """Return Investment records for the authenticated investor."""
    user = request.current_user
    try:
        from LoanMVP.models.investor_models import Investment, InvestorProfile
        profile = InvestorProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({'investments': [], 'stats': {}}), 200
        investments = Investment.query.filter_by(investor_profile_id=profile.id).order_by(Investment.created_at.desc()).all()

        def _ser(inv):
            profit = getattr(inv, 'projected_profit', None)
            roi = getattr(inv, 'projected_roi', None)
            return {
                'id': inv.id,
                'title': getattr(inv, 'title', '') or getattr(inv, 'property_address', '') or 'Untitled',
                'strategy': getattr(inv, 'strategy', '') or '',
                'address': getattr(inv, 'property_address', '') or '',
                'city': getattr(inv, 'city', '') or '',
                'state': getattr(inv, 'state', '') or '',
                'status': getattr(inv, 'status', 'pipeline') or 'pipeline',
                'stage': getattr(inv, 'stage', '') or '',
                'purchase_price': int(getattr(inv, 'purchase_price', 0) or 0),
                'rehab_budget': int(getattr(inv, 'rehab_budget', 0) or 0),
                'arv': int(getattr(inv, 'arv', 0) or 0),
                'monthly_rent': int(getattr(inv, 'monthly_rent', 0) or 0),
                'loan_amount': int(getattr(inv, 'loan_amount', 0) or 0),
                'projected_profit': int(profit or 0),
                'projected_roi': float(roi or 0),
                'notes': getattr(inv, 'notes', '') or '',
                'created_at': str(getattr(inv, 'created_at', '') or ''),
            }

        serialized = [_ser(i) for i in investments]

        total_invested = sum(i['purchase_price'] + i['rehab_budget'] for i in serialized)
        total_arv = sum(i['arv'] for i in serialized)
        total_profit = sum(i['projected_profit'] for i in serialized)
        by_status = {}
        by_strategy = {}
        for i in serialized:
            by_status[i['status']] = by_status.get(i['status'], 0) + 1
            if i['strategy']:
                by_strategy[i['strategy']] = by_strategy.get(i['strategy'], 0) + 1

        return jsonify({
            'investments': serialized,
            'stats': {
                'total': len(serialized),
                'total_invested': total_invested,
                'total_arv': total_arv,
                'total_profit': total_profit,
                'by_status': by_status,
                'by_strategy': by_strategy,
            }
        }), 200
    except Exception as exc:
        current_app.logger.error('investor_portfolio error: %s', exc)
        return jsonify({'investments': [], 'stats': {}}), 200


@mobile_api.route('/investor/funding-requests', methods=['GET'])
@require_auth
def list_funding_requests():
    user = request.current_user
    try:
        from LoanMVP.models.investor_models import FundingRequest
        from LoanMVP.models import Deal
        requests_q = FundingRequest.query.filter_by(investor_id=user.id).order_by(FundingRequest.created_at.desc()).all()

        def _ser(fr):
            deal = None
            try:
                deal = Deal.query.get(fr.deal_id)
            except Exception:
                pass
            return {
                'id': fr.id,
                'deal_id': fr.deal_id,
                'deal_title': (getattr(deal, 'title', '') or getattr(deal, 'address', '') or 'Deal') if deal else 'Deal',
                'requested_amount': float(fr.requested_amount or 0),
                'status': fr.status or 'submitted',
                'notes': fr.notes or '',
                'created_at': str(fr.created_at or ''),
                'updated_at': str(fr.updated_at or ''),
            }

        return jsonify({'requests': [_ser(r) for r in requests_q], 'total': len(requests_q)}), 200
    except Exception as exc:
        current_app.logger.error('list_funding_requests error: %s', exc)
        return jsonify({'requests': [], 'total': 0}), 200


@mobile_api.route('/investor/funding-requests', methods=['POST'])
@require_auth
def create_funding_request():
    user = request.current_user
    data = request.get_json(force=True) or {}
    deal_id = data.get('deal_id')
    requested_amount = data.get('requested_amount', 0)
    notes = data.get('notes', '')

    if not deal_id:
        return jsonify({'error': 'deal_id is required'}), 400

    try:
        from LoanMVP.models import Deal
        from LoanMVP.models.investor_models import FundingRequest
        deal = Deal.query.get(deal_id)
        if not deal or deal.user_id != user.id:
            return jsonify({'error': 'Deal not found'}), 404

        fr = FundingRequest(
            investor_id=user.id,
            deal_id=deal_id,
            requested_amount=float(requested_amount or 0),
            notes=notes,
            status='submitted',
        )
        db.session.add(fr)
        deal.submitted_for_funding = True
        db.session.commit()
        return jsonify({'id': fr.id, 'status': 'submitted'}), 201
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('create_funding_request error: %s', exc)
        return jsonify({'error': str(exc)}), 500


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
# Processor routes
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/processor/queue', methods=['GET'])
@require_auth
def processor_queue():
    user = request.current_user
    try:
        from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
        from LoanMVP.models.processor_model import ProcessorProfile
        profile = ProcessorProfile.query.filter_by(user_id=user.id).first()
        if profile:
            loans = LoanApplication.query.filter_by(processor_id=profile.id, is_active=True).order_by(LoanApplication.updated_at.desc()).all()
        else:
            loans = LoanApplication.query.filter(
                LoanApplication.status.in_(['processing', 'Processing', 'submitted', 'Submitted', 'in_review', 'In Review'])
            ).order_by(LoanApplication.updated_at.desc()).limit(50).all()

        def _ser(l):
            bp = None
            try: bp = l.borrower_profile
            except: pass
            return {
                'id': l.id,
                'borrower_name': (getattr(bp, 'full_name', '') or '') if bp else '',
                'amount': float(l.amount or 0),
                'loan_type': l.loan_type or '',
                'status': l.status or '',
                'milestone_stage': l.milestone_stage or '',
                'progress_percent': int(l.progress_percent or 0),
                'property_address': l.property_address or '',
                'risk_level': l.risk_level or 'Medium',
                'risk_score': float(l.risk_score or 0),
                'processor_notes': l.processor_notes or '',
                'updated_at': str(l.updated_at or ''),
                'created_at': str(l.created_at or ''),
            }
        return jsonify({'loans': [_ser(l) for l in loans], 'total': len(loans)}), 200
    except Exception as exc:
        current_app.logger.error('processor_queue: %s', exc)
        return jsonify({'loans': [], 'total': 0}), 200


@mobile_api.route('/lending/processor/conditions', methods=['GET'])
@require_auth
def processor_conditions():
    user = request.current_user
    try:
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        from LoanMVP.models.loan_models import LoanApplication
        from LoanMVP.models.processor_model import ProcessorProfile
        profile = ProcessorProfile.query.filter_by(user_id=user.id).first()
        status_filter = request.args.get('status', 'Open')

        if profile:
            loan_ids = [l.id for l in LoanApplication.query.filter_by(processor_id=profile.id, is_active=True).all()]
            if loan_ids:
                q = UnderwritingCondition.query.filter(
                    UnderwritingCondition.loan_id.in_(loan_ids)
                )
            else:
                q = UnderwritingCondition.query.filter_by(status='Open')
        else:
            q = UnderwritingCondition.query

        if status_filter and status_filter != 'All':
            q = q.filter_by(status=status_filter)
        conditions = q.order_by(UnderwritingCondition.created_at.desc()).limit(100).all()

        def _ser(c):
            loan_addr = ''
            try:
                loan = LoanApplication.query.get(c.loan_id)
                loan_addr = getattr(loan, 'property_address', '') or ''
            except: pass
            return {
                'id': c.id,
                'loan_id': c.loan_id,
                'loan_address': loan_addr,
                'condition_type': c.condition_type or '',
                'description': c.description or '',
                'severity': c.severity or 'Standard',
                'status': c.status or 'Open',
                'notes': c.notes or '',
                'requested_by': c.requested_by or '',
                'cleared_by': c.cleared_by or '',
                'created_at': str(c.created_at or ''),
                'cleared_at': str(c.cleared_at or ''),
            }
        return jsonify({'conditions': [_ser(c) for c in conditions], 'total': len(conditions)}), 200
    except Exception as exc:
        current_app.logger.error('processor_conditions: %s', exc)
        return jsonify({'conditions': [], 'total': 0}), 200


@mobile_api.route('/lending/processor/conditions/<int:condition_id>', methods=['POST'])
@require_auth
def update_condition(condition_id):
    user = request.current_user
    data = request.get_json(force=True) or {}
    new_status = data.get('status', 'Cleared')
    notes = data.get('notes', '')
    try:
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        cond = UnderwritingCondition.query.get(condition_id)
        if not cond:
            return jsonify({'error': 'Condition not found'}), 404
        cond.status = new_status
        if notes:
            cond.notes = notes
        if new_status == 'Cleared':
            from datetime import datetime
            cond.cleared_at = datetime.utcnow()
            cond.cleared_by = user.full_name or user.email or 'Processor'
        db.session.commit()
        return jsonify({'id': cond.id, 'status': cond.status}), 200
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('update_condition: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/processor/loan/<int:loan_id>', methods=['GET'])
@require_auth
def processor_loan_detail(loan_id):
    try:
        from LoanMVP.models.loan_models import LoanApplication
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        from LoanMVP.models.document_models import LoanDocument
        loan = LoanApplication.query.get(loan_id)
        if not loan:
            return jsonify({'error': 'Not found'}), 404
        bp = None
        try: bp = loan.borrower_profile
        except: pass
        docs = []
        try:
            docs = LoanDocument.query.filter_by(loan_application_id=loan_id).all()
        except: pass
        conditions = []
        try:
            conditions = UnderwritingCondition.query.filter_by(loan_id=loan_id).all()
        except: pass

        def _doc(d):
            return {
                'id': d.id,
                'filename': getattr(d, 'filename', '') or getattr(d, 'original_filename', '') or '',
                'doc_type': getattr(d, 'doc_type', '') or getattr(d, 'document_type', '') or '',
                'status': getattr(d, 'status', '') or '',
                'uploaded_at': str(getattr(d, 'uploaded_at', '') or getattr(d, 'created_at', '') or ''),
            }

        def _cond(c):
            return {
                'id': c.id,
                'condition_type': c.condition_type or '',
                'description': c.description or '',
                'severity': c.severity or 'Standard',
                'status': c.status or 'Open',
            }

        return jsonify({
            'loan': {
                'id': loan.id,
                'borrower_name': (getattr(bp, 'full_name', '') or '') if bp else '',
                'amount': float(loan.amount or 0),
                'loan_type': loan.loan_type or '',
                'status': loan.status or '',
                'milestone_stage': loan.milestone_stage or '',
                'progress_percent': int(loan.progress_percent or 0),
                'property_address': loan.property_address or '',
                'risk_level': loan.risk_level or 'Medium',
                'risk_score': float(loan.risk_score or 0),
                'ltv': float(loan.ltv or loan.ltv_ratio or 0),
                'rate': float(loan.rate or 0),
                'front_end_dti': float(loan.front_end_dti or 0),
                'back_end_dti': float(loan.back_end_dti or 0),
                'processor_notes': loan.processor_notes or '',
                'ai_summary': loan.ai_summary or '',
                'updated_at': str(loan.updated_at or ''),
                'created_at': str(loan.created_at or ''),
            },
            'documents': [_doc(d) for d in docs],
            'conditions': [_cond(c) for c in conditions],
        }), 200
    except Exception as exc:
        current_app.logger.error('processor_loan_detail: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Underwriter routes
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/underwriter/queue', methods=['GET'])
@require_auth
def underwriter_queue():
    user = request.current_user
    try:
        from LoanMVP.models.loan_models import LoanApplication
        from LoanMVP.models.underwriter_model import UnderwriterProfile
        profile = UnderwriterProfile.query.filter_by(user_id=user.id).first()
        if profile:
            loans = LoanApplication.query.filter_by(underwriter_id=profile.id, is_active=True).order_by(LoanApplication.updated_at.desc()).all()
        else:
            loans = LoanApplication.query.filter(
                LoanApplication.status.in_(['underwriting', 'Underwriting', 'in_review', 'In Review', 'conditionally_approved'])
            ).order_by(LoanApplication.risk_score.desc()).limit(50).all()

        def _ser(l):
            bp = None
            try: bp = l.borrower_profile
            except: pass
            return {
                'id': l.id,
                'borrower_name': (getattr(bp, 'full_name', '') or '') if bp else '',
                'amount': float(l.amount or 0),
                'loan_type': l.loan_type or '',
                'status': l.status or '',
                'milestone_stage': l.milestone_stage or '',
                'risk_level': l.risk_level or 'Medium',
                'risk_score': float(l.risk_score or 0),
                'ltv': float(l.ltv or l.ltv_ratio or 0),
                'rate': float(l.rate or 0),
                'front_end_dti': float(l.front_end_dti or 0),
                'back_end_dti': float(l.back_end_dti or 0),
                'property_address': l.property_address or '',
                'ai_summary': l.ai_summary or '',
                'decision_notes': l.decision_notes or '',
                'updated_at': str(l.updated_at or ''),
            }
        return jsonify({'loans': [_ser(l) for l in loans], 'total': len(loans)}), 200
    except Exception as exc:
        current_app.logger.error('underwriter_queue: %s', exc)
        return jsonify({'loans': [], 'total': 0}), 200


@mobile_api.route('/lending/underwriter/loan/<int:loan_id>', methods=['GET'])
@require_auth
def underwriter_loan_detail(loan_id):
    try:
        from LoanMVP.models.loan_models import LoanApplication
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        from LoanMVP.models.document_models import LoanDocument
        loan = LoanApplication.query.get(loan_id)
        if not loan:
            return jsonify({'error': 'Not found'}), 404
        bp = None
        try: bp = loan.borrower_profile
        except: pass
        conditions = []
        try:
            conditions = UnderwritingCondition.query.filter_by(loan_id=loan_id).all()
        except: pass
        open_conds = sum(1 for c in conditions if c.status == 'Open')
        cleared_conds = sum(1 for c in conditions if c.status == 'Cleared')

        return jsonify({
            'loan': {
                'id': loan.id,
                'borrower_name': (getattr(bp, 'full_name', '') or '') if bp else '',
                'amount': float(loan.amount or 0),
                'loan_type': loan.loan_type or '',
                'status': loan.status or '',
                'milestone_stage': loan.milestone_stage or '',
                'risk_level': loan.risk_level or 'Medium',
                'risk_score': float(loan.risk_score or 0),
                'ltv': float(loan.ltv or loan.ltv_ratio or 0),
                'rate': float(loan.rate or 0),
                'front_end_dti': float(loan.front_end_dti or 0),
                'back_end_dti': float(loan.back_end_dti or 0),
                'property_address': loan.property_address or '',
                'property_value': float(loan.property_value or 0),
                'ai_summary': loan.ai_summary or '',
                'decision_notes': loan.decision_notes or '',
                'processor_notes': loan.processor_notes or '',
                'open_conditions': open_conds,
                'cleared_conditions': cleared_conds,
                'total_conditions': len(conditions),
                'updated_at': str(loan.updated_at or ''),
                'created_at': str(loan.created_at or ''),
            },
            'conditions': [
                {
                    'id': c.id,
                    'condition_type': c.condition_type or '',
                    'description': c.description or '',
                    'severity': c.severity or 'Standard',
                    'status': c.status or 'Open',
                    'notes': c.notes or '',
                }
                for c in conditions
            ],
        }), 200
    except Exception as exc:
        current_app.logger.error('underwriter_loan_detail: %s', exc)
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/lending/underwriter/loan/<int:loan_id>/decision', methods=['POST'])
@require_auth
def underwriter_decision(loan_id):
    user = request.current_user
    data = request.get_json(force=True) or {}
    decision = data.get('decision', '')  # approved | denied | conditional | suspended
    notes = data.get('notes', '')
    new_status = {
        'approved': 'Approved',
        'denied': 'Denied',
        'conditional': 'Conditionally Approved',
        'suspended': 'Suspended',
    }.get(decision, decision)

    if not new_status:
        return jsonify({'error': 'decision is required'}), 400

    try:
        from LoanMVP.models.loan_models import LoanApplication
        from datetime import datetime
        loan = LoanApplication.query.get(loan_id)
        if not loan:
            return jsonify({'error': 'Not found'}), 404
        loan.status = new_status
        loan.decision_notes = notes
        loan.decision_date = datetime.utcnow()
        loan.milestone_stage = new_status
        db.session.commit()
        return jsonify({'id': loan_id, 'status': new_status}), 200
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('underwriter_decision: %s', exc)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Borrower routes
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/borrower/dashboard', methods=['GET'])
@require_auth
def borrower_dashboard():
    user = request.current_user
    try:
        from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        profile = BorrowerProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            return jsonify({'loans': [], 'open_conditions': 0, 'total_loans': 0}), 200
        loans = LoanApplication.query.filter_by(borrower_profile_id=profile.id, is_active=True).order_by(LoanApplication.updated_at.desc()).all()
        total_conds = 0
        for loan in loans:
            try:
                open_c = UnderwritingCondition.query.filter_by(loan_id=loan.id, status='Open').count()
                total_conds += open_c
            except: pass

        def _ser(l):
            return {
                'id': l.id,
                'amount': float(l.amount or 0),
                'loan_type': l.loan_type or '',
                'status': l.status or '',
                'milestone_stage': l.milestone_stage or '',
                'progress_percent': int(l.progress_percent or 0),
                'property_address': l.property_address or '',
                'rate': float(l.rate or 0),
                'term_months': int(l.term_months or 0),
                'updated_at': str(l.updated_at or ''),
            }
        return jsonify({
            'loans': [_ser(l) for l in loans],
            'total_loans': len(loans),
            'open_conditions': total_conds,
        }), 200
    except Exception as exc:
        current_app.logger.error('borrower_dashboard: %s', exc)
        return jsonify({'loans': [], 'open_conditions': 0, 'total_loans': 0}), 200


@mobile_api.route('/lending/borrower/loan/<int:loan_id>', methods=['GET'])
@require_auth
def borrower_loan_detail(loan_id):
    user = request.current_user
    try:
        from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
        from LoanMVP.models.underwriter_model import UnderwritingCondition
        from LoanMVP.models.document_models import LoanDocument
        profile = BorrowerProfile.query.filter_by(user_id=user.id).first()
        loan = LoanApplication.query.get(loan_id)
        if not loan:
            return jsonify({'error': 'Not found'}), 404
        if profile and loan.borrower_profile_id != profile.id:
            return jsonify({'error': 'Not authorized'}), 403

        conditions = []
        try:
            conditions = UnderwritingCondition.query.filter_by(loan_id=loan_id).all()
        except: pass
        docs = []
        try:
            docs = LoanDocument.query.filter_by(loan_application_id=loan_id).all()
        except: pass

        MILESTONES = [
            'Application Started', 'Documents Collected', 'Processing',
            'Underwriting', 'Conditionally Approved', 'Clear to Close', 'Funded'
        ]
        current_stage = loan.milestone_stage or 'Application Started'
        current_idx = next((i for i, m in enumerate(MILESTONES) if m.lower() == current_stage.lower()), 0)

        lo = None
        try:
            lop = loan.loan_officer
            if lop:
                lo = {
                    'name': getattr(lop, 'full_name', '') or '',
                    'email': getattr(lop, 'email', '') or '',
                    'phone': getattr(lop, 'phone', '') or '',
                }
        except: pass

        return jsonify({
            'loan': {
                'id': loan.id,
                'amount': float(loan.amount or 0),
                'loan_type': loan.loan_type or '',
                'status': loan.status or '',
                'milestone_stage': current_stage,
                'milestone_index': current_idx,
                'milestones': MILESTONES,
                'progress_percent': int(loan.progress_percent or 0),
                'property_address': loan.property_address or '',
                'property_value': float(loan.property_value or 0),
                'rate': float(loan.rate or 0),
                'term_months': int(loan.term_months or 0),
                'ltv': float(loan.ltv or loan.ltv_ratio or 0),
                'front_end_dti': float(loan.front_end_dti or 0),
                'back_end_dti': float(loan.back_end_dti or 0),
                'ai_summary': loan.ai_summary or '',
                'updated_at': str(loan.updated_at or ''),
                'created_at': str(loan.created_at or ''),
            },
            'loan_officer': lo,
            'open_conditions': sum(1 for c in conditions if c.status == 'Open'),
            'conditions': [
                {
                    'id': c.id,
                    'condition_type': c.condition_type or '',
                    'description': c.description or '',
                    'severity': c.severity or 'Standard',
                    'status': c.status or 'Open',
                }
                for c in conditions
            ],
            'documents': [
                {
                    'id': d.id,
                    'filename': getattr(d, 'filename', '') or '',
                    'doc_type': getattr(d, 'doc_type', '') or '',
                    'status': getattr(d, 'status', '') or '',
                    'uploaded_at': str(getattr(d, 'uploaded_at', '') or getattr(d, 'created_at', '') or ''),
                }
                for d in docs
            ],
        }), 200
    except Exception as exc:
        current_app.logger.error('borrower_loan_detail: %s', exc)
        return jsonify({'error': str(exc)}), 500


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


@mobile_api.route('/academy/lesson-progress', methods=['GET'])
@require_auth
def get_lesson_progress():
    user = request.current_user
    try:
        from LoanMVP.models.training_models import AcademyLessonProgress
        rows = AcademyLessonProgress.query.filter_by(user_id=user.id).all()
        return jsonify({
            'completed': [{'module_id': r.module_id, 'lesson_index': r.lesson_index} for r in rows]
        }), 200
    except Exception as exc:
        current_app.logger.error('get_lesson_progress: %s', exc)
        return jsonify({'completed': []}), 200


@mobile_api.route('/academy/lesson/complete', methods=['POST'])
@require_auth
def complete_lesson():
    user = request.current_user
    data = request.get_json(force=True) or {}
    module_id = data.get('module_id', '')
    lesson_index = data.get('lesson_index')
    undo = bool(data.get('undo', False))

    if not module_id or lesson_index is None:
        return jsonify({'error': 'module_id and lesson_index required'}), 400

    try:
        from LoanMVP.models.training_models import AcademyLessonProgress
        if undo:
            AcademyLessonProgress.query.filter_by(
                user_id=user.id, module_id=module_id, lesson_index=lesson_index
            ).delete()
            db.session.commit()
            return jsonify({'ok': True, 'completed': False}), 200

        existing = AcademyLessonProgress.query.filter_by(
            user_id=user.id, module_id=module_id, lesson_index=lesson_index
        ).first()
        if not existing:
            row = AcademyLessonProgress(user_id=user.id, module_id=module_id, lesson_index=lesson_index)
            db.session.add(row)
            db.session.commit()
        return jsonify({'ok': True, 'completed': True}), 200
    except Exception as exc:
        current_app.logger.error('complete_lesson: %s', exc)
        db.session.rollback()
        return jsonify({'error': str(exc)}), 500


VALID_COURSES = {
    'residential', 'commercial', 'mortgage', 'realtor_growth',
    'investing', 'deal_structuring', 'underwriting', 'construction',
}


@mobile_api.route('/academy/choose-course', methods=['POST'])
@require_auth
def choose_course():
    """Set the user's included course selection (can only be set once)."""
    user = request.current_user
    data = request.get_json(force=True) or {}
    course_id = (data.get('course_id') or '').strip()

    if course_id not in VALID_COURSES:
        return jsonify({'error': f'Invalid course. Must be one of: {", ".join(sorted(VALID_COURSES))}'}), 400

    # Check if user already has a chosen course (unlock with no payment)
    try:
        from LoanMVP.models.training_models import UserCourseUnlock
        existing_chosen = UserCourseUnlock.query.filter_by(
            user_id=user.id, stripe_payment_id=None
        ).first()
        if existing_chosen:
            return jsonify({'error': 'Course already chosen', 'chosen_course': existing_chosen.course_id}), 409
    except Exception as exc:
        current_app.logger.error('choose_course check error: %s', exc)

    try:
        from LoanMVP.models.training_models import UserCourseUnlock
        unlock = UserCourseUnlock(user_id=user.id, course_id=course_id, stripe_payment_id=None)
        db.session.add(unlock)
        db.session.commit()
        return jsonify({'ok': True, 'chosen_course': course_id, 'user': _serialize_user(user)}), 200
    except Exception as exc:
        current_app.logger.error('choose_course error: %s', exc)
        db.session.rollback()
        return jsonify({'error': 'Could not save course selection'}), 500


@mobile_api.route('/academy/lesson/score', methods=['POST'])
@require_auth
def record_lesson_score():
    """Record a quiz score for a lesson. Score must be >=70 to pass."""
    user = request.current_user
    data = request.get_json(force=True) or {}
    module_id = data.get('module_id', '')
    lesson_index = data.get('lesson_index')
    score = data.get('score')  # 0-100

    if not module_id or lesson_index is None or score is None:
        return jsonify({'error': 'module_id, lesson_index, and score required'}), 400

    score = max(0, min(100, int(score)))
    passed = score >= 70

    try:
        from LoanMVP.models.training_models import AcademyLessonScore
        existing = AcademyLessonScore.query.filter_by(
            user_id=user.id, module_id=module_id, lesson_index=lesson_index
        ).first()
        if existing:
            existing.score = max(existing.score, score)
            existing.passed = existing.score >= 70
            existing.attempts += 1
            existing.completed_at = db.func.now()
        else:
            row = AcademyLessonScore(
                user_id=user.id, module_id=module_id,
                lesson_index=lesson_index, score=score, passed=passed
            )
            db.session.add(row)
        db.session.commit()
        return jsonify({'ok': True, 'score': score, 'passed': passed}), 200
    except Exception as exc:
        current_app.logger.error('record_lesson_score: %s', exc)
        db.session.rollback()
        return jsonify({'error': str(exc)}), 500


@mobile_api.route('/academy/business-plan', methods=['POST'])
@require_auth
def academy_business_plan():
    user = request.current_user
    data = request.get_json(force=True) or {}
    answers = data.get('answers', {})
    tier = getattr(user, 'university_tier', None) or 'elite'

    prompt = f"""You are Ravlo Academy's business plan generator. The user is a real estate professional.

Their profile:
- Role: {answers.get('role', 'Real estate professional')}
- Primary goal: {answers.get('goal', 'Grow my business')}
- Main challenge: {answers.get('challenge', 'Finding leads')}
- Market/location: {answers.get('market', 'Not specified')}
- Experience level: {answers.get('experience', 'Not specified')}
- Academy tier: {tier}

Create a focused 90-day action plan with:
1. Clear business objective (1-2 sentences)
2. Three priority actions for the first 30 days
3. Three priority actions for days 31-60
4. Three priority actions for days 61-90
5. One key metric to track each month
6. One accountability step

Be specific, actionable, and tailored to their role and goal. Keep it concise and motivating."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        reply = message.content[0].text
        return jsonify({'plan': reply}), 200
    except Exception as exc:
        current_app.logger.error('academy_business_plan: %s', exc)
        return jsonify({'error': 'Could not generate plan. Please try again.'}), 500


@mobile_api.route('/academy/chat', methods=['POST'])
@require_auth
def academy_chat():
    """Academy AI Coach — real estate education context chat."""
    user = request.current_user
    data = request.get_json(force=True) or {}
    messages_in = data.get('messages', [])
    tier = data.get('tier') or getattr(user, 'university_tier', None) or 'starter'

    first_name = getattr(user, 'first_name', '') or 'there'
    system_prompt = (
        f"You are Ravlo AI Coach, an expert real estate educator inside the Ravlo Academy platform. "
        f"You are speaking with {first_name}, a {tier}-tier member. "
        f"Your expertise covers: residential and commercial real estate, mortgage lending, real estate investing, "
        f"BRRRR strategy, deal analysis, cap rates, DSCR, creative financing, syndication, "
        f"and real estate business growth strategies. "
        f"Give clear, educational, actionable answers. Use examples and numbers where helpful. "
        f"Be encouraging but professional. Keep responses focused and not too long unless detail is needed."
    )

    messages = [
        {'role': m['role'], 'content': m['content']}
        for m in messages_in
        if m.get('role') in ('user', 'assistant') and m.get('content')
    ]

    if not messages:
        return jsonify({'error': 'No messages provided'}), 400

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text if response.content else ''
        return jsonify({'reply': reply}), 200
    except Exception as exc:
        current_app.logger.error('academy_chat: %s', exc)
        return jsonify({'error': 'AI coach temporarily unavailable. Please try again.'}), 500


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
