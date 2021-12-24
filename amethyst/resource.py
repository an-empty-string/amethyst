import asyncio
import os
import os.path
import subprocess

from .mime import default_mime_types
from .response import Status, Response


class FilesystemResource():
    def __init__(self, base_path,
                 index_files=None,
                 directory_indexing=False,
                 cgi=False,
                 mime_types=None,
                 default_mime_type="application/octet-stream"):

        self.directory_indexing = directory_indexing
        self.cgi = cgi

        self.index_files = index_files
        if self.index_files is None:
            self.index_files = ["index.gmi"]

        self.mime_types = mime_types
        if self.mime_types is None:
            self.mime_types = default_mime_types

        self.postprocessors = None
        if self.postprocessors is None:
            self.postprocessors = {}

        self.default_mime_type = default_mime_type
        self.base_path = os.path.abspath(base_path)

    def send_file(self, filename):
        mime_type = self.default_mime_type
        for ext in sorted(self.mime_types, key=len):
            if filename.lower().endswith(ext.lower()):
                mime_type = self.mime_types[ext]

        with open(filename, "rb") as f:
            contents = f.read()

        return Response(Status.SUCCESS, mime_type, contents)

    async def do_cgi(self, ctx, filename):
        # TODO: signal client certificates here
        env = {
            "GATEWAY_INTERFACE": "CGI/1.1",
            "QUERY_STRING": ctx.query or "",
            "REMOTE_ADDR": ctx.conn.peer_addr[0],
            "SCRIPT_NAME": ctx.orig_path,
            "SERVER_NAME": ctx.host,
            "SERVER_PORT": str(ctx.conn.my_port),
            "SERVER_PROTOCOL": "Gemini/0.16.0",
            "SERVER_SOFTWARE": "Amethyst",
        }

        proc = await asyncio.create_subprocess_exec(
            filename, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=(os.environ | env)
        )

        stdout, stderr = await proc.communicate()

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
                if value.isnumeric() and int(value) in status:
                    status = Status[int(value)]
            elif key == "location":
                return Response(Status.REDIRECT_TEMPORARY, value)

        result = b"\n".join(lines)
        if line:
            result = line + b"\n" + result

        return Response(status, content_type, result)

    async def __call__(self, ctx):
        full_path = os.path.abspath(os.path.join(self.base_path, ctx.path))

        if os.path.isdir(full_path):
            if not (full_path + os.sep).startswith(self.base_path + os.sep):
                return Response(Status.BAD_REQUEST, "Invalid path")

            for filename in self.index_files:
                filename = os.path.join(full_path, filename)
                if os.path.exists(filename):
                    return self.send_file(filename)

            if self.directory_indexing:
                lines = [f"# Directory listing of {ctx.orig_path}", ""]

                for filename in sorted(os.listdir(full_path)):
                    if os.path.isdir(os.path.join(full_path, filename)):
                        lines.append(f"=> {filename}/")
                    else:
                        lines.append(f"=> {filename}")

                listing = "\n".join(lines).encode()
                return Response(Status.SUCCESS, "text/gemini", listing)

        elif os.path.isfile(full_path):
            if full_path != self.base_path and not full_path.startswith(self.base_path + os.sep):
                return Response(Status.BAD_REQUEST, "Invalid path")

            if self.cgi and os.access(full_path, os.X_OK):
                return await self.do_cgi(ctx, full_path)

            return self.send_file(full_path)

        return Response(Status.NOT_FOUND,
                        f"{ctx.orig_path} was not found on this server.")
