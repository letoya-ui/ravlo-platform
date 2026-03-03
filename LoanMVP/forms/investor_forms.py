# LoanMVP/forms/investor_forms.py

# LoanMVP/forms/investor_profile_form.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField, IntegerField, DecimalField,   BooleanField, DateField, TextAreaField
)
from wtforms.validators import DataRequired, Optional, NumberRange,Email

class InvestorProfileForm(FlaskForm):
    # Required fields for creating a profile
    strategy = SelectField(
        "Primary Strategy",
        choices=[
            ("fix_and_flip", "Fix & Flip"),
            ("buy_and_hold", "Buy & Hold"),
            ("new_construction", "New Construction"),
            ("wholesale", "Wholesale"),
        ],
        validators=[DataRequired()],
    )

    experience_level = SelectField(
        "Experience Level",
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
        ],
        validators=[DataRequired()],
    )

    # Buy box
    target_markets = StringField("Target Markets", validators=[Optional()])
    property_types = StringField("Property Types", validators=[Optional()])
    min_price = IntegerField("Min Price", validators=[Optional(), NumberRange(min=0)])
    max_price = IntegerField("Max Price", validators=[Optional(), NumberRange(min=0)])
    min_sqft = IntegerField("Min Sq Ft", validators=[Optional(), NumberRange(min=0)])
    max_sqft = IntegerField("Max Sq Ft", validators=[Optional(), NumberRange(min=0)])

    # Capital & returns
    capital_available = DecimalField("Capital Available", validators=[Optional()])
    min_cash_on_cash = DecimalField("Min Cash-on-Cash Return", validators=[Optional()])
    min_roi = DecimalField("Min ROI", validators=[Optional()])
    timeline_days = IntegerField("Timeline (Days)", validators=[Optional()])

    # Risk
    risk_tolerance = SelectField(
        "Risk Tolerance",
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        validators=[Optional()],
    )

    notes = TextAreaField("Notes", validators=[Optional()])

    submit = SubmitField("Create Profile")

class InvestorSettingsForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    strategy = StringField("Investment Strategy", validators=[Optional()])

    current_password = PasswordField("Current Password", validators=[Optional()])
    new_password = PasswordField("New Password", validators=[Optional()])
    confirm_password = PasswordField("Confirm Password", validators=[Optional()])

    submit = SubmitField("Save Changes")
