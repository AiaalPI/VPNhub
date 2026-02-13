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
import uvloop


log = logging.getLogger(__name__)


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
        log.info("event=startup.runtime_init uvloop=true")
        uvloop.install()
        log.info("event=startup.bot_begin")
        asyncio.run(start_bot())

if __name__ == '__main__':
    main()
