from amethyst.handler import GenericHandler
from amethyst.resource import FilesystemResource
from amethyst.server import Server
from amethyst.tls import make_context

Server(
    ssl_context=make_context("cert.pem", "key.pem"),
    url_handler=GenericHandler({"localhost": {
        "/": FilesystemResource(
            "/home/tris/gemtest", directory_indexing=True, cgi=True
        ),
        "/cool/beans/": FilesystemResource(
            "/home/tris/gemtest/coolbeans.gmi"
        )
    }})
).start()
