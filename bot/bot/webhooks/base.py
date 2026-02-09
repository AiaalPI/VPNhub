from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
import logging

from bot.webhooks.hook_wata import wata_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    http_client = httpx.AsyncClient(timeout=10)
    app.state.http_client = http_client
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def add_common_dependencies(request: Request, call_next):
    request.state.bot = app.state.bot
    async with app.state.session_maker() as session:
        request.state.session = session
        try:
            response = await call_next(request)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    return response


app.include_router(wata_router)
