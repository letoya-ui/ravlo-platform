# -*- coding: utf-8 -*-
import os, zipfile, subprocess, sys

# === AUTO-INSTALL REQUIRED PACKAGES ===
required = ['flask', 'flask-cors', 'flask-login']
for pkg in required:
    try:
        __import__(pkg.replace('-', '_'))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# === DEFINE PATHS ===
base_dir = r"C:\LoanMVP_Bundle\LoanMVP"
ext_dir = os.path.join(base_dir, "extensions")
os.makedirs(ext_dir, exist_ok=True)

zip_path = os.path.join(ext_dir, "LoanMVP_Part8_Full.zip")

# === CREATE TEMP STRUCTURE ===
temp_folder = os.path.join(ext_dir, "LoanMVP_Part8")
os.makedirs(temp_folder, exist_ok=True)

routes_dir = os.path.join(temp_folder, "routes")
templates_lo = os.path.join(temp_folder, "templates", "loan_officer")
templates_b = os.path.join(temp_folder, "templates", "borrower")
static_js = os.path.join(temp_folder, "static", "js")
utils_dir = os.path.join(temp_folder, "utils")

for folder in [routes_dir, templates_lo, templates_b, static_js, utils_dir]:
    os.makedirs(folder, exist_ok=True)

# === ROUTE FILE ===
quote_route = f'''from flask import Blueprint, jsonify, request, render_template
from flask_cors import cross_origin

quote_bp = Blueprint('quote_bp', __name__, url_prefix='/api/quote')

@quote_bp.route('/generate', methods=['POST'])
@cross_origin()
def generate_quote():
    data = request.get_json() or {{}}
    amount = float(data.get('amount', 250000))
    term = int(data.get('term', 30))
    rate = 6.5
    monthly = round((amount * (rate/100/12)) / (1 - (1 + rate/100/12)**(-term*12)), 2)
    return jsonify({{
        'loan_type': 'Commercial',
        'lender': 'CM Loan Services',
        'term': f"{{term}} years",
        'rate': rate,
        'monthly_payment': monthly
    }})

@quote_bp.route('/dashboard')
def quote_dashboard():
    return render_template('loan_officer/quote_engine.html', title='AI Quote Engine')
'''
with open(os.path.join(routes_dir, "quote_engine.py"), "w") as f:
    f.write(quote_route)

# === LOAN OFFICER TEMPLATE ===
quote_engine_html = """{% extends 'loan_officer/base.html' %}
{% block content %}
<div class='container mt-5'>
  <h2 class='mb-4'>AI Quote Generator</h2>
  <form id='quoteForm'>
    <div class='mb-3'>
      <label>Loan Amount ($)</label>
      <input type='number' class='form-control' name='amount' required>
    </div>
    <div class='mb-3'>
      <label>Term (years)</label>
      <input type='number' class='form-control' name='term' value='30' required>
    </div>
    <button type='submit' class='btn btn-primary'>Generate Quote</button>
  </form>
  <div id='quoteResult' class='mt-4'></div>
</div>
<script src='{{ url_for('static', filename='js/quote_engine.js') }}'></script>
{% endblock %}
"""
with open(os.path.join(templates_lo, "quote_engine.html"), "w") as f:
    f.write(quote_engine_html)

# === BORROWER TEMPLATE ===
borrower_html = """{% extends 'borrower/base.html' %}
{% block content %}
<div class='container mt-5'>
  <h2>Your Loan Quotes</h2>
  <p class='text-muted'>AI-generated based on your inputs.</p>
  <table class='table table-striped mt-4'>
    <thead><tr><th>Lender</th><th>Loan Type</th><th>Rate</th><th>Term</th><th>Monthly Payment</th></tr></thead>
    <tbody id='quoteList'>
      <tr><td colspan='5'>No quotes yet.</td></tr>
    </tbody>
  </table>
</div>
{% endblock %}
"""
with open(os.path.join(templates_b, "quotes.html"), "w") as f:
    f.write(borrower_html)

# === JAVASCRIPT ===
quote_js = """document.getElementById('quoteForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/quote/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  const q = await res.json();
  document.getElementById('quoteResult').innerHTML = `
    <div class='alert alert-info'>
      <strong>${q.lender}</strong><br>
      Type: ${q.loan_type}<br>
      Term: ${q.term}<br>
      Rate: ${q.rate}%<br>
      Payment: $${q.monthly_payment}
    </div>`;
});"""
with open(os.path.join(static_js, "quote_engine.js"), "w") as f:
    f.write(quote_js)

# === ZIP EVERYTHING ===
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(temp_folder):
        for file in files:
            filepath = os.path.join(root, file)
            zipf.write(filepath, os.path.relpath(filepath, temp_folder))

print(f"\n✅ Build complete! Package saved at:\n{zip_path}")
