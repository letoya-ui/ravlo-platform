# LoanMVP/forms/investor_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Optional

class InvestorSettingsForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    strategy = StringField("Investment Strategy", validators=[Optional()])

    current_password = PasswordField("Current Password", validators=[Optional()])
    new_password = PasswordField("New Password", validators=[Optional()])
    confirm_password = PasswordField("Confirm Password", validators=[Optional()])

    submit = SubmitField("Save Changes")
