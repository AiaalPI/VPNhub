#!/usr/bin/env python3
"""Local design preview only: no credentials, email, database or payment calls."""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "bot/bot/portal/static"


class Handler(BaseHTTPRequestHandler):
    demo_account = False

    def do_GET(self):
        if self.path == "/web/api/config":
            payload = {"preview": True, "plans": [
                {"months": m, "amount_kopecks": p, "quota_gb": q}
                for m, p, q in [(1, 15000, 50), (3, 45000, 150), (6, 90000, 300), (12, 180000, 600)]],
                "login_available": True, "checkout_available": False,
                "support_email": "", "terms_url": "", "privacy_url": ""}
            return self.send(json.dumps(payload).encode(), "application/json")
        if self.path == "/web/api/account" and self.demo_account:
            now = int(time.time())
            payload = {"email": "demo@example.test", "subscription": {
                "id": "preview", "expires_at": now + 30 * 86400, "active": True, "ready": True, "quota_gb": 50},
                "orders": [{"id": "preview", "months": 1, "amount_kopecks": 15000,
                            "created_at": now, "paid_at": now, "status": "paid"}]}
            return self.send(json.dumps(payload).encode(), "application/json")
        if self.path.startswith("/web/api/"):
            return self.send(b'{"detail":"Preview only"}', "application/json", 401)
        files = {"/": ("index.html", "text/html"), "/web/": ("index.html", "text/html"),
                 "/web/privacy": ("privacy.html", "text/html"),
                 "/web/terms": ("terms.html", "text/html"),
                 "/web/assets/style.css": ("style.css", "text/css"),
                 "/web/assets/app.js": ("app.js", "text/javascript"),
                 "/web/assets/favicon.svg": ("favicon.svg", "image/svg+xml"),
                 "/web/assets/sun.svg": ("sun.svg", "image/svg+xml"),
                 "/web/assets/main-menu.jpg": ("main-menu.jpg", "image/jpeg")}
        item = files.get(self.path)
        if not item:
            return self.send(b"Not found", "text/plain", 404)
        self.send((ROOT / item[0]).read_bytes(), item[1])

    def do_POST(self):
        self.send(json.dumps({"detail": "Это локальный просмотр дизайна. Отправка писем и оплата отключены."}).encode(), "application/json", 503)

    def send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--account", action="store_true", help="Show a clearly labelled sample account; no real profiles or payments")
    args = parser.parse_args()
    Handler.demo_account = args.account
    print(f"Design preview (sample prices, no purchases): http://127.0.0.1:{args.port}/web/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
