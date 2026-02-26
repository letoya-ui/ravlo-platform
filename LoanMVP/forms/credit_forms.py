# LoanMVP/forms/credit.py
from flask_wtf import FlaskForm
from wtforms import IntegerField, SubmitField
from wtforms.validators import DataRequired

class CreditCheckForm(FlaskForm):
    borrower_id = IntegerField("Borrower ID", validators=[DataRequired()])
    submit = SubmitField("Run Credit Check")