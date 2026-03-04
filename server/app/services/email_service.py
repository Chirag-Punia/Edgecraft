import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def send_otp_email(email: str, code: str) -> None:
    """Send OTP email. For MVP, just log the code. Replace with real SMTP later."""
    logger.info(f"[EMAIL] OTP for {email}: {code}")
    # TODO: Implement real SMTP sending
    # import smtplib
    # from email.mime.text import MIMEText
    # msg = MIMEText(f"Your verification code is: {code}")
    # msg["Subject"] = "Bharat Seller OS - Email Verification"
    # msg["From"] = settings.FROM_EMAIL
    # msg["To"] = email
    # with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
    #     server.starttls()
    #     server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    #     server.send_message(msg)
