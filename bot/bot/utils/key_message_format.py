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


def format_key_payload_message(
    config: str,
    lang: str,
    *,
    clash_url: str | None = None,
    singbox_url: str | None = None,
) -> str:
    title = "🔑 Your connection key" if lang == "en" else "🔑 Ваш ключ для подключения"
    result = f"{title}\n<pre>{escape(config.strip())}</pre>"
    if clash_url or singbox_url:
        if lang == "en":
            result += "\n\n📱 <b>Subscriptions with .ru bypass</b>"
            if clash_url:
                result += f'\n• <a href="{escape(clash_url)}">v2rayN (Android) — Clash</a>'
            if singbox_url:
                result += f'\n• <a href="{escape(singbox_url)}">Streisand (iOS) — Sing-box</a>'
        else:
            result += "\n\n📱 <b>Подписки — сайты .ru без VPN</b>"
            if clash_url:
                result += f'\n• <a href="{escape(clash_url)}">v2rayN (Android) — Clash</a>'
            if singbox_url:
                result += f'\n• <a href="{escape(singbox_url)}">Streisand (iOS) — Sing-box</a>'
    return result
