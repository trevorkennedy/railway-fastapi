from os import getenv

from mailersend import emails


def send_email(subject: str, message: str):
    mail_body = {}

    mail_from = {
        "name": getenv('MAILER_FROM_NAME'),
        "email": getenv('MAILER_FROM'),
    }

    recipients = [
        {
            "email": getenv('MAILER_TO'),
        }
    ]

    mailer = emails.NewEmail(getenv("MAILER_KEY"))
    mailer.set_mail_from(mail_from, mail_body)
    mailer.set_reply_to(mail_from, mail_body)
    mailer.set_mail_to(recipients, mail_body)
    mailer.set_subject(subject, mail_body)
    mailer.set_html_content(message, mail_body)
    return mailer.send(mail_body)
