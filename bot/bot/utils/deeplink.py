from urllib.parse import quote_plus


def build_hiddify_android_deeplink(subscription_link: str) -> str:
    """Build Android deep-link for direct Hiddify import."""
    return f"hiddify://install-config?url={quote_plus(subscription_link)}"


def resolve_device_connect_link(device: str, subscription_link: str) -> str:
    """
    Return connect URL depending on target platform.

    Android uses Hiddify deep-link; other platforms receive raw subscription URL.
    """
    if device == "android":
        return build_hiddify_android_deeplink(subscription_link)
    return subscription_link

