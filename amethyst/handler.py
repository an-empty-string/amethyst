from .resource import Resource
from .response import Status, Response
from .request import Connection, Context
from urllib.parse import urlparse
from typing import Dict, Callable, Awaitable

import logging
import re

Handler = Callable[[str, Connection], Awaitable[Response]]
PORT_RE = re.compile(r":([0-9]{1,5})$")


class GenericHandler():
    def __init__(self, url_map: Dict[str, Dict[str, Resource]]):
        self.url_map = url_map
        self.log = logging.getLogger("amethyst.handler.GenericHandler")

    async def __call__(self, url: str, conn: Connection) -> Response:
        result = urlparse(url)

        if not result.scheme:
            return Response(
                Status.BAD_REQUEST,
                f"Requested URL must have a scheme."
            )

        if result.scheme != "gemini":
            # This is exclusively a Gemini server.
            return Response(
                Status.PROXY_REQUEST_REFUSED,
                f"This server does not proxy non-Gemini URLs."
            )

        host = result.netloc

        # Ignore port component of URL; we'd only need it if we were proxying,
        # which we explicitly do not support.
        #
        # If we support virtual hosting based on ports in the future, this might
        # need to be reconsidered.

        if (port_match := PORT_RE.search(host)):
            if int(port_match.group(1)) != conn.server.config.port:
                return Response(
                    Status.PROXY_REQUEST_REFUSED,
                    f"{host} is not served here."
                )

            host = PORT_RE.sub("", host) 

        if host not in self.url_map:
            self.log.warn(f"Received request for host {host} not in URL map")

            return Response(
                Status.PROXY_REQUEST_REFUSED,
                f"{host} is not served here.",
            )

        req_path = result.path
        if req_path == "":
            req_path = "/"

        paths = self.url_map[host]

        for path in sorted(paths, key=len, reverse=True):
            if req_path.startswith(path):
                truncated_path = req_path[len(path):]

                return await paths[path](Context(
                    result.netloc, req_path, truncated_path,
                    result.query, conn
                ))

        return Response(
            Status.NOT_FOUND, f"{req_path} was not found on this server."
        )