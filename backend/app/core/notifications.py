import ipaddress
import logging
import httpx
import os
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

WEBHOOK_DOMAIN_ALLOWLIST = {
    "hooks.slack.com",
    "discord.com",
    "discordapp.com",
    "outlook.office.com",
    "outlook.office365.com",
}


def _is_safe_webhook_url(url: str) -> bool:
    """Validate webhook URL against SSRF attacks."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("https",):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    if any(hostname.endswith(f".{domain}") or hostname == domain for domain in WEBHOOK_DOMAIN_ALLOWLIST):
        return True

    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in resolved:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False

    return True


async def send_slack_alert(message: str, webhook_url: str) -> bool:
    """
    Send an alert message to a Slack or MS Teams webhook.
    """
    if not webhook_url:
        return False

    if not _is_safe_webhook_url(webhook_url):
        logger.warning("Blocked webhook request to disallowed URL: domain not in allowlist or resolves to private IP")
        return False

    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0")) as client:
            response = await client.post(
                webhook_url,
                json={"text": message},
                timeout=10.0
            )
            response.raise_for_status()
        logger.info("Slack alert sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False

async def send_whatsapp_alert(message: str, phone_number: str) -> bool:
    """
    Send a WhatsApp alert via Twilio API.
    Required Environment Variables:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_WHATSAPP_NUMBER (e.g., 'whatsapp:+14155238886')
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    
    if not all([account_sid, auth_token, from_number, phone_number]):
        logger.warning("Twilio credentials missing. Skipping WhatsApp alert.")
        return False
        
    # Ensure phone number is formatted for WhatsApp
    to_number = phone_number
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
        
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        # Twilio SDK is synchronous, but for alerting we can run it here
        # or wrap it in a threadpool if it becomes a bottleneck.
        msg = client.messages.create(
            from_=from_number,
            body=message,
            to=to_number
        )
        logger.info(f"WhatsApp alert sent successfully via Twilio (SID: {msg.sid}).")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp alert: {e}")
        return False
