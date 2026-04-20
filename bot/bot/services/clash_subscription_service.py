import logging
from urllib.parse import urlsplit, parse_qs, unquote

import yaml

log = logging.getLogger(__name__)

_RU_BYPASS_RULES = [
    "GEOIP,RU,DIRECT",
    "GEOSITE,ru,DIRECT",
]


def _parse_vless_uri(uri: str) -> dict | None:
    try:
        parts = urlsplit(uri)
        if parts.scheme != "vless":
            return None

        params = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        name = unquote(parts.fragment) if parts.fragment else f"{parts.hostname}:{parts.port}"
        security = params.get("security", "")

        proxy: dict = {
            "name": name,
            "type": "vless",
            "server": parts.hostname,
            "port": int(parts.port),
            "uuid": parts.username,
            "network": params.get("type", "tcp"),
            "tls": security in ("tls", "reality"),
            "udp": True,
        }

        if flow := params.get("flow"):
            proxy["flow"] = flow
        if fp := params.get("fp"):
            proxy["client-fingerprint"] = fp
        if sni := params.get("sni"):
            proxy["servername"] = sni

        if security == "reality":
            reality_opts = {}
            if pbk := params.get("pbk"):
                reality_opts["public-key"] = pbk
            if sid := params.get("sid"):
                reality_opts["short-id"] = sid
            if reality_opts:
                proxy["reality-opts"] = reality_opts

        return proxy
    except Exception:
        log.warning("Failed to parse VLESS URI: %s", uri[:80], exc_info=True)
        return None


def build_clash_config(vless_uris: list[str]) -> str:
    proxies = [p for uri in vless_uris if (p := _parse_vless_uri(uri)) is not None]
    if not proxies:
        return ""

    proxy_names = [p["name"] for p in proxies]

    config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "dns": {
            "enable": True,
            "enhanced-mode": "fake-ip",
            "nameserver": ["8.8.8.8", "1.1.1.1"],
            "fallback": ["tls://1.1.1.1", "tls://8.8.8.8"],
            "fallback-filter": {
                "geoip": True,
                "geoip-code": "RU",
                "geosite": ["ru"],
            },
        },
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "🚀 VPN",
                "type": "select",
                "proxies": proxy_names,
            }
        ],
        "rules": _RU_BYPASS_RULES + ["MATCH,🚀 VPN"],
    }

    return yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
