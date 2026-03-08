# LoanMVP/forms/investor_forms.py

# LoanMVP/forms/investor_profile_form.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField, IntegerField, DecimalField,   BooleanField, DateField, TextAreaField
)
from wtforms.validators import  DataRequired, Optional, Length, Email, NumberRange



class InvestorProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional()])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    city = StringField("City", validators=[Optional(), Length(max=100)])
    state = StringField("State", validators=[Optional(), Length(max=50)])
    zip_code = StringField("Zip Code", validators=[Optional(), Length(max=10)])
    employment_status = SelectField("Employment Status", choices=[
        ("Employed", "Employed"),
        ("Self-Employed", "Self-Employed"),
        ("Unemployed", "Unemployed"),
        ("Retired", "Retired"),
        ("Other", "Other")
    ], validators=[Optional()])
    annual_income = DecimalField("Annual Income ($)", validators=[Optional()])
    credit_score = IntegerField("Credit Score", validators=[Optional()])
    strategy = SelectField(
        "Investment Strategy",
        choices=[
            ("fix_and_flip", "Fix & Flip"),
            ("buy_and_hold", "Buy & Hold"),
            ("new_construction", "New Construction"),
            ("wholesale", "Wholesale"),
        ],
        validators=[Optional()],
    )

    experience_level = SelectField(
        "Experience Level",
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
        ],
        validators=[Optional()],
    )

    target_markets = StringField("Target Markets", validators=[Optional()])
    property_types = StringField("Property Types", validators=[Optional()])

    min_price = IntegerField("Min Price", validators=[Optional()])
    max_price = IntegerField("Max Price", validators=[Optional()])
    min_sqft = IntegerField("Min Sq Ft", validators=[Optional()])
    max_sqft = IntegerField("Max Sq Ft", validators=[Optional()])

    capital_available = IntegerField("Capital Available", validators=[Optional()])
    min_cash_on_cash = DecimalField("Min Cash-on-Cash Return", validators=[Optional()])
    min_roi = DecimalField("Min ROI", validators=[Optional()])
    timeline_days = IntegerField("Timeline (Days)", validators=[Optional()])

    risk_tolerance = SelectField(
        "Risk Tolerance",
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        validators=[Optional()],
    )

    submit = SubmitField("Create Profile")

class InvestorSettingsForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])

    current_password = PasswordField("Current Password", validators=[Optional()])
    new_password = PasswordField("New Password", validators=[Optional()])
    confirm_password = PasswordField("Confirm Password", validators=[Optional()])

    submit = SubmitField("Save Changes")

class CapitalApplicationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    loan_type = SelectField(
        "Loan Type",
        choices=[
            ("Investor Capital", "Investor Capital"),
            ("Fix & Flip", "Fix & Flip"),
            ("Bridge Loan", "Bridge Loan"),
            ("Rental Loan", "Rental Loan"),
            ("New Construction", "New Construction"),
        ],
        validators=[DataRequired()],
        default="Investor Capital"
    )

    project_address = StringField("Project Address", validators=[DataRequired(), Length(max=255)])
    project_description = TextAreaField("Project Description", validators=[Optional(), Length(max=2000)])

    amount = DecimalField("Requested Amount", validators=[DataRequired(), NumberRange(min=1)])
    property_value = DecimalField("Property Value", validators=[Optional(), NumberRange(min=0)])

    preferred_loan_officer_id = SelectField(
        "Preferred Loan Officer (Optional)",
        choices=[],
        validators=[Optional()],
        coerce=int,
        default=0
    )

    submit = SubmitField("Submit Application")