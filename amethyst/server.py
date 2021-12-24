#!/usr/bin/env python3

import asyncio
import ssl

from typing import Callable

from .response import Response
from .request import Connection


class Server():
    def __init__(
        self,
        ssl_context: ssl.SSLContext,
        url_handler: Callable[[str, bytes], Response],
        port: int = 1965
    ):
        self.ssl_context = ssl_context
        self.url_handler = url_handler
        self.port = port

    def start(self):
        loop = asyncio.get_event_loop()

        server = asyncio.start_server(
            self.handle_connection, port=self.port,
            ssl=self.ssl_context, loop=loop,
        )

        loop.run_until_complete(server)
        loop.run_forever()

    async def handle_connection(self, reader, writer):
        peer_addr = writer.get_extra_info("peername")
        peer_cert = writer.get_extra_info("peercert")

        url = (await reader.readline()).rstrip(b"\r\n").decode()
        response = await self.url_handler(
            url, Connection(self.port, peer_addr, peer_cert)
        )

        line = f"{response.status_code.value} {response.meta}\r\n".encode()
        writer.write(line)

        if response.status_code.is_success() and response.content is not None:
            writer.write(response.content)

        writer.close()
