from flask import Blueprint, jsonify, request, render_template
from flask_cors import cross_origin

quote_bp = Blueprint('quote_bp', __name__, url_prefix='/api/quote')

@quote_bp.route('/generate', methods=['POST'])
@cross_origin()
def generate_quote():
    data = request.get_json() or {}
    amount = float(data.get('amount', 250000))
    term = int(data.get('term', 30))
    rate = 6.5
    monthly = round((amount * (rate/100/12)) / (1 - (1 + rate/100/12)**(-term*12)), 2)
    return jsonify({
        'loan_type': 'Commercial',
        'lender': 'CM Loan Services',
        'term': f"{term} years",
        'rate': rate,
        'monthly_payment': monthly
    })

@quote_bp.route('/dashboard')
def quote_dashboard():
    return render_template('loan_officer/quote_engine.html', title='AI Quote Engine')
