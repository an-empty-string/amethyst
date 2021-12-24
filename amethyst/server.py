#!/usr/bin/env python3

import asyncio
import logging
import ssl
import traceback

from typing import Callable

from .response import Response, Status
from .request import Connection


class Server():
    def __init__(
        self,
        ssl_context: ssl.SSLContext,
        url_handler: Callable[[str, bytes], Response],
        port: int = 1965
    ):
        self.log = logging.getLogger("amethyst.server")
        self.ssl_context = ssl_context
        self.url_handler = url_handler
        self.port = port

    def start(self):
        loop = asyncio.get_event_loop()

        server = asyncio.start_server(
            self.handle_connection, port=self.port,
            ssl=self.ssl_context, loop=loop,
        )

        self.log.info(f"Starting server on port {self.port}")

        loop.run_until_complete(server)
        loop.run_forever()

    async def handle_connection(self, reader, writer):
        peer_addr = writer.get_extra_info("peername")
        peer_cert = writer.get_extra_info("peercert")

        self.log.debug(f"Received connection from {peer_addr}")

        try:
            url = (await reader.readline()).rstrip(b"\r\n").decode()
            response = await self.url_handler(
                url, Connection(self.port, peer_addr, peer_cert)
            )

        except Exception:
            self.log.error(f"While generating response; {traceback.format_exc()}")

            response = Response(
                Status.TEMPORARY_FAILURE,
                "Exception thrown during request processing; see server logs for details."
            )

        try:
            line = f"{response.status_code.value} {response.meta}\r\n".encode()
            writer.write(line)

            if response.status_code.is_success() and response.content is not None:
                writer.write(response.content)

        except Exception:
            self.log.error(f"While writing response; {traceback.format_exc()}")

        finally:
            writer.close()
