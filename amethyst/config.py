import datetime
import ssl

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .handler import GenericHandler, Handler
from .resource import Resource
from .resource_registry import registry

import os


@dataclass
class TLSConfig():
    host: str
    auto: bool = False
    cert_path: Optional[str] = None
    key_path: Optional[str] = None

    _context_cache: Optional[Tuple[datetime.datetime, ssl.SSLContext]] = None

    @classmethod
    def from_config(cls, host, cfg):
        o = cls(host)

        if cfg == "auto":
            cfg = {
                "auto": True
            }

        state = os.getenv("STATE_DIRECTORY", ".")

        o.auto = cfg.get("auto", False)
        o.cert_path = cfg.get("cert_path", 
            os.path.join(state, f"{host}.cert.pem"))
        o.key_path = cfg.get("key_path", 
            os.path.join(state, f"{host}.key.pem"))

        return o

    def clear_context_cache(self):
        self._context_cache = None

    def get_ssl_context(self):
        from . import tls
        if self._context_cache is not None:
            expires, context = self._context_cache

            if expires is None or expires > datetime.datetime.now():
                return context

        elif self.auto:
            expires = tls.update_certificate(self.cert_path, self.key_path, [self.host])
        else:
            # We want to keep using a manually-specified certificate forever
            # or at least until the server is restarted / HUPed.
            expires = None

        context = tls.make_context(self.cert_path, self.key_path)

        self._context_cache = expires, context
        return context


@dataclass
class HostConfig():
    host: str
    tls: TLSConfig
    path_map: Dict[str, Resource]

    @classmethod
    def _construct_resource(cls, cfg) -> Resource:
        resource_type = cfg.pop("type", "filesystem")
        return registry[resource_type](**cfg)


    @classmethod
    def from_config(cls, cfg):
        host = cfg["name"]
        tls = TLSConfig.from_config(host, cfg["tls"])
        path_map = {
            path: cls._construct_resource(config)
            for path, config in cfg["paths"].items()
        }

        return cls(host, tls, path_map)


@dataclass
class Config():
    hosts: List[HostConfig]
    handler: Handler
    port: int = 1965

    def load(self, cfg):
        self.hosts =[
            HostConfig.from_config(host)
            for host in cfg.get("hosts", [])
        ]
 
        if not self.hosts:
            raise ValueError("Server can't run without any hosts!")

        self.handler = GenericHandler({
            host.host: host.path_map for host in self.hosts
        })

    @classmethod
    def from_config(cls, cfg):
        o = cls([], None, cfg.get("port", 1965))
        o.load(cfg)
        return o