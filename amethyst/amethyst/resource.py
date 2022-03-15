import asyncio
import logging
import os
import os.path
import subprocess

from .mime import default_mime_types
from .response import Status, Response
from .request import Context

from typing import Callable, Awaitable

Resource = Callable[[Context], Awaitable[Response]]


class FilesystemResource:
    def __init__(
        self,
        root,
        autoindex=False,
        cgi=False,
        mime_types=None,
        default_mime_type="application/octet-stream",
    ):

        self.log = logging.getLogger("amethyst.resource.FilesystemResource")
        self.cgi_log = logging.getLogger("amethyst.resource.FilesystemResource.cgi")

        self.autoindex = autoindex
        self.cgi = cgi

        self.index_files = ["index.gmi"]

        self.mime_types = mime_types
        if self.mime_types is None:
            self.mime_types = default_mime_types

        self.postprocessors = None
        if self.postprocessors is None:
            self.postprocessors = {}

        self.default_mime_type = default_mime_type
        self.root = os.path.abspath(root)

    def send_file(self, filename: str) -> Response:
        mime_type = self.default_mime_type
        for ext in sorted(self.mime_types, key=len):
            if filename.lower().endswith(ext.lower()):
                mime_type = self.mime_types[ext]

        with open(filename, "rb") as f:
            contents = f.read()

        self.log.debug(
            f"Sending file {filename} ({len(contents)} bytes) as {mime_type}"
        )

        return Response(Status.SUCCESS, mime_type, contents)

    async def do_cgi(self, ctx: Context, filename: str) -> Response:
        # TODO: signal client certificates here
        env = {
            "GATEWAY_INTERFACE": "CGI/1.1",
            "QUERY_STRING": ctx.query or "",
            "REMOTE_ADDR": ctx.conn.peer_addr[0],
            "SCRIPT_NAME": ctx.orig_path,
            "SERVER_NAME": ctx.host,
            "SERVER_PORT": str(ctx.conn.server.config.port),
            "SERVER_PROTOCOL": "Gemini/0.16.0",
            "SERVER_SOFTWARE": "Amethyst",
        }

        self.log.debug(f"Starting CGI script {filename}")

        proc = await asyncio.create_subprocess_exec(
            filename,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=(os.environ | env),
        )

        stdout, stderr = await proc.communicate()

        self.cgi_log.info(
            f"{filename} returned {proc.returncode} "
            f"(stdout bytes {len(stdout)}, "
            f"stderr bytes {len(stderr)})"
        )

        if proc.returncode != 0:
            return Response(Status.CGI_ERROR, f"Script returned {proc.returncode}")

        content_type = "text/gemini"
        status = Status.SUCCESS

        lines = iter(stdout.split(b"\n"))

        for line in lines:
            if not line or b":" not in line:
                break

            key, value = line.decode().strip().split(":", maxsplit=1)
            key, value = key.strip().lower(), value.strip()

            if key == "content-type":
                content_type = value
            elif key == "status":
                try:
                    status = Status(int(value))
                except ValueError:
                    pass
            elif key == "location":
                return Response(Status.REDIRECT_TEMPORARY, value)

        result = b"\n".join(lines)
        if line:
            result = line + b"\n" + result

        return Response(status, content_type, result)

    async def __call__(self, ctx: Context) -> Response:
        full_path = os.path.abspath(os.path.join(self.root, ctx.path.lstrip("/")))

        if os.path.isdir(full_path):
            if not (full_path + os.sep).startswith(self.root + os.sep):
                self.log.warn(f"Tried to handle from disallowed path {full_path}!")
                return Response(Status.BAD_REQUEST, "Invalid path")

            for filename in self.index_files:
                filename = os.path.join(full_path, filename)
                if os.path.exists(filename):
                    self.log.debug(
                        f"Sending index file {filename} for request to {ctx.orig_path}"
                    )
                    return self.send_file(filename)

            if self.autoindex:
                self.log.debug(
                    f"Performing directory listing of {full_path} for request to {ctx.orig_path}"
                )

                lines = [f"# Directory listing of {ctx.orig_path}", ""]

                for filename in sorted(os.listdir(full_path)):
                    if os.path.isdir(os.path.join(full_path, filename)):
                        lines.append(f"=> {filename}/")
                    else:
                        lines.append(f"=> {filename}")

                listing = "\n".join(lines).encode()
                return Response(Status.SUCCESS, "text/gemini", listing)

        elif os.path.isfile(full_path):
            if full_path != self.root and not full_path.startswith(self.root + os.sep):
                self.log.warn(f"Tried to handle from disallowed path {full_path}!")
                return Response(Status.BAD_REQUEST, "Invalid path")

            if self.cgi and os.access(full_path, os.X_OK):
                return await self.do_cgi(ctx, full_path)

            return self.send_file(full_path)

        self.log.debug("{full_path} not found")
        return Response(
            Status.NOT_FOUND, f"{ctx.orig_path} was not found on this server."
        )
