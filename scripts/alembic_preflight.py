#!/usr/bin/env python3
"""
Alembic migration drift detector for VPNHub.

Prints the current alembic revision, expected head revision, and detects
whether the live DB schema contains columns that alembic does not yet know
about (schema-ahead-of-alembic drift).

EXIT CODES
  0  — no drift detected, alembic is at head
  1  — drift detected or alembic is behind head (human action required)
  2  — cannot connect to DB / configuration error

USAGE (from repo root, inside the bot/ context or with correct env):
  python scripts/alembic_preflight.py

ENVIRONMENT
  Reads the same env vars as the bot: POSTGRES_DB, POSTGRES_USER,
  POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, DEBUG.
  Loads bot/.env automatically if python-dotenv is available.

NEVER applies DDL automatically. Output is advisory only.
"""
import os
import sys

# ---------------------------------------------------------------------------
# Load environment the same way the bot does
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "bot", ".env"))
except ImportError:
    pass  # dotenv not installed in this environment — rely on shell env

DEBUG = os.getenv("DEBUG", "False") == "True"
POSTGRES_DB = os.getenv("POSTGRES_DB", "")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db_postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

if DEBUG:
    DB_URL = "sqlite:///bot/database/DatabaseVPN.db"
else:
    if not all([POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]):
        print("ERROR: POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD not set.", file=sys.stderr)
        print("       Set DEBUG=True or provide postgres credentials.", file=sys.stderr)
        sys.exit(2)
    DB_URL = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

# ---------------------------------------------------------------------------
# Imports (need sqlalchemy + alembic; both are bot dependencies)
# ---------------------------------------------------------------------------
try:
    import sqlalchemy as sa
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
except ImportError as exc:
    print(f"ERROR: Missing dependency — {exc}", file=sys.stderr)
    print("       Run: pip install sqlalchemy alembic", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Columns the full migration chain should have added to each table.
# Update this map whenever a new migration adds columns.
# ---------------------------------------------------------------------------
EXPECTED_COLUMNS: dict[str, list[str]] = {
    "users": [
        "id", "tgid", "banned", "trial_period", "special_offer",
        "username", "fullname", "referral_user_tgid", "referral_balance",
        "status", "referral_percent",
        "lang", "lang_tg", "blocked", "date_registered", "group", "metric",
        "trial_activated_at", "trial_expires_at",
    ],
    "servers": [
        "id", "type_vpn", "outline_link", "ip", "connection_method",
        "panel", "inbound_id", "password", "login",
        "actual_space", "work", "auto_work", "free_server", "vds",
        "remnawave_squad_id",
    ],
    "keys": [
        "id", "user_tgid", "subscription", "notion_oneday",
        "switch_location", "id_payment", "trial_period", "free_key",
        "server", "wg_public_key",
    ],
    "static_persons": ["id", "name", "server", "wg_public_key"],
    "promocode": ["id", "text", "percent", "count_use", "type_promo", "count_days"],
    "not_remove_key": ["id", "name_key", "key_id", "server_id"],
}


def main() -> int:
    print("=" * 60)
    print("VPNHub Alembic Preflight Check")
    print("=" * 60)
    print(f"DB URL (masked): {DB_URL.split('@')[-1]}")
    print()

    # ------------------------------------------------------------------
    # 1. Connect and read current alembic revision
    # ------------------------------------------------------------------
    try:
        engine = sa.create_engine(DB_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_revs = ctx.get_current_heads()
    except Exception as exc:
        print(f"ERROR: Cannot connect to database — {exc}", file=sys.stderr)
        return 2

    current = ", ".join(current_revs) if current_revs else "(none — alembic_version table empty or missing)"
    print(f"Current revision : {current}")

    # ------------------------------------------------------------------
    # 2. Determine head revision from migration scripts
    # ------------------------------------------------------------------
    alembic_cfg_path = os.path.join(
        os.path.dirname(__file__), "..", "bot", "alembic.ini"
    )
    try:
        cfg = Config(alembic_cfg_path)
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        head = heads[0] if heads else "(unknown)"
    except Exception as exc:
        print(f"WARNING: Could not read alembic scripts — {exc}", file=sys.stderr)
        head = "(unknown)"

    print(f"Head revision    : {head}")
    print()

    drift = False

    # ------------------------------------------------------------------
    # 3. Check alembic version lag
    # ------------------------------------------------------------------
    if not current_revs:
        print("⚠  DRIFT: alembic_version is empty.")
        print("   The DB may have been created outside Alembic (e.g. from models directly).")
        print()
        print("   RECOMMENDED ACTION:")
        print("   If the schema is already correct, stamp the head revision:")
        print(f"     cd bot && alembic stamp {head}")
        print("   If the schema is empty, run migrations:")
        print("     cd bot && alembic upgrade head")
        drift = True
    elif current_revs and head != "(unknown)" and head not in current_revs:
        print(f"⚠  DRIFT: DB is at {current} but head is {head}.")
        print()
        print("   RECOMMENDED ACTION:")
        print("   Review pending migrations, then run:")
        print("     cd bot && alembic upgrade head")
        drift = True
    else:
        print(f"✓  Alembic version is at head ({head}).")

    # ------------------------------------------------------------------
    # 4. Schema-ahead-of-alembic: check for unexpected extra columns
    # ------------------------------------------------------------------
    print()
    print("Schema column audit:")
    try:
        insp = sa.inspect(engine)
        existing_tables = set(insp.get_table_names())
        for table, expected_cols in EXPECTED_COLUMNS.items():
            if table not in existing_tables:
                print(f"  {table}: TABLE MISSING (not yet created or wrong DB)")
                drift = True
                continue
            actual_cols = {c["name"] for c in insp.get_columns(table)}
            expected_set = set(expected_cols)
            missing = expected_set - actual_cols
            extra = actual_cols - expected_set
            if missing:
                print(f"  {table}: ⚠  columns missing from DB: {sorted(missing)}")
                print(f"           → DB is BEHIND migrations. Run: cd bot && alembic upgrade head")
                drift = True
            if extra:
                print(f"  {table}: ⚠  extra columns in DB not in migration chain: {sorted(extra)}")
                print(f"           → DB is AHEAD of Alembic. Stamp after verifying:")
                print(f"             cd bot && alembic stamp {head}")
                drift = True
            if not missing and not extra:
                print(f"  {table}: ✓  columns match")
    except Exception as exc:
        print(f"  WARNING: Could not inspect schema — {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 5. Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    if drift:
        print("RESULT: ⚠  DRIFT DETECTED — human action required (see above).")
        print("        Do NOT restart the bot until drift is resolved.")
        return 1
    else:
        print("RESULT: ✓  No drift detected. Safe to proceed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
