from .response import Status, Response
from .request import Context
from urllib.parse import urlparse


def dummy_handler(url, cert):
    return Response(
        Status.SUCCESS, "text/plain",
        b"hello world! " + url.encode()
    )


class GenericHandler():
    def __init__(self, url_map):
        self.url_map = url_map

    async def __call__(self, url, conn):
        result = urlparse(url)

        host = result.netloc
        if host not in self.url_map:
            return Response(
                Status.PROXY_REQUEST_REFUSED,
                f"{host} is not served here.",
            )

        paths = self.url_map[host]

        for path in sorted(paths, key=len, reverse=True):
            if result.path.startswith(path):
                truncated_path = result.path[len(path):]

                return await paths[path](Context(
                    result.netloc, result.path, truncated_path,
                    result.query, conn
                ))

        return Response(
            Status.SUCCESS, "text/plain",
            str(result).encode()
        )
