from urllib.parse import quote_plus


def build_hiddify_android_deeplink(subscription_link: str) -> str:
    """Build Android deep-link for direct Hiddify import."""
    return f"hiddify://install-config?url={quote_plus(subscription_link)}"


def resolve_device_connect_link(device: str, subscription_link: str) -> str:
    """
    Return connect URL depending on target platform.

    NOTE:
    Telegram inline buttons do not support non-http(s) schemes and reject
    hiddify:// links with "Unsupported URL protocol". To keep Android button
    clickable in Telegram, we return the raw subscription HTTPS URL here.
    The deep-link remains available for clients/instructions as fallback.
    """
    return subscription_link
