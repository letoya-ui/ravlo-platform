from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DecimalField, IntegerField,
    SelectField, SubmitField, BooleanField, FileField
)
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange

# 📋 Borrower Intake
class BorrowerIntakeForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    annual_income = DecimalField("Annual Income ($)", validators=[Optional()])
    credit_score = IntegerField("Credit Score", validators=[Optional(), NumberRange(min=300, max=850)])
    employment_status = SelectField("Employment Status", choices=[
        ("Employed", "Employed"),
        ("Self-Employed", "Self-Employed"),
        ("Unemployed", "Unemployed"),
        ("Retired", "Retired"),
        ("Other", "Other")
    ])
    submit = SubmitField("Create Borrower")

# 📋 Borrower Search
class BorrowerSearchForm(FlaskForm):
    name = StringField("Name", validators=[Optional()])
    email = StringField("Email", validators=[Optional()])
    phone = StringField("Phone", validators=[Optional()])
    loan_status = SelectField("Loan Status", choices=[
        ("", "Any"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ])
    submit = SubmitField("Search")

# 📋 Loan Edit
class LoanEditForm(FlaskForm):
    loan_type = SelectField("Loan Type", choices=[
        ("Purchase", "Purchase"),
        ("Refinance", "Refinance"),
        ("HELOC", "HELOC"),
        ("Other", "Other")
    ])
    loan_amount = DecimalField("Loan Amount", validators=[DataRequired()])
    status = SelectField("Status", choices=[
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Update Loan")

# 📋 Quote Generation
class QuoteForm(FlaskForm):
    rate = DecimalField("Interest Rate (%)", validators=[DataRequired()])
    term_months = IntegerField("Term (Months)", validators=[DataRequired()])
    monthly_payment = DecimalField("Monthly Payment ($)", validators=[DataRequired()])
    submit = SubmitField("Generate Quote")

# 📋 Quote Plan
class QuotePlanForm(FlaskForm):
    title = StringField("Plan Title", validators=[DataRequired()])
    notes = TextAreaField("Loan Officer Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save Quote Plan")

# 📋 Upload Center
class UploadForm(FlaskForm):
    file = FileField("Upload File", validators=[DataRequired()])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    loan_id = SelectField("Related Loan", coerce=int, validators=[Optional()])
    submit = SubmitField("Upload")

# 📋 Follow-Up
class FollowUpForm(FlaskForm):
    description = StringField("Next Step", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Add Follow-Up")

# 📋 CRM Note
class CRMNoteForm(FlaskForm):
    content = TextAreaField("Note", validators=[DataRequired(), Length(max=2000)])
    is_private = BooleanField("Private Note")
    submit = SubmitField("Save Note")

# 📋 Campaign Creation
class CampaignForm(FlaskForm):
    name = StringField("Campaign Name", validators=[DataRequired(), Length(max=100)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Launch Campaign")

# 📋 Task Management
class TaskForm(FlaskForm):
    description = StringField("Task", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Add Task")

class GenerateQuoteForm(FlaskForm):
    borrower_name = StringField("Borrower Name", validators=[DataRequired()])
    loan_type = SelectField("Loan Type", choices=[
        ("commercial", "Commercial Loan"),
        ("residential", "Residential Loan"),
        ("bridge", "Bridge Loan"),
        ("construction", "Construction Loan"),
    ], validators=[DataRequired()])
    loan_amount = DecimalField("Loan Amount ($)", validators=[DataRequired(), NumberRange(min=10000)])
    interest_rate = DecimalField("Interest Rate (%)", validators=[DataRequired(), NumberRange(min=0.1, max=25)])
    term_months = IntegerField("Term (Months)", validators=[DataRequired(), NumberRange(min=6, max=480)])
    notes = StringField("Notes")
    submit = SubmitField("Generate Quote")