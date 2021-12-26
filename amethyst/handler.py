from .resource import Resource
from .response import Status, Response
from .request import Connection, Context
from .util import get_path_components
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
        try:
            req_path = get_path_components(req_path)
        except ValueError:
            return Response(Status.BAD_REQUEST, "Invalid URL")

        paths = [
            (get_path_components(i), v) for i, v in self.url_map[host].items()
        ]

        for path, resource in sorted(paths, key=lambda k: len(k[0]), reverse=True):
            if len(req_path) < len(path) or req_path[:len(path)] != path:
                continue

            truncated_path = "/".join(req_path[len(path):])
            if result.path.endswith("/"):
                truncated_path += "/"

            return await resource(Context(
                result.netloc, result.path, truncated_path,
                result.query, conn
            ))

        return Response(
            Status.NOT_FOUND, f"{req_path} was not found on this server."
        )
