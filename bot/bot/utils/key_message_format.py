from html import escape


def format_key_delivery_intro(lang: str, *, vpn_name: str | None = None, is_subscription: bool = False) -> str:
    safe_vpn_name = (vpn_name or "VPN").strip()
    if lang == "en":
        if is_subscription:
            return (
                "🌐 Your VPN is ready.\n\n"
                "Use the fresh subscription link from the next message to import "
                "the profile into your app."
            )
        return (
            "🌐 Your VPN is ready.\n\n"
            "The next message contains your new connection key.\n"
            f"🔐 Protocol: {safe_vpn_name}"
        )
    if is_subscription:
        return (
            "🌐 Ваш VPN готов.\n\n"
            "В следующем сообщении отправили новую ссылку подписки для быстрого импорта."
        )
    return (
        "🌐 Ваш VPN готов.\n\n"
        "В следующем сообщении отправили новый ключ для подключения.\n"
        f"🔐 Протокол: {safe_vpn_name}"
    )


def format_key_payload_message(config: str, lang: str) -> str:
    title = "🔑 Your connection key" if lang == "en" else "🔑 Ваш ключ для подключения"
    return f"{title}\n<pre>{escape(config.strip())}</pre>"
