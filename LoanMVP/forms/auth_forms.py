# LoanMVP/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, DecimalField,   BooleanField, DateField, TextAreaField

from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional,  NumberRange


# ------------------------------
# 🔑 Login Form
# ------------------------------
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# ------------------------------
# 🔐 Request Reset Form
# ------------------------------
class ResetPasswordRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")

# ------------------------------
# 🔁 Reset Password Form
# ------------------------------
class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Update Password")


class RegisterForm(FlaskForm):
    username = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    role = SelectField("Role", choices=[
        ("investor", "Investor"),
        ("borrower", "Borrower"),
        ("loan_officer", "Loan Officer"),
        ("processor", "Processor"),
        ("underwriter", "Underwriter"),
        ("admin", "Admin"),
    ], default="investor")
    submit = SubmitField("Create Account")



