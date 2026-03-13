from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
from utils.logger import get_logger

logger = get_logger("email_sender")


class EmailSender:
    """Sends HTML emails via SMTP (Gmail)."""

    def send(self, html_content: str, subject: str,
             recipient: str | None = None) -> bool:
        """Send an HTML email."""
        recipient = recipient or config.EMAIL_RECIPIENT

        if not config.SMTP_USER or not config.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured. Skipping email send.")
            logger.info(f"Would have sent email to {recipient}: {subject}")
            return False

        if not recipient:
            logger.warning("No recipient configured. Skipping email send.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config.EMAIL_SENDER or config.SMTP_USER
        msg["To"] = recipient

        # Plain text fallback
        plain_text = (
            f"{subject}\n\n"
            "Bu email HTML formatındadır. "
            "Lütfen HTML destekleyen bir email istemcisi kullanın.\n\n"
            f"Dashboard: http://localhost:3000"
        )
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(msg["From"], [recipient], msg.as_string())

            logger.info(f"Email sent to {recipient}: {subject}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
