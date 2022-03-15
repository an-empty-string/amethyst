from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Status(Enum):
    INPUT = 10
    SENSITIVE_INPUT = 11
    SUCCESS = 20
    REDIRECT_TEMPORARY = 30
    REDIRECT_PERMANENT = 31
    TEMPORARY_FAILURE = 40
    SERVER_UNAVAILABLE = 41
    CGI_ERROR = 42
    PROXY_ERROR = 43
    SLOW_DOWN = 44
    PERMANENT_FAILURE = 50
    NOT_FOUND = 51
    GONE = 52
    PROXY_REQUEST_REFUSED = 53
    BAD_REQUEST = 59
    CLIENT_CERTIFICATE_REQUIRED = 60
    CERTIFICATE_NOT_AUTHORIZED = 61
    CERTIFICATE_NOT_VALID = 62

    def is_success(self):
        return 20 <= self.value <= 29


@dataclass
class Response:
    status_code: Status
    meta: str
    content: Optional[bytes] = None
