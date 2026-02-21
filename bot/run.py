import argparse
import fcntl
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
import subprocess


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(filename)s:%(lineno)d "
           "[%(asctime)s] - %(name)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            filename='logs/all.log',
            maxBytes=1024 * 1024 * 25,
            encoding='UTF-8',
        ),
        RotatingFileHandler(
            filename='logs/errors.log',
            maxBytes=1024 * 1024 * 25,
            encoding='UTF-8',
        ),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.getLogger().handlers[1].setLevel(logging.ERROR)

logging.getLogger("httpx").setLevel(logging.INFO)

from bot.main import start_bot
import asyncio

try:
    import uvloop  # type: ignore
except ModuleNotFoundError:
    uvloop = None


log = logging.getLogger(__name__)


def setup_event_loop() -> bool:
    raw_value = os.getenv("USE_UVLOOP", "auto")
    value = raw_value.strip().lower()
    force_enable = value in {"1", "true", "yes"}
    force_disable = value in {"0", "false", "no"}
    unknown_value = not (force_enable or force_disable or value == "auto")
    if unknown_value:
        log.warning(
            "event=startup.uvloop.invalid_value value=%r action=fallback_auto",
            raw_value,
        )
    if force_disable:
        log.info("event=startup.uvloop.enabled value=false mode=disabled_by_env")
        return False
    if uvloop is None:
        if force_enable:
            log.warning(
                "event=startup.uvloop.enabled value=false mode=forced_but_missing action=use_default_loop"
            )
        else:
            log.info("event=startup.uvloop.enabled value=false mode=not_installed")
        return False
    uvloop.install()
    mode = "forced" if force_enable else "auto"
    log.info("event=startup.uvloop.enabled value=true mode=%s", mode)
    return True


def run_alembic_command(command, *args):
    """Выполняет команды Alembic."""
    cmd = ['alembic', command] + list(args)
    log.info("event=migration.run cmd=%s", " ".join(cmd))
    result = subprocess.run(cmd, check=True)
    return result


def run_migrations_with_retry(
    retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
) -> None:
    cmd = [sys.executable, '-m', 'alembic', 'upgrade', 'head']
    attempt = 1
    while True:
        try:
            log.info("event=migration.start attempt=%d cmd=%s", attempt, " ".join(cmd))
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            log.info("event=migration.success attempt=%d", attempt)
            return
        except subprocess.CalledProcessError as exc:
            stdout = (exc.stdout or "").strip()
            stderr = (exc.stderr or "").strip()
            log.error(
                "event=migration.fail attempt=%d exit_code=%s stdout=%r stderr=%r",
                attempt,
                exc.returncode,
                stdout[-1000:],
                stderr[-1000:],
            )
            if attempt >= retries:
                log.critical(
                    "event=migration.abort attempts=%d reason=max_retries_exceeded",
                    retries,
                )
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            log.warning("event=migration.retry_in seconds=%.1f next_attempt=%d", delay, attempt + 1)
            time.sleep(delay)
            attempt += 1


def acquire_single_instance_lock(lock_path: str = "/tmp/vpnhub_bot.lock"):
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.critical("event=startup.abort reason=instance_lock_exists lock=%s", lock_path)
        raise SystemExit(1)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    log.info("event=startup.lock_acquired lock=%s pid=%s", lock_path, os.getpid())
    return lock_file


def create_migration(description):
    """Создает новую миграцию с описанием."""
    if not description:
        log.error("Описание миграции не может быть пустым.")
        sys.exit(1)
    try:
        run_alembic_command(
            'revision', '--autogenerate', '-m', description
        )
        log.info("Миграция успешно создана.")
    except subprocess.CalledProcessError as e:
        log.error('Ошибка при создании миграции', exc_info=e)

def  main():
    parser = argparse.ArgumentParser(
        description="Управление ботом и миграциями.")
    parser.add_argument("--newmigrate",
                        help="Создать новую миграцию с описанием.")
    args = parser.parse_args()

    if args.newmigrate:
        create_migration(args.newmigrate)
    else:
        _instance_lock = acquire_single_instance_lock()
        run_migrations_with_retry()
        uvloop_enabled = setup_event_loop()
        log.info("event=startup.runtime_init uvloop=%s", str(uvloop_enabled).lower())
        log.info("event=startup.bot_begin")
        asyncio.run(start_bot())

if __name__ == '__main__':
    main()
