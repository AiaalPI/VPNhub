import argparse
import logging
import sys
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

def run_alembic_command(command, *args):
    """Выполняет команды Alembic."""
    cmd = ['alembic', command] + list(args)
    logging.info(f"Выполнение команды: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True)
    return result

def create_migration(description):
    """Создает новую миграцию с описанием."""
    if not description:
        logging.error("Описание миграции не может быть пустым.")
        sys.exit(1)
    try:
        run_alembic_command(
            'revision', '--autogenerate', '-m', description
        )
        logging.info("Миграция успешно создана.")
    except subprocess.CalledProcessError as e:
        logging.error('Ошибка при создании миграции', exc_info=e)

def  main():
    parser = argparse.ArgumentParser(
        description="Управление ботом и миграциями.")
    parser.add_argument("--newmigrate",
                        help="Создать новую миграцию с описанием.")
    args = parser.parse_args()

    if args.newmigrate:
        create_migration(args.newmigrate)
    else:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'])
        uvloop.install()
        asyncio.run(start_bot())

if __name__ == '__main__':
    main()
