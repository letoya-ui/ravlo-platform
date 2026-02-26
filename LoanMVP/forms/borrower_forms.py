from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, DecimalField,   BooleanField, DateField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange

class BorrowerProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])
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
    submit = SubmitField("Save Profile")

class PreapprovalForm(FlaskForm):
    # Business Info
    business_name = StringField("Business Name", validators=[DataRequired()])
    annual_revenue = DecimalField("Annual Revenue ($)", validators=[DataRequired(), NumberRange(min=0)])
    years_in_business = IntegerField("Years in Business", validators=[DataRequired(), NumberRange(min=0)])

    # Loan Request
    loan_amount = DecimalField("Loan Amount Requested ($)", validators=[DataRequired(), NumberRange(min=10000)])
    collateral = StringField("Collateral Offered", validators=[Optional(), Length(max=100)])
    property_address = StringField("Property Address (optional)", validators=[Optional(), Length(max=200)])

    # Personal Info for Soft Pull
    full_name = StringField("Full Legal Name", validators=[DataRequired()])
    ssn = StringField("SSN (last 4 OK for mock)", validators=[DataRequired(), Length(min=4, max=11)])
    dob = DateField("Date of Birth", validators=[DataRequired()], format="%Y-%m-%d")
    address = StringField("Home Address", validators=[DataRequired(), Length(max=200)])
    consent = BooleanField("I authorize a soft credit pull", validators=[DataRequired()])
    property_value = DecimalField("Property Value", validators=[DataRequired()])
    loan_amount = DecimalField("Requested Loan Amount", validators=[DataRequired()])
    loan_type = SelectField("Loan Type", choices=[
        ("rehab", "Rehab"),
        ("commercial", "Commercial"),
        ("residential", "Residential")
    ], validators=[DataRequired()])
    submit = SubmitField("Request Pre-Approval")

    


