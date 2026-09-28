import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PortalConfig:
    enabled: bool
    origin: str
    secret: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    mail_from: str
    notification_secret: str
    server_id: int
    support_email: str
    terms_url: str
    privacy_url: str

    @classmethod
    def from_env(cls):
        origin = os.getenv("PORTAL_ORIGIN", "").rstrip("/")
        enabled = os.getenv("PORTAL_ENABLED", "false").lower() == "true"
        secret = os.getenv("PORTAL_SECRET", "")
        if enabled:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError("PORTAL_ORIGIN must be an HTTPS origin")
            if len(secret) < 32:
                raise ValueError("PORTAL_SECRET must have at least 32 characters")
        return cls(enabled, origin, secret,
                   os.getenv("PORTAL_SMTP_HOST", ""), int(os.getenv("PORTAL_SMTP_PORT", "465")),
                   os.getenv("PORTAL_SMTP_USER", ""), os.getenv("PORTAL_SMTP_PASSWORD", ""),
                   os.getenv("PORTAL_MAIL_FROM", ""), os.getenv("PORTAL_YOOMONEY_NOTIFICATION_SECRET", ""),
                   int(os.getenv("PORTAL_SERVER_ID", "1")), os.getenv("PORTAL_SUPPORT_EMAIL", ""),
                   os.getenv("PORTAL_TERMS_URL", ""), os.getenv("PORTAL_PRIVACY_URL", ""))

    @property
    def mail_ready(self):
        return bool(self.smtp_host and self.mail_from and self.smtp_user and self.smtp_password)
