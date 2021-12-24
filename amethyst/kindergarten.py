from amethyst.handler import GenericHandler
from amethyst.resource import FilesystemResource
from amethyst.server import Server
from amethyst.tls import make_context, update_certificate

import configparser
import logging
import sys

log = logging.getLogger("amethyst.kindergarten")


def create_server(config):
    hosts = config.get("global", "hosts").split()

    ssl_cert = config.get("global", "ssl_cert")
    ssl_key = config.get("global", "ssl_key")

    update_certificate(ssl_cert, ssl_key, hosts)
    ssl_context = make_context(ssl_cert, ssl_key)

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

    log.info(f"Building server for {len(hosts)} hosts and {len(path_map)} paths")

    return Server(
        ssl_context, url_handler,
        port=config.getint("global", "port", fallback=1965)
    )


def create_server_from_config(path):
    config = configparser.ConfigParser()
    config.read(path)
    return create_server(config)


def cli():
    logging.basicConfig(level=logging.INFO)
    create_server_from_config(sys.argv[1]).start()
