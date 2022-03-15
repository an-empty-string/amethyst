from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .server import Server


@dataclass
class Connection:
    server: Server
    peer_addr: str
    peer_cert: Optional[bytes] = None


@dataclass
class Context:
    host: str
    orig_path: str
    path: str
    query: Optional[str]
    conn: Connection

    data: Dict[str, Any] = field(default_factory=dict)
