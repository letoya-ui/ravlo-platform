"""Mobile API Blueprint - JWT-authenticated endpoints for Ravlo mobile apps."""

import os
import jwt
import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from LoanMVP.extensions import csrf

mobile_api = Blueprint('mobile_api', __name__, url_prefix='/mobile')
csrf.exempt(mobile_api)

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
LO_ROLES = ('loan_officer', 'processor', 'underwriter')

def require_auth(f):
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
# Auth
# ---------------------------------------------------------------------------

@mobile_api.route('/auth/login', methods=['POST'])
def login():
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
    return jsonify({'user': _serialize_user(request.current_user)}), 200

@mobile_api.route('/auth/refresh', methods=['POST'])
@require_auth
def refresh():
    token = _encode_token(request.current_user.id)
    return jsonify({'token': token}), 200

# ---------------------------------------------------------------------------
# Loan Officer Dashboard (aggregated stats in one call)
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/dashboard', methods=['GET'])
@require_auth
def lending_dashboard():
    user = request.current_user
    import datetime as dt
    from LoanMVP.extensions import db

    lead_stats = {'total': 0, 'new': 0, 'active': 0, 'closed': 0}
    try:
        from LoanMVP.models.crm_models import Lead
        q = Lead.query.filter_by(assigned_to=user.id)
        lead_stats['total'] = q.count()
        lead_stats['new'] = q.filter(Lead.status.ilike('new')).count()
        lead_stats['active'] = q.filter(Lead.status.in_(['Active', 'In Progress', 'Contacted'])).count()
        lead_stats['closed'] = q.filter(Lead.status.in_(['Closed', 'Converted', 'Lost'])).count()
    except Exception as exc:
        current_app.logger.error('lending_dashboard leads: %s', exc)

    task_stats = {'pending': 0, 'due_today': 0, 'overdue': 0}
    try:
        from LoanMVP.models.crm_models import Task
        today = dt.datetime.utcnow().date()
        q = Task.query.filter_by(assigned_to=user.id, completed=False)
        task_stats['pending'] = q.count()
        task_stats['due_today'] = q.filter(Task.due_date == today).count()
        task_stats['overdue'] = q.filter(Task.due_date < today).count()
    except Exception as exc:
        current_app.logger.error('lending_dashboard tasks: %s', exc)

    unread_messages = 0
    try:
        from LoanMVP.models.crm_models import Message
        unread_messages = Message.query.filter_by(receiver_id=user.id, is_read=False).count()
    except Exception as exc:
        current_app.logger.error('lending_dashboard messages: %s', exc)

    pipeline = {'total': 0, 'active': 0, 'volume': 0.0}
    try:
        from LoanMVP.models import Loan
        from sqlalchemy import func
        pipeline['total'] = Loan.query.count()
        pipeline['active'] = Loan.query.filter(
            Loan.status.in_(('submitted', 'processing', 'underwriting', 'approved', 'in_review'))
        ).count()
        vol = db.session.query(func.sum(Loan.loan_amount)).scalar()
        pipeline['volume'] = float(vol or 0)
    except Exception as exc:
        current_app.logger.error('lending_dashboard pipeline: %s', exc)

    return jsonify({
        'leads': lead_stats,
        'tasks': task_stats,
        'unread_messages': unread_messages,
        'pipeline': pipeline,
    }), 200

# ---------------------------------------------------------------------------
# Loans
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
    user = request.current_user
    try:
        from LoanMVP.models import Loan
    except ImportError:
        return jsonify({'loans': [], 'total': 0}), 200
    try:
        if getattr(user, 'role', '') == 'borrower':
            borrower_id_col = getattr(Loan, 'borrower_id', None)
            loans = Loan.query.filter_by(borrower_id=user.id).all() if borrower_id_col is not None else Loan.query.all()
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
        total = Loan.query.count()
        active = Loan.query.filter(Loan.status.in_(('submitted', 'processing', 'underwriting', 'approved', 'in_review'))).count()
        closed = Loan.query.filter(Loan.status.in_(('closed', 'funded', 'denied', 'cancelled'))).count()
        volume = float(db.session.query(func.sum(Loan.loan_amount)).scalar() or 0)
    except Exception as exc:
        current_app.logger.error('pipeline_summary error: %s', exc)
        return jsonify({'total': 0, 'active': 0, 'closed': 0, 'volume': 0.0}), 200
    return jsonify({'total': total, 'active': active, 'closed': closed, 'volume': volume}), 200

# ---------------------------------------------------------------------------
# Leads (CRM)
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/leads', methods=['GET'])
@require_auth
def list_leads():
    user = request.current_user
    search = (request.args.get('search') or '').strip()
    status_filter = (request.args.get('status') or '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 25))))
    try:
        from LoanMVP.models.crm_models import Lead
        query = Lead.query.filter_by(assigned_to=user.id)
        if search:
            like = f'%{search}%'
            query = query.filter(
                (Lead.name.ilike(like)) | (Lead.email.ilike(like)) | (Lead.phone.ilike(like))
            )
        if status_filter and status_filter != 'All':
            query = query.filter(Lead.status.ilike(f'%{status_filter}%'))
        total = query.count()
        leads = query.order_by(Lead.updated_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        def _s(l):
            return {
                'id': l.id, 'name': l.name or '', 'email': l.email or '',
                'phone': l.phone or '', 'status': l.status or 'New',
                'message': (l.message or '')[:120],
                'created_at': str(l.created_at or ''), 'updated_at': str(l.updated_at or ''),
            }
        return jsonify({'leads': [_s(l) for l in leads], 'total': total, 'page': page,
                        'pages': (total + per_page - 1) // per_page}), 200
    except Exception as exc:
        current_app.logger.error('list_leads error: %s', exc)
        return jsonify({'leads': [], 'total': 0}), 200

@mobile_api.route('/lending/leads/<int:lead_id>', methods=['GET'])
@require_auth
def lead_detail_view(lead_id):
    try:
        from LoanMVP.models.crm_models import Lead
        lead = Lead.query.get(lead_id)
        if lead is None:
            return jsonify({'error': 'Lead not found'}), 404
        notes = []
        try:
            for n in (lead.notes or []):
                notes.append({'id': n.id, 'content': n.content, 'created_at': str(n.created_at or '')})
        except Exception:
            pass
        borrowers = []
        try:
            for b in (lead.borrowers or []):
                first = getattr(b, 'first_name', '') or ''
                last = getattr(b, 'last_name', '') or ''
                borrowers.append({'id': b.id, 'name': f'{first} {last}'.strip(), 'email': getattr(b, 'email', '') or ''})
        except Exception:
            pass
        return jsonify({'lead': {
            'id': lead.id, 'name': lead.name or '', 'email': lead.email or '',
            'phone': lead.phone or '', 'status': lead.status or 'New',
            'message': lead.message or '', 'created_at': str(lead.created_at or ''),
            'updated_at': str(lead.updated_at or ''), 'notes': notes, 'borrowers': borrowers,
        }}), 200
    except Exception as exc:
        current_app.logger.error('lead_detail error: %s', exc)
        return jsonify({'error': 'Could not retrieve lead'}), 500

@mobile_api.route('/lending/leads/<int:lead_id>/status', methods=['POST'])
@require_auth
def update_lead_status(lead_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    if not new_status:
        return jsonify({'error': 'Status is required'}), 400
    try:
        from LoanMVP.models.crm_models import Lead
        from LoanMVP.extensions import db
        lead = Lead.query.get(lead_id)
        if lead is None:
            return jsonify({'error': 'Lead not found'}), 404
        lead.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'status': new_status}), 200
    except Exception as exc:
        current_app.logger.error('update_lead_status error: %s', exc)
        return jsonify({'error': 'Could not update status'}), 500

@mobile_api.route('/lending/leads/<int:lead_id>/note', methods=['POST'])
@require_auth
def add_lead_note(lead_id):
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Note content is required'}), 400
    try:
        from LoanMVP.models.crm_models import CRMNote, Lead
        from LoanMVP.extensions import db
        if Lead.query.get(lead_id) is None:
            return jsonify({'error': 'Lead not found'}), 404
        note = CRMNote(lead_id=lead_id, user_id=request.current_user.id, content=content)
        db.session.add(note)
        db.session.commit()
        return jsonify({'success': True, 'note': {'id': note.id, 'content': note.content, 'created_at': str(note.created_at)}}), 201
    except Exception as exc:
        current_app.logger.error('add_lead_note error: %s', exc)
        return jsonify({'error': 'Could not add note'}), 500

# ---------------------------------------------------------------------------
# Borrowers
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/borrowers', methods=['GET'])
@require_auth
def list_borrowers():
    user = request.current_user
    search = (request.args.get('search') or '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 25))))
    try:
        from LoanMVP.models import BorrowerProfile
        query = BorrowerProfile.query
        if search:
            like = f'%{search}%'
            try:
                query = query.filter(
                    (BorrowerProfile.first_name.ilike(like)) |
                    (BorrowerProfile.last_name.ilike(like)) |
                    (BorrowerProfile.email.ilike(like))
                )
            except Exception:
                pass
        total = query.count()
        borrowers = query.order_by(BorrowerProfile.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
        def _s(b):
            first = getattr(b, 'first_name', '') or ''
            last = getattr(b, 'last_name', '') or ''
            loan_status = ''
            try:
                apps = list(getattr(b, 'loan_applications', None) or [])
                if apps:
                    loan_status = getattr(sorted(apps, key=lambda x: getattr(x, 'created_at', None) or datetime.datetime.min, reverse=True)[0], 'status', '') or ''
            except Exception:
                pass
            return {
                'id': b.id,
                'full_name': f'{first} {last}'.strip() or getattr(b, 'email', '') or f'Borrower {b.id}',
                'email': getattr(b, 'email', '') or '',
                'phone': getattr(b, 'phone', '') or '',
                'loan_amount': float(getattr(b, 'loan_amount', 0) or 0),
                'loan_status': loan_status,
                'property_type': getattr(b, 'property_type', '') or '',
                'created_at': str(getattr(b, 'created_at', '') or ''),
            }
        return jsonify({'borrowers': [_s(b) for b in borrowers], 'total': total, 'page': page,
                        'pages': (total + per_page - 1) // per_page}), 200
    except Exception as exc:
        current_app.logger.error('list_borrowers error: %s', exc)
        return jsonify({'borrowers': [], 'total': 0}), 200

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/tasks', methods=['GET'])
@require_auth
def list_tasks():
    user = request.current_user
    show_completed = request.args.get('completed', 'false').lower() == 'true'
    try:
        from LoanMVP.models.crm_models import Task
        import datetime as dt
        today = dt.datetime.utcnow().date()
        tasks = Task.query.filter_by(assigned_to=user.id, completed=show_completed)\
            .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
        def _s(t):
            due = getattr(t, 'due_date', None)
            return {
                'id': t.id, 'title': t.title or '', 'description': t.description or '',
                'status': t.status or 'Pending', 'priority': t.priority or 'Normal',
                'completed': bool(t.completed),
                'due_date': str(due) if due else None,
                'is_overdue': bool(due and not t.completed and due < today),
                'loan_id': t.loan_id, 'created_at': str(t.created_at or ''),
            }
        return jsonify({'tasks': [_s(t) for t in tasks], 'total': len(tasks)}), 200
    except Exception as exc:
        current_app.logger.error('list_tasks error: %s', exc)
        return jsonify({'tasks': [], 'total': 0}), 200

@mobile_api.route('/lending/tasks/<int:task_id>/complete', methods=['POST'])
@require_auth
def complete_task(task_id):
    try:
        from LoanMVP.models.crm_models import Task
        from LoanMVP.extensions import db
        task = Task.query.get(task_id)
        if task is None:
            return jsonify({'error': 'Task not found'}), 404
        task.completed = True
        task.status = 'Completed'
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as exc:
        current_app.logger.error('complete_task error: %s', exc)
        return jsonify({'error': 'Could not complete task'}), 500

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@mobile_api.route('/lending/messages', methods=['GET'])
@require_auth
def list_messages():
    user = request.current_user
    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.models import User
        from sqlalchemy import func
        from LoanMVP.extensions import db
        sent = Message.query.filter_by(sender_id=user.id).all()
        recv = Message.query.filter_by(receiver_id=user.id).all()
        convos = {}
        for m in sent + recv:
            other_id = m.receiver_id if m.sender_id == user.id else m.sender_id
            if other_id not in convos or (m.created_at and convos[other_id]['_dt'] and m.created_at > convos[other_id]['_dt']):
                other = User.query.get(other_id)
                first = getattr(other, 'first_name', '') or '' if other else ''
                last = getattr(other, 'last_name', '') or '' if other else ''
                convos[other_id] = {
                    'user_id': other_id,
                    'name': f'{first} {last}'.strip() or (getattr(other, 'email', '') if other else f'User {other_id}'),
                    'role': getattr(other, 'role', '') or '' if other else '',
                    'last_message': (m.content or '')[:80],
                    'last_at': str(m.created_at or ''),
                    'unread': 0,
                    '_dt': m.created_at,
                }
        for sid, cnt in db.session.query(Message.sender_id, func.count(Message.id))\
                .filter_by(receiver_id=user.id, is_read=False).group_by(Message.sender_id).all():
            if sid in convos:
                convos[sid]['unread'] = cnt
        result = sorted([{k: v for k, v in c.items() if k != '_dt'} for c in convos.values()],
                        key=lambda x: x['last_at'], reverse=True)
        return jsonify({'conversations': result, 'total': len(result)}), 200
    except Exception as exc:
        current_app.logger.error('list_messages error: %s', exc)
        return jsonify({'conversations': [], 'total': 0}), 200

@mobile_api.route('/lending/messages/<int:other_user_id>/thread', methods=['GET'])
@require_auth
def message_thread(other_user_id):
    user = request.current_user
    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.extensions import db
        from sqlalchemy import or_, and_
        messages = Message.query.filter(
            or_(
                and_(Message.sender_id == user.id, Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id, Message.receiver_id == user.id)
            )
        ).order_by(Message.created_at.asc()).all()
        for m in messages:
            if m.receiver_id == user.id and not m.is_read:
                m.is_read = True
        db.session.commit()
        def _s(m):
            return {
                'id': m.id, 'content': m.content or '',
                'sender_id': m.sender_id, 'is_mine': m.sender_id == user.id,
                'is_read': m.is_read, 'created_at': str(m.created_at or ''),
            }
        return jsonify({'messages': [_s(m) for m in messages]}), 200
    except Exception as exc:
        current_app.logger.error('message_thread error: %s', exc)
        return jsonify({'messages': []}), 200

@mobile_api.route('/lending/messages/send', methods=['POST'])
@require_auth
def send_message():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    receiver_id = data.get('receiver_id')
    content = (data.get('content') or '').strip()
    if not receiver_id or not content:
        return jsonify({'error': 'receiver_id and content are required'}), 400
    try:
        from LoanMVP.models.crm_models import Message
        from LoanMVP.extensions import db
        msg = Message(sender_id=user.id, receiver_id=int(receiver_id), content=content,
                      sender_role=getattr(user, 'role', ''))
        db.session.add(msg)
        db.session.commit()
        return jsonify({'success': True, 'message': msg.to_dict()}), 201
    except Exception as exc:
        current_app.logger.error('send_message error: %s', exc)
        return jsonify({'error': 'Could not send message'}), 500

# ---------------------------------------------------------------------------
# Investor
# ---------------------------------------------------------------------------

def _serialize_deal(deal) -> dict:
    return {
        'id': getattr(deal, 'id', None),
        'name': getattr(deal, 'title', '') or getattr(deal, 'name', '') or getattr(deal, 'address', '') or '',
        'amount': float(getattr(deal, 'purchase_price', 0) or 0),
        'arv': float(getattr(deal, 'arv', 0) or 0),
        'rehab_cost': float(getattr(deal, 'rehab_cost', 0) or 0),
        'status': getattr(deal, 'status', '') or '',
        'strategy': getattr(deal, 'strategy', '') or '',
        'address': getattr(deal, 'address', '') or '',
        'deal_score': getattr(deal, 'deal_score', None),
        'created_at': str(getattr(deal, 'created_at', '') or ''),
    }

@mobile_api.route('/investor/dashboard', methods=['GET'])
@require_auth
def investor_dashboard():
    user = request.current_user
    try:
        from LoanMVP.models.borrowers import Deal
        from sqlalchemy import func
        from LoanMVP.extensions import db
        q = Deal.query.filter_by(user_id=user.id)
        total_deals = q.count()
        active_deals = q.filter(Deal.status.in_(['active', 'open'])).count()
        vol = db.session.query(func.sum(Deal.purchase_price)).filter_by(user_id=user.id).scalar()
    except Exception as exc:
        current_app.logger.error('investor_dashboard error: %s', exc)
        total_deals, active_deals, vol = 0, 0, 0
    return jsonify({'total_deals': total_deals, 'active_deals': active_deals,
                    'total_invested': float(vol or 0)}), 200

@mobile_api.route('/investor/deals', methods=['GET'])
@require_auth
def investor_deals():
    user = request.current_user
    try:
        from LoanMVP.models.borrowers import Deal
        deals = Deal.query.filter_by(user_id=user.id).order_by(Deal.created_at.desc()).all()
        return jsonify({'deals': [_serialize_deal(d) for d in deals], 'total': len(deals)}), 200
    except Exception as exc:
        current_app.logger.error('investor_deals error: %s', exc)
        return jsonify({'deals': [], 'total': 0}), 200

@mobile_api.route('/investor/deals/<int:deal_id>', methods=['GET'])
@require_auth
def deal_detail(deal_id):
    try:
        from LoanMVP.models.borrowers import Deal
        deal = Deal.query.get(deal_id)
    except Exception as exc:
        current_app.logger.error('deal_detail error: %s', exc)
        return jsonify({'error': 'Database error'}), 500
    if deal is None:
        return jsonify({'error': 'Deal not found'}), 404
    return jsonify({'deal': _serialize_deal(deal)}), 200

# ---------------------------------------------------------------------------
# Partner
# ---------------------------------------------------------------------------

@mobile_api.route('/partner/referrals', methods=['GET'])
@require_auth
def partner_referrals():
    return jsonify({'referrals': [], 'total': 0, 'pending': 0, 'converted': 0}), 200

# ---------------------------------------------------------------------------
# Academy
# ---------------------------------------------------------------------------

@mobile_api.route('/academy/courses', methods=['GET'])
@require_auth
def list_courses():
    try:
        from LoanMVP.models import Course
        courses = Course.query.filter_by(is_published=True).all() if getattr(Course, 'is_published', None) is not None else Course.query.all()
        def _s(c):
            return {'id': c.id, 'title': getattr(c,'title','') or '', 'description': getattr(c,'description','') or '',
                    'level': getattr(c,'level','') or 'Beginner', 'category': getattr(c,'category','') or ''}
        return jsonify({'courses': [_s(c) for c in courses], 'total': len(courses)}), 200
    except Exception:
        return jsonify({'courses': [], 'total': 0}), 200

@mobile_api.route('/academy/progress', methods=['GET'])
@require_auth
def get_progress():
    user = request.current_user
    try:
        from LoanMVP.models import CourseProgress
        progress_list = CourseProgress.query.filter_by(user_id=user.id).all()
        completed = sum(1 for p in progress_list if getattr(p, 'completed', False))
        total = len(progress_list)
        def _s(p):
            return {'id': p.id, 'course_id': p.course_id, 'completed': p.completed,
                    'percent_complete': float(getattr(p,'percent_complete',0) or 0)}
        return jsonify({'progress': [_s(p) for p in progress_list],
                        'courses_completed': completed, 'completion_rate': (completed/total*100) if total else 0.0}), 200
    except Exception:
        return jsonify({'progress': [], 'courses_completed': 0, 'completion_rate': 0.0}), 200

# ---------------------------------------------------------------------------
# Ravlo AI
# ---------------------------------------------------------------------------

@mobile_api.route('/ai/chat', methods=['POST'])
@require_auth
def ai_chat():
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
    system_prompt = (
        f"You are Ravlo AI, an intelligent assistant for the Ravlo lending and real estate platform. "
        f"You are speaking with {getattr(user,'first_name','') or 'there'}, whose role is {getattr(user,'role','borrower')}. "
        f"Specialize in real estate lending, loan origination, underwriting, investment analysis, and mortgage products. "
        f"Be concise, professional, and friendly."
    )
    msgs = []
    for e in history:
        if e.get('role') in ('user', 'assistant') and e.get('content'):
            msgs.append({'role': e['role'], 'content': e['content']})
    msgs.append({'role': 'user', 'content': message})
    try:
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        response = client.messages.create(model='claude-opus-4-7', max_tokens=1024, system=system_prompt, messages=msgs)
        reply = response.content[0].text if response.content else ''
    except Exception as exc:
        current_app.logger.error('ai_chat error: %s', exc)
        return jsonify({'error': 'Ravlo AI is temporarily unavailable.'}), 500
    return jsonify({'reply': reply, 'role': 'assistant'}), 200

# ---------------------------------------------------------------------------
# Notifications / Documents
# ---------------------------------------------------------------------------

@mobile_api.route('/notifications/register', methods=['POST'])
@require_auth
def register_push_token():
    body = request.get_json() or {}
    push_token = body.get('push_token', '')
    if not push_token:
        return jsonify({'error': 'push_token required'}), 400
    try:
        user = request.current_user
        if hasattr(user, 'push_token'):
            user.push_token = push_token
            from LoanMVP.extensions import db
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f'Push token error: {e}')
    return jsonify({'success': True})

@mobile_api.route('/lending/documents/upload', methods=['POST'])
@require_auth
def upload_document():
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
        from werkzeug.utils import secure_filename
        import uuid
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'mobile', str(loan_id))
        os.makedirs(upload_dir, exist_ok=True)
        local_path = os.path.join(upload_dir, f'{uuid.uuid4()}_{filename}')
        file.save(local_path)
        return jsonify({'success': True, 'document': {'filename': filename, 'doc_type': doc_type}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------------------------
# Admin / Owner
# ---------------------------------------------------------------------------

@mobile_api.route('/admin/overview', methods=['GET'])
@require_auth
@require_admin
def admin_overview():
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
        loan_stats['active'] = Loan.query.filter(Loan.status.in_(('submitted','processing','underwriting','approved','in_review'))).count()
        loan_stats['volume'] = float(db.session.query(func.sum(Loan.loan_amount)).scalar() or 0)
    except Exception as exc:
        current_app.logger.error('admin_overview loan stats: %s', exc)

    company_count = 0
    try:
        from LoanMVP.models import Company
        company_count = Company.query.count()
    except Exception as exc:
        current_app.logger.error('admin_overview company: %s', exc)

    request_stats = {'pending': 0, 'approved': 0, 'total': 0}
    try:
        from LoanMVP.models import AccessRequest
        request_stats['total'] = AccessRequest.query.count()
        request_stats['pending'] = AccessRequest.query.filter_by(status='pending').count()
        request_stats['approved'] = AccessRequest.query.filter_by(status='approved').count()
    except Exception as exc:
        current_app.logger.error('admin_overview requests: %s', exc)

    pending_invites = 0
    try:
        from LoanMVP.models import UserInvite
        pending_invites = UserInvite.query.filter_by(status='pending').count()
    except Exception as exc:
        current_app.logger.error('admin_overview invites: %s', exc)

    doc_count = 0
    try:
        from LoanMVP.models.document_models import LoanDocument
        doc_count = LoanDocument.query.count()
    except Exception as exc:
        current_app.logger.error('admin_overview docs: %s', exc)

    return jsonify({'users': user_stats, 'loans': loan_stats, 'companies': company_count,
                    'documents': doc_count, 'access_requests': request_stats,
                    'pending_invites': pending_invites}), 200

@mobile_api.route('/admin/users', methods=['GET'])
@require_auth
@require_admin
def admin_users():
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 25))))
    search = (request.args.get('search') or '').strip()
    role_filter = (request.args.get('role') or '').strip()
    try:
        from LoanMVP.models import User
        query = User.query
        if search:
            like = f'%{search}%'
            query = query.filter((User.email.ilike(like))|(User.first_name.ilike(like))|(User.last_name.ilike(like)))
        if role_filter:
            query = query.filter_by(role=role_filter)
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
        def _s(u):
            first = getattr(u,'first_name','') or ''; last = getattr(u,'last_name','') or ''
            return {'id': u.id, 'full_name': f'{first} {last}'.strip() or u.email, 'email': u.email,
                    'role': getattr(u,'role','') or '', 'subscription': getattr(u,'subscription','') or 'free',
                    'is_active': getattr(u,'is_active',True), 'is_blocked': getattr(u,'is_blocked',False),
                    'created_at': str(getattr(u,'created_at','') or ''), 'last_login': str(getattr(u,'last_login','') or ''),
                    'onboarding_complete': getattr(u,'onboarding_complete',False)}
        return jsonify({'users': [_s(u) for u in users], 'total': total, 'page': page,
                        'per_page': per_page, 'pages': (total+per_page-1)//per_page}), 200
    except Exception as exc:
        current_app.logger.error('admin_users error: %s', exc)
        return jsonify({'error': 'Could not retrieve users'}), 500

@mobile_api.route('/admin/activity', methods=['GET'])
@require_auth
@require_admin
def admin_activity():
    recent_users = []
    try:
        from LoanMVP.models import User
        for u in User.query.order_by(User.created_at.desc()).limit(10).all():
            first = getattr(u,'first_name','') or ''; last = getattr(u,'last_name','') or ''
            recent_users.append({'id': u.id, 'name': f'{first} {last}'.strip() or u.email, 'email': u.email,
                                  'role': getattr(u,'role','') or '', 'subscription': getattr(u,'subscription','') or 'free',
                                  'created_at': str(getattr(u,'created_at','') or '')})
    except Exception as exc:
        current_app.logger.error('admin_activity users: %s', exc)

    recent_requests = []
    try:
        from LoanMVP.models import AccessRequest
        for r in AccessRequest.query.order_by(AccessRequest.created_at.desc()).limit(10).all():
            recent_requests.append({'id': r.id, 'name': getattr(r,'contact_name','') or '', 'email': getattr(r,'email','') or '',
                                     'company': getattr(r,'company_name','') or '', 'status': getattr(r,'status','') or '',
                                     'created_at': str(getattr(r,'created_at','') or '')})
    except Exception as exc:
        current_app.logger.error('admin_activity requests: %s', exc)

    recent_leads = []
    try:
        from LoanMVP.models.crm_models import Lead
        for l in Lead.query.order_by(Lead.created_at.desc()).limit(5).all():
            recent_leads.append({'id': l.id, 'name': l.name or '', 'email': l.email or '',
                                  'status': l.status or '', 'created_at': str(l.created_at or '')})
    except Exception as exc:
        current_app.logger.error('admin_activity leads: %s', exc)

    return jsonify({'recent_users': recent_users, 'recent_requests': recent_requests, 'recent_leads': recent_leads}), 200
