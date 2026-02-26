from flask_mail import Message
from LoanMVP.app import mail

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

    mail.send(msg)
