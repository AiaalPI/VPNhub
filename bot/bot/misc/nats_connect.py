import nats
from nats.aio.client import Client
from nats.js import JetStreamContext


async def connect_to_nats(servers: list[str]) -> tuple[
    Client, JetStreamContext]:
    nc: Client = await nats.connect(
        servers=servers,
        allow_reconnect=True,
        max_reconnect_attempts=-1,
        reconnect_time_wait=2,
    )
    js: JetStreamContext = nc.jetstream()

    return nc, js
