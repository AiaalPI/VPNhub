"""Shared subscription metadata for website and Telegram exports."""
import base64

from bot.services.subscription_usage_service import SubscriptionUsage

SUBSCRIPTION_PROFILE_TITLE = '☀️ KYNVPN ✅ Active'


def subscription_profile_headers(*, user_id=0, key_id=0, expire_ts: int,
                                 content_disposition: str,
                                 usage: SubscriptionUsage | None = None) -> dict[str, str]:
    title = base64.b64encode(SUBSCRIPTION_PROFILE_TITLE.encode()).decode('ascii')
    headers = {'Cache-Control': 'no-store', 'Content-Disposition': content_disposition,
               'profile-title': f'base64:{title}', 'profile-update-interval': '1',
               'Referrer-Policy': 'no-referrer'}
    if usage is not None:
        headers['subscription-userinfo'] = (
            f'upload={usage.upload}; download={usage.download}; total={usage.total}; '
            f'expire={max(int(expire_ts or 0), 0)}')
    return headers
