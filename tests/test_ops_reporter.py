"""Owner reports must stay honest, durable, read-only, and in Yakutsk time."""
import asyncio
from datetime import datetime, timezone
import json

import ops_reporter as r


def test_schedule_uses_yakutsk_and_crosses_utc_date():
    # 22:00 UTC on Oct 29 is 07:00 Yakutsk on Oct 30.
    previous, slot = r.report_slot(datetime(2026, 10, 29, 22, tzinfo=timezone.utc))
    assert slot.isoformat() == "2026-10-30T07:00:00+09:00"
    assert previous.isoformat() == "2026-10-29T21:00:00+09:00"
    previous, slot = r.report_slot(datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
    assert slot.hour == 21 and previous.hour == 7
    _, before = r.report_slot(datetime(2026, 10, 29, 21, 59, tzinfo=timezone.utc))
    assert before.hour == 21 and before.day == 29


def test_incomplete_report_cannot_claim_all_working():
    body = r.render([r.Check("vpn_primary", "unknown", "проверка не подключена", 100)], 0, 100, 300, (0, 0, 0))
    assert "Всё проверено и работает" not in body
    assert "проверка не подключена" in body
    assert "Отсутствие замеров" in body
    assert "после планового времени" in body


def test_collector_freshness_and_secret_safe_output(tmp_path):
    def write(name, value):
        (tmp_path / (name + ".json")).write_text(json.dumps(value))
    write("vpn_primary", {"status": "ok", "checked_at": 1000, "detail": "SECRET-UUID"})
    write("vpn_fallback", {"status": "ok", "checked_at": 0})
    write("route_ru", {"status": "ok", "checked_at": 2000})
    write("accounts_e2e", {"status": "green", "checked_at": 1000})
    checks = {c.name: c for c in r.observations(tmp_path, 1100)}
    assert checks["vpn_primary"].status == "ok"
    assert checks["vpn_fallback"].status == "unknown"
    assert checks["route_ru"].status == "unknown"
    assert checks["accounts_e2e"].status == "unknown"
    assert checks["backup_offsite"].detail == "проверка не подключена"
    assert "SECRET" not in repr(checks)


def test_delivery_survives_restart_and_is_per_channel(tmp_path):
    path = tmp_path / "state.sqlite3"
    s = r.Store(path)
    s.enqueue("slot", ("email", "telegram"), "subject", "body", 1000)
    s.db.execute("UPDATE outbox SET sent=1 WHERE channel='email'")
    s.db.commit()
    s.db.close()
    s = r.Store(path)
    s.enqueue("slot", ("email", "telegram"), "subject", "new body", 1000)
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 2
    assert s.db.execute("SELECT channel FROM outbox WHERE sent=0").fetchone()[0] == "telegram"
    assert s.db.execute("SELECT body FROM outbox LIMIT 1").fetchone()[0] == "body"
    s.db.close()


def test_incident_three_failures_and_two_successes(tmp_path):
    s = r.Store(tmp_path / "state.sqlite3")
    for now in (100, 160):
        s.record([r.Check("website", "fail", "HTTP 502", now)], now, ("email",))
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
    s.record([r.Check("website", "fail", "HTTP 502", 220)], 220, ("email",))
    s.record([r.Check("website", "fail", "HTTP 502", 280)], 280, ("email",))
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
    for now in (340, 400):
        s.record([r.Check("website", "ok", "HTTP 200", now)], now, ("email",))
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 2
    assert s.db.execute("SELECT opened FROM incidents").fetchone()[0] is None
    s.db.close()


def test_stale_collector_alerts_but_not_unconfigured(tmp_path):
    s = r.Store(tmp_path / "state.sqlite3")
    for now in (100, 160, 220):
        s.record([r.Check("route_ru", "unknown", "результат устарел или время неверно", now),
                  r.Check("vpn_primary", "unknown", "проверка не подключена", now)], now, ("telegram",))
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
    s.db.close()


def test_disappearing_previously_working_collector_alerts(tmp_path):
    s = r.Store(tmp_path / "state.sqlite3")
    s.record([r.Check("vpn_primary", "ok", "подтверждено сборщиком", 100)], 100, ("email",))
    for now in (160, 220, 280):
        s.record([r.Check("vpn_primary", "unknown", "проверка не подключена", now)], now, ("email",))
    assert s.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
    s.db.close()


def test_public_origin_rejects_http_credentials_or_path():
    import pytest
    for base in ("http://example.com", "https://user:secret@example.com", "https://example.com/a", "https://example.com?token=secret"):
        with pytest.raises(ValueError):
            r.https_url(base, "/healthz")
    assert r.https_url("https://example.com:8443/", "/healthz") == "https://example.com:8443/healthz"


def test_readiness_requires_db_and_nats():
    class Response:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self): return {"status": "ok", "details": {"db": True, "nats": False}}
    class Session:
        def get(self, *args, **kwargs): return Response()
    check = asyncio.run(r.http_check(Session(), "readiness", "http://vpn_hub_bot:8888", "/health", 100, health=True, private=True))
    assert check.status == "fail"


def test_preview_does_not_send_or_create_state(tmp_path, monkeypatch, capsys):
    async def collect(*args): return [r.Check("website", "ok", "HTTP 200", 100)]
    monkeypatch.setattr(r, "collect", collect)
    monkeypatch.setenv("OPS_REPORT_STATE_DIR", str(tmp_path / "must-not-exist"))
    asyncio.run(r.run(preview=True))
    assert not (tmp_path / "must-not-exist").exists()
    assert "Текущий замер" in capsys.readouterr().out


def test_email_failure_does_not_block_telegram_or_leak_secrets(tmp_path, monkeypatch, caplog):
    s = r.Store(tmp_path / "state.sqlite3")
    s.enqueue("slot", ("email", "telegram"), "subject", "body", 1000)
    s.db.commit()
    def failed(*args): raise RuntimeError("PRIVATE_PASSWORD")
    monkeypatch.setattr(r, "send_email", failed)
    monkeypatch.setenv("TG_TOKEN", "SECRET")
    monkeypatch.setenv("ADMIN_TG_ID", "123")
    class Response:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self): return {"ok": True}
    class Session:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(r.aiohttp, "ClientSession", Session)
    asyncio.run(r.deliver(s, 100))
    assert s.db.execute("SELECT sent FROM outbox WHERE channel='telegram'").fetchone()[0] == 1
    assert s.db.execute("SELECT sent FROM outbox WHERE channel='email'").fetchone()[0] == 0
    assert "PRIVATE_PASSWORD" not in caplog.text
    s.db.close()


def test_database_uses_readonly_transaction_and_returns_only_aggregates(monkeypatch):
    import asyncpg
    seen = {}
    class Transaction:
        async def __aenter__(self): pass
        async def __aexit__(self, *args): pass
    class Connection:
        def transaction(self, **kwargs):
            seen["transaction"] = kwargs
            return Transaction()
        async def fetchrow(self, query, now):
            assert "count(*)" in query and "SELECT" in query
            return dict(links=2, tg=6, web=2, missing=0, pending=0)
        async def close(self, **kwargs): seen["closed"] = True
    async def connect(**kwargs):
        seen["settings"] = kwargs["server_settings"]
        return Connection()
    monkeypatch.setattr(asyncpg, "connect", connect)
    result = asyncio.run(r.account_check(1000))
    assert result.status == "ok"
    assert "TG 6, web 2" in result.detail
    assert seen["transaction"] == {"readonly": True}
    assert seen["settings"]["default_transaction_read_only"] == "on"
    assert seen["closed"]


def test_telegram_rate_limit_delays_retry(tmp_path, monkeypatch):
    s = r.Store(tmp_path / "state.sqlite3")
    s.enqueue("slot", ("telegram",), "subject", "body", 1000)
    s.db.commit()
    monkeypatch.setenv("TG_TOKEN", "SECRET")
    monkeypatch.setenv("ADMIN_TG_ID", "123")
    monkeypatch.setattr(r.time, "time", lambda: 100)
    class Response:
        status = 429
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self): return {"ok": False, "parameters": {"retry_after": 300}}
    class Session:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(r.aiohttp, "ClientSession", Session)
    asyncio.run(r.deliver(s, 100))
    assert s.db.execute("SELECT sent,retry_at FROM outbox").fetchone() == (0, 400)
    s.db.close()
