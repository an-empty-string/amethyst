from .config import Config
from .mime import init_mime_types
from .server import Server

import asyncio
import json
import logging
import signal
import sys

log = logging.getLogger("amethyst.kindergarten")


class ServerManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = Config.from_config(self._get_config())
        self.server = Server(self.config)

    def _get_config(self):
        with open(self.config_path) as f:
            return json.load(f)

    def reconfigure(self):
        log.info("Received HUP; reloading configuration.")

        self.config.load(self._get_config())

        for host in self.config.hosts:
            host.tls.clear_context_cache()

    def start(self):
        # XXX: Not sure a global MIME type configuration is "correct" here.
        # Perhaps Server should be responsible for its own MimeTypes module?
        init_mime_types()

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGHUP, self.reconfigure)

        log.info(f"Starting server on port {self.config.port}")

        loop.run_until_complete(self.server.server)
        loop.run_forever()


def cli():
    logging.basicConfig(level=logging.DEBUG)
    ServerManager(sys.argv[1]).start()


if __name__ == "__main__":
    cli()
