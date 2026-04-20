import json
import logging
from urllib.parse import urlsplit, parse_qs, unquote

log = logging.getLogger(__name__)


def _parse_vless_uri(uri: str) -> dict | None:
    try:
        parts = urlsplit(uri)
        if parts.scheme != "vless":
            return None

        params = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        security = params.get("security", "")
        sni = params.get("sni", "")
        fp = params.get("fp", "chrome")
        pbk = params.get("pbk", "")
        sid = params.get("sid", "")
        flow = params.get("flow", "")
        tag = f"{parts.hostname}-{parts.port}"

        outbound: dict = {
            "type": "vless",
            "tag": tag,
            "server": parts.hostname,
            "server_port": int(parts.port),
            "uuid": parts.username,
        }

        if flow:
            outbound["flow"] = flow

        if security in ("tls", "reality"):
            tls: dict = {
                "enabled": True,
                "server_name": sni,
                "utls": {"enabled": True, "fingerprint": fp},
            }
            if security == "reality":
                tls["reality"] = {
                    "enabled": True,
                    "public_key": pbk,
                    "short_id": sid,
                }
            outbound["tls"] = tls

        return outbound
    except Exception:
        log.warning("Failed to parse VLESS URI for sing-box: %s", uri[:80], exc_info=True)
        return None


def build_singbox_config(vless_uris: list[str]) -> str:
    proxies = [o for uri in vless_uris if (o := _parse_vless_uri(uri)) is not None]
    if not proxies:
        return ""

    first_tag = proxies[0]["tag"]

    outbounds = proxies + [
        {"type": "direct", "tag": "direct"},
        {"type": "block", "tag": "block"},
    ]

    config = {
        "outbounds": outbounds,
        "route": {
            "final": first_tag,
        },
    }

    return json.dumps(config, ensure_ascii=False, indent=2)
