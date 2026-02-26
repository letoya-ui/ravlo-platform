from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Optional, Length

# 🧠 AI Intake Prompt Form
class AIIntakePromptForm(FlaskForm):
    borrower_id = StringField("Borrower ID", validators=[DataRequired()])
    context = TextAreaField("Borrower Context", validators=[DataRequired(), Length(max=5000)])
    submit = SubmitField("Generate AI Summary")

# 💬 AI Chat Prompt Form
class AIChatForm(FlaskForm):
    question = TextAreaField("Ask a Question", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Send")

# 🧾 AI Campaign Generator
class AICampaignForm(FlaskForm):
    audience = SelectField("Audience", choices=[
        ("first_time_buyers", "First-Time Buyers"),
        ("refinance_candidates", "Refinance Candidates"),
        ("self_employed", "Self-Employed Borrowers"),
        ("high_credit", "High Credit Score")
    ])
    tone = SelectField("Tone", choices=[
        ("friendly", "Friendly"),
        ("professional", "Professional"),
        ("urgent", "Urgent"),
        ("casual", "Casual")
    ])
    goal = StringField("Campaign Goal", validators=[DataRequired(), Length(max=120)])
    submit = SubmitField("Generate Campaign")

class AIIntakeForm(FlaskForm):
    """
    Used on: /loan_officer/ai-intake/<borrower_id>
    Purpose: Triggers AI summarization for a borrower intake.
    """
    notes = TextAreaField(
        "Officer Notes (optional)",
        validators=[Optional(), Length(max=2000)],
        render_kw={"placeholder": "Add context for the AI summary..."}
    )
    submit = SubmitField("🧠 Generate AI Summary")


class AIIntakeReviewForm(FlaskForm):
    """
    Used on: /loan_officer/ai-intake-review/<intake_id>
    Purpose: Loan officer review and annotate the AI summary.
    """
    status = SelectField(
        "Status",
        choices=[
            ("pending", "Pending"),
            ("reviewed", "Reviewed"),
            ("approved", "Approved"),
            ("flagged", "Flagged for Follow-Up")
        ],
        validators=[DataRequired()]
    )

    reviewer_notes = TextAreaField(
        "Reviewer Notes",
        validators=[Optional(), Length(max=2000)],
        render_kw={
            "placeholder": "Enter comments, corrections, or next steps for this AI summary..."
        }
    )

    submit = SubmitField("💾 Save Review")