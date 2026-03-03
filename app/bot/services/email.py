import logging

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """Simple email service via Resend API."""

    def __init__(self, api_key: str, from_email: str = "noreply@proxycraft.tech") -> None:
        self.api_key = api_key
        self.from_email = from_email
        logger.info("Email Service initialized.")

    async def send(self, to: str, subject: str, html: str) -> bool:
        """Send an email via Resend API.

        Args:
            to: Recipient email address.
            subject: Email subject.
            html: HTML body content.

        Returns:
            True if sent successfully, False otherwise.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(RESEND_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(f"Email sent to {to}: {subject}")
                return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
