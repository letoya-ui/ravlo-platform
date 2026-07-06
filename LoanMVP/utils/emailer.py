from flask_mail import Message
from LoanMVP.app import mail
from LoanMVP.utils.safe_http import safe_call

def send_email_with_attachment(to, subject, html_body, file_path):
    msg = Message(
        subject=subject,
        recipients=[to],
        html=html_body
    )

    # attach file
    with open(file_path, "rb") as f:
        msg.attach(
            filename=file_path.split("/")[-1],
            content_type="application/pdf",
            data=f.read()
        )

    safe_call(mail.send, msg)


def send_email(to, subject, html_body, text_body=None):
    msg = Message(
        subject=subject,
        recipients=[to],
        html=html_body,
        body=text_body or "Please view this email in HTML format."
    )

    safe_call(mail.send, msg)