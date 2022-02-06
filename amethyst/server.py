#!/usr/bin/env python3

import asyncio
import logging
import signal
import traceback
from typing import TYPE_CHECKING

from .response import Response, Status
from .tls import make_sni_context

if TYPE_CHECKING:
    from .config import Config


class Server:
    def __init__(
        self,
        config: "Config",
    ):
        self.log = logging.getLogger("amethyst.server")
        self.access_log = logging.getLogger("amethyst.access")

        self.server = None
        self.config = config

        self.ssl_context = make_sni_context(config)
        self.server = self.get_server()

    def get_server(self):
        loop = asyncio.get_event_loop()

        return asyncio.start_server(
            self.handle_connection,
            port=self.config.port,
            ssl=self.ssl_context,
            loop=loop,
        )

    async def handle_connection(self, reader, writer):
        from .request import Connection

        peer_addr = writer.get_extra_info("peername")
        peer_cert = writer.get_extra_info("peercert")

        self.log.debug(f"Received connection from {peer_addr}")

        url = "-"
        try:
            url = (await reader.readuntil(b"\r\n")).rstrip(b"\r\n").decode()

            if len(url) > 1024:
                response = Response(Status.BAD_REQUEST, "URL too long!")
            else:
                response = await self.config.handler(
                    url, Connection(self, peer_addr, peer_cert)
                )

        except UnicodeDecodeError:
            response = Response(Status.BAD_REQUEST, "URL must be UTF-8")

        except Exception:
            self.log.error(f"While generating response; {traceback.format_exc()}")

            response = Response(
                Status.TEMPORARY_FAILURE,
                "Exception thrown during request processing; see server logs for details.",
            )

        self.access_log.info(
            f"{url} {response.status_code.value}[{response.status_code.name}]"
            f" {response.meta}"
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
