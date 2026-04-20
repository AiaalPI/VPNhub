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


def format_key_payload_message(config: str, lang: str, *, clash_url: str | None = None) -> str:
    title = "🔑 Your connection key" if lang == "en" else "🔑 Ваш ключ для подключения"
    result = f"{title}\n<pre>{escape(config.strip())}</pre>"
    if clash_url:
        if lang == "en":
            sub_title = "📱 Subscription for v2rayN / Streisand (sites .ru without VPN)"
        else:
            sub_title = "📱 Подписка для v2rayN / Streisand (сайты .ru без VPN)"
        result += f"\n\n{sub_title}\n<code>{escape(clash_url)}</code>"
    return result
