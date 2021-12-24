from amethyst.handler import GenericHandler
from amethyst.resource import FilesystemResource
from amethyst.server import Server
from amethyst.tls import make_context

import configparser
import sys


def create_server(config):
    hosts = config.get("global", "hosts").split()

    ssl_context = make_context(
        config.get("global", "ssl_cert"),
        config.get("global", "ssl_key"),
    )

    path_map = {}
    for path in config.sections():
        if path == "global":
            continue

        path_map[path] = FilesystemResource(
            config.get(path, "root"),
            index_files=config.get(path, "index", fallback="index.gmi").split(),
            directory_indexing=config.getboolean(path, "autoindex"),
            cgi=config.getboolean(path, "cgi"),
        )

    url_handler = GenericHandler({host: path_map for host in hosts})

    return Server(
        ssl_context, url_handler,
        port=config.getint("global", "port", fallback=1965)
    )


def create_server_from_config(path):
    config = configparser.ConfigParser()
    config.read(path)
    return create_server(config)


def cli():
    create_server_from_config(sys.argv[1]).start()
