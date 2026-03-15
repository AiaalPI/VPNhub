from bot.misc.util import CONFIG

MIGRATION_STATUS_NONE = "none"
MIGRATION_STATUS_PROMPT_SENT = "prompt_sent"
MIGRATION_STATUS_MIGRATED = "migrated"


LEGACY_BACKEND_TYPES = {
    CONFIG.TypeVpn.VLESS.value,
    CONFIG.TypeVpn.SHADOW_SOCKS.value,
    CONFIG.TypeVpn.WIREGUARD.value,
    CONFIG.TypeVpn.AMNEZIA_WG.value,
    CONFIG.TypeVpn.TROJAN.value,
}


def is_legacy_backend_type(type_vpn: int | None) -> bool:
    if type_vpn is None:
        return False
    return int(type_vpn) in LEGACY_BACKEND_TYPES


def should_send_migration_prompt(migration_status: str | None) -> bool:
    status = (migration_status or MIGRATION_STATUS_NONE).strip().lower()
    return status == MIGRATION_STATUS_NONE
