"""Independent, read-only checks and durable owner reports. Never starts bot polling."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import smtplib
import sqlite3
import ssl
import time
from urllib.parse import urlsplit

import aiohttp
import pytz

TZ = pytz.timezone("Asia/Yakutsk")
LOG = logging.getLogger("ops_reporter")
LABELS = {
    "readiness": "Бот / БД / NATS",
    "redis": "Redis",
    "website": "Сайт HTTPS",
    "subscriptions": "Сервис подписок HTTPS",
    "accounts": "Учёт подписок в БД",
    "vpn_primary": "VPN 443: внешний трафик",
    "vpn_fallback": "VPN 2087: внешний трафик",
    "xui_integrity": "Согласованность БД / XUI",
    "accounts_e2e": "Привязка сайта и Telegram: E2E",
    "route_ru": "Доступ из сети РФ без VPN",
    "backup_offsite": "Внешний бэкап",
    "backup_restore": "Пробное восстановление",
}
OPTIONAL = tuple(LABELS)[5:]
ICONS = {"ok": "✅", "fail": "❌", "unknown": "⚪"}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    checked_at: float


def report_slot(now: datetime) -> tuple[datetime, datetime]:
    """Explicit Yakutsk schedule, independent of host/container timezone."""
    local = now.astimezone(TZ)
    slots = [TZ.localize(datetime.combine(local.date() + timedelta(days=d),
             datetime.min.time())).replace(hour=h) for d in (-1, 0) for h in (7, 21)]
    slot = max(s for s in slots if s <= local)
    previous = max(s for s in slots if s < slot)
    return previous, slot


def https_url(base: str, suffix: str) -> str:
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("invalid HTTPS origin")
    return base.rstrip("/") + suffix


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS samples (
              at REAL NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL,
              PRIMARY KEY(at,name));
            CREATE TABLE IF NOT EXISTS outbox (
              id TEXT NOT NULL, channel TEXT NOT NULL, subject TEXT NOT NULL,
              body TEXT NOT NULL, expires REAL NOT NULL, retry_at REAL NOT NULL DEFAULT 0,
              sent INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(id,channel));
            CREATE TABLE IF NOT EXISTS incidents (
              name TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0,
              successes INTEGER NOT NULL DEFAULT 0, opened REAL);
        """)

    def enqueue(self, key, channels, subject, body, expires):
        for channel in channels:
            self.db.execute("INSERT OR IGNORE INTO outbox(id,channel,subject,body,expires) VALUES(?,?,?,?,?)",
                            (key, channel, subject, body, expires))

    def record(self, checks, now, channels):
        for c in checks:
            self.db.execute("INSERT OR REPLACE INTO samples VALUES(?,?,?)", (now, c.name, c.status))
            old = self.db.execute("SELECT failures,successes,opened FROM incidents WHERE name=?", (c.name,)).fetchone()
            # Missing optional collectors remain visible in reports without startup alert spam.
            if c.status == "unknown":
                if c.detail != "проверка не подключена" or old is not None:
                    state = "fail"
                else:
                    continue
            else:
                state = c.status
            failures, successes, opened = old or (0, 0, None)
            failures, successes = (failures + 1, 0) if state == "fail" else (0, successes + 1)
            if failures >= 3 and opened is None:
                opened = now
                body = f"❌ {LABELS[c.name]}: три последовательных сбоя.\n{c.detail}\nПроверка: {stamp(now)}"
                self.enqueue(f"incident:{c.name}:{now}", channels, "VPNHub: сбой", body, now + 3600)
            elif successes >= 2 and opened is not None:
                body = f"✅ {LABELS[c.name]}: восстановлено.\nДлительность инцидента: {int((now-opened)/60)} мин.\nПроверка: {stamp(now)}"
                self.enqueue(f"recovered:{c.name}:{opened}", channels, "VPNHub: восстановлено", body, now + 3600)
                opened = None
            self.db.execute("INSERT OR REPLACE INTO incidents VALUES(?,?,?,?)", (c.name, failures, successes, opened))
        self.db.execute("DELETE FROM samples WHERE at < ?", (now - 30*86400,))
        self.db.execute("DELETE FROM outbox WHERE expires < ?", (now - 30*86400,))
        self.db.commit()

    def history(self, start, end):
        return self.db.execute("SELECT COUNT(DISTINCT at), SUM(status='fail'), SUM(status='unknown') FROM samples WHERE at>=? AND at<=?",
                               (start, end)).fetchone()

    def incident_summary(self, start, end):
        opened = self.db.execute("SELECT count(DISTINCT id) FROM outbox WHERE id LIKE 'incident:%' AND expires-3600>=? AND expires-3600<=?", (start, end)).fetchone()[0]
        recovered = self.db.execute("SELECT count(DISTINCT id) FROM outbox WHERE id LIKE 'recovered:%' AND expires-3600>=? AND expires-3600<=?", (start, end)).fetchone()[0]
        active = self.db.execute("SELECT count(*) FROM incidents WHERE opened IS NOT NULL").fetchone()[0]
        return f"Инцидентов за период: {opened}; восстановлений: {recovered}; открыто сейчас: {active}."

    def delivery_summary(self, now):
        rows = self.db.execute("SELECT channel,count(*) FROM outbox WHERE sent=0 AND expires<? GROUP BY channel", (now,)).fetchall()
        return "Просроченных доставок: " + (", ".join(f"{channel}: {count}" for channel, count in rows) if rows else "0") + "."


def stamp(epoch):
    return datetime.fromtimestamp(epoch, TZ).strftime("%d.%m %H:%M")


def render(checks, start, slot, now, history):
    good = all(c.status == "ok" for c in checks)
    title = "✅ Всё проверено и работает" if good else "⚠️ Есть сбои или непроверенные компоненты"
    lines = [f"VPNHub — отчёт {stamp(slot)} (Якутск)", title,
             f"Период: {stamp(start)} — {stamp(slot)}", f"Текущий замер: {stamp(now)}", ""]
    for c in checks:
        lines.append(f"{ICONS[c.status]} {LABELS[c.name]}: {c.detail} [{stamp(c.checked_at)}]")
    samples, failed, unknown = history
    lines += ["", f"В периоде: замеров {samples}, неуспешных проверок {failed or 0}, без подтверждения {unknown or 0}.",
              "Отсутствие замеров не означает отсутствие сбоев.",
              "HTTP-проверки выполнены с VPS; маршрут клиента они не подтверждают."]
    if now - slot > 120:
        lines.append("Доставка после планового времени; время свежего замера указано выше.")
    return "\n".join(lines)


async def http_check(session, name, base, path, now, *, health=False, private=False):
    if not base:
        return Check(name, "unknown", "проверка не подключена", now)
    try:
        url = base + path if private else https_url(base, path)
        async with session.get(url, allow_redirects=False) as r:
            if r.status != 200:
                return Check(name, "fail", f"HTTP {r.status}", now)
            if health:
                data = await r.json()
                ok = data.get("status") == "ok"
                if name == "readiness":
                    ok = ok and data.get("details", {}).get("db") is True and data.get("details", {}).get("nats") is True
                return Check(name, "ok" if ok else "fail", "готов" if ok else "зависимости недоступны", now)
            # Consume only a bounded part; never persist or print response contents.
            body = await r.content.read(512)
            return Check(name, "ok" if body else "fail", "HTTP 200" if body else "пустой ответ", now)
    except Exception as exc:
        return Check(name, "fail", type(exc).__name__, now)


async def redis_check(now):
    try:
        from redis.asyncio import Redis
        async with Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), socket_connect_timeout=3, socket_timeout=3) as client:
            ok = await client.ping()
        return Check("redis", "ok" if ok else "fail", "PING" if ok else "нет ответа", now)
    except Exception as exc:
        return Check("redis", "fail", type(exc).__name__, now)


async def account_check(now):
    """Aggregate-only SQL; explicitly read-only, no ORM startup or migrations."""
    conn = None
    try:
        import asyncpg
        settings = {"default_transaction_read_only": "on", "statement_timeout": "5000"}
        dsn = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://", 1)
        options = {"dsn": dsn} if dsn else dict(host=os.getenv("POSTGRES_HOST", "db_postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")), user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"), database=os.getenv("POSTGRES_DB"))
        conn = await asyncpg.connect(**options, timeout=5, command_timeout=5, server_settings=settings)
        async with conn.transaction(readonly=True):
            row = await conn.fetchrow("""
                SELECT (SELECT count(*) FROM web_telegram_links) links,
                  (SELECT count(*) FROM keys WHERE subscription > $1) tg,
                  (SELECT count(*) FROM web_subscriptions WHERE expires_at > $1) web,
                  (SELECT count(*) FROM keys WHERE subscription > $1 AND server IS NULL) missing,
                  (SELECT count(*) FROM web_subscriptions WHERE expires_at > $1 AND provisioned_until < expires_at) pending
            """, int(now))
        detail = f"связей {row['links']}, активных TG {row['tg']}, web {row['web']}"
        if row["missing"] or row["pending"]:
            return Check("accounts", "fail", detail + f"; без сервера {row['missing']}, ожидают выдачи {row['pending']}", now)
        return Check("accounts", "ok", detail + "; E2E — отдельная проверка", now)
    except Exception as exc:
        return Check("accounts", "fail", type(exc).__name__, now)
    finally:
        if conn is not None:
            try:
                await conn.close(timeout=3)
            except Exception:
                # A broken DB connection must not cancel the other report checks.
                conn.terminate()


def observations(directory: Path, now):
    """Read admin-owned collector results, never arbitrary messages or secrets.

    No default success. Unknown, old, future-dated, or malformed results fail closed.
    Per-check freshness ceilings prevent accidental indefinite green status.
    """
    result = []
    for name in OPTIONAL:
        path = directory / (name + ".json")
        if not path.exists():
            result.append(Check(name, "unknown", "проверка не подключена", now))
            continue
        try:
            if path.stat().st_size > 4096:
                raise ValueError()
            data = json.loads(path.read_text())
            checked = float(data["checked_at"])
            ttl = 35*86400 if name == "backup_restore" else 26*3600 if name in ("backup_offsite", "accounts_e2e") else 900
            if not 0 <= now - checked <= ttl:
                result.append(Check(name, "unknown", "результат устарел или время неверно", now))
            elif data["status"] not in ("ok", "fail"):
                raise ValueError()
            else:
                result.append(Check(name, data["status"], "подтверждено сборщиком" if data["status"] == "ok" else "сбой проверки", checked))
        except (ValueError, TypeError, KeyError, OSError):
            result.append(Check(name, "unknown", "некорректный результат сборщика", now))
    return result


async def collect(now, directory):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
        checks = await asyncio.gather(
            http_check(session, "readiness", "http://vpn_hub_bot:8888", "/health", now, health=True, private=True),
            redis_check(now),
            http_check(session, "website", os.getenv("PORTAL_ORIGIN", ""), "/web/", now),
            http_check(session, "subscriptions", os.getenv("PUBLIC_SUBSCRIPTION_BASE", ""), "/healthz", now, health=True),
            account_check(now),
        )
    return list(checks) + observations(directory, now)


def send_email(subject, body, key):
    msg = EmailMessage()
    msg["From"] = os.environ["PORTAL_MAIL_FROM"]
    msg["To"] = os.environ["OPS_REPORT_EMAIL_TO"]
    msg["Subject"] = subject
    # Stable ID helps mail clients deduplicate an ambiguous SMTP acknowledgement.
    msg["Message-ID"] = f"<{hashlib.sha256(key.encode()).hexdigest()}@vpnhub-report>"
    msg.set_content(body)
    port = int(os.getenv("PORTAL_SMTP_PORT", "465"))
    context = ssl.create_default_context()
    if port == 465:
        smtp = smtplib.SMTP_SSL(os.environ["PORTAL_SMTP_HOST"], port, timeout=15, context=context)
    else:
        smtp = smtplib.SMTP(os.environ["PORTAL_SMTP_HOST"], port, timeout=15)
    with smtp:
        if port != 465:
            smtp.starttls(context=context)
        smtp.login(os.environ["PORTAL_SMTP_USER"], os.environ["PORTAL_SMTP_PASSWORD"])
        smtp.send_message(msg)


async def deliver(store, now):
    rows = store.db.execute("SELECT id,channel,subject,body FROM outbox WHERE sent=0 AND retry_at<=? AND expires>=? ORDER BY rowid LIMIT 10", (now, now)).fetchall()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for key, channel, subject, body in rows:
            retry = 60
            ok = False
            try:
                if channel == "email":
                    await asyncio.to_thread(send_email, subject, body, key)
                    ok = True
                else:
                    token = os.environ["TG_TOKEN"]
                    async with session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                        "chat_id": os.environ["ADMIN_TG_ID"], "text": body, "disable_web_page_preview": True}) as r:
                        data = await r.json()
                        ok = r.status == 200 and data.get("ok") is True
                        if r.status == 429:
                            retry = max(60, int(data.get("parameters", {}).get("retry_after", 60)))
                LOG.info("event=report_delivery channel=%s status=%s", channel, "sent" if ok else "retry")
            except Exception as exc:
                # Never log exception messages: SMTP/HTTP exceptions may contain secrets.
                LOG.warning("event=report_delivery channel=%s error_type=%s", channel, type(exc).__name__)
            store.db.execute("UPDATE outbox SET sent=?,retry_at=? WHERE id=? AND channel=?", (int(ok), time.time()+retry, key, channel))
            store.db.commit()


def channels_from_env():
    channels = tuple(dict.fromkeys(os.getenv("OPS_REPORT_CHANNELS", "email,telegram").split(",")))
    if not channels or any(c not in ("email", "telegram") for c in channels):
        raise ValueError("invalid report channels")
    needed = []
    if "email" in channels:
        needed += ["OPS_REPORT_EMAIL_TO", "PORTAL_MAIL_FROM", "PORTAL_SMTP_HOST", "PORTAL_SMTP_USER", "PORTAL_SMTP_PASSWORD"]
    if "telegram" in channels:
        needed += ["ADMIN_TG_ID", "TG_TOKEN"]
    if any(not os.getenv(key) or "\r" in os.environ[key] or "\n" in os.environ[key] for key in needed):
        raise ValueError("report delivery configuration is incomplete")
    return channels


async def run(preview=False):
    now = time.time()
    start, slot = report_slot(datetime.fromtimestamp(now, TZ))
    directory = Path(os.getenv("OPS_OBSERVATIONS_DIR", "/observations"))
    if preview:
        checks = await collect(now, directory)
        print(render(checks, start.timestamp(), slot.timestamp(), now, (0, 0, 0)))
        return
    channels = channels_from_env()
    state = Path(os.getenv("OPS_REPORT_STATE_DIR", "/state"))
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Only one sender may use this state volume, including manual invocations.
    with (state / "sender.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = Store(state / "reports.sqlite3")
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        try:
            while not stop.is_set():
                now = time.time()
                checks = await collect(now, directory)
                store.record(checks, now, channels)
                start, slot = report_slot(datetime.fromtimestamp(now, TZ))
                # Catch up for one hour after a restart; never flood old reports.
                if now - slot.timestamp() <= 3600:
                    body = render(checks, start.timestamp(), slot.timestamp(), now,
                                  store.history(start.timestamp(), slot.timestamp()))
                    body += "\n" + store.incident_summary(start.timestamp(), slot.timestamp())
                    body += "\n" + store.delivery_summary(now)
                    store.enqueue(f"report:{slot.isoformat()}", channels,
                                  "VPNHub — отчёт " + stamp(slot.timestamp()), body, slot.timestamp()+3600)
                    store.db.commit()
                await deliver(store, now)
                (state / "heartbeat").touch(mode=0o600)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
        finally:
            store.db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Collect and print; do not schedule, store, or send")
    args = parser.parse_args()
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        asyncio.run(run(args.preview))
    except Exception as exc:
        LOG.error("event=reporter_stopped error_type=%s", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
