from .response import Status, Response
from .request import Context
from urllib.parse import urlparse

import logging


class GenericHandler():
    def __init__(self, url_map):
        self.url_map = url_map
        self.access_log = logging.getLogger("amethyst.access")
        self.log = logging.getLogger("amethyst.handler.GenericHandler")

    async def __call__(self, url, conn):
        result = urlparse(url)

        host = result.netloc
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

                resp = await paths[path](Context(
                    result.netloc, req_path, truncated_path,
                    result.query, conn
                ))

                break

        else:
            resp = Response(Status.NOT_FOUND,
                            f"{req_path} was not found on this server.")

        self.access_log.info(
            f"{conn.peer_addr[0]} {req_path} "
            f"{resp.status_code.value}: {resp.meta}"
        )

        return resp
