import os
import asyncio
import logging

import nats

from nats.js.api import StreamConfig


async def main():
    logger = logging.getLogger(__name__)
    nc = await nats.connect('nats://nats:4222')
    js = nc.jetstream()
    logger.debug('NATS connection established')

    stream_config = StreamConfig(
        name="DeleteKeyStream",
        subjects=[
            "aiogram.remove.key",
        ],
        retention="limits",
        max_bytes=300 * 1024 * 1024,
        max_msg_size=10 * 1024 * 1024,
        storage="file",
        allow_direct=True,
    )

    await js.add_stream(stream_config)

    print("Stream `DeleteKeyStream` created successfully.")


if __name__ == '__main__':
    asyncio.run(main())
