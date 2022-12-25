import asyncio
import configparser
import enum
import logging
import mimetypes
import os
import os.path
import subprocess

from .response import Status, Response
from .request import Context

from dataclasses import dataclass
from typing import (
    Callable,
    Awaitable,
    List,
    NamedTuple,
    Union,
    Literal,
    Tuple,
    Dict,
    Optional,
)

Resource = Callable[[Context], Awaitable[Response]]


class InvalidPathException(Exception):
    pass


class FileType(enum.Enum):
    FILE = "file"
    DIRECTORY = "directory"


class PathInfo(NamedTuple):
    original_path_components: List[str]
    path: str
    extra: str
    file_type: FileType


@dataclass
class Meta:
    cgi: Optional[bool] = None
    autoindex: Optional[bool] = None
    index: Optional[str] = None
    mime_type: Optional[str] = None

    def merge_from(self, other: "Meta"):
        for prop in self.__dict__:
            if getattr(self, prop) is None:
                setattr(self, prop, getattr(other, prop))


DEFAULT_META = Meta(cgi=False, autoindex=False, index="index.gmi", mime_type=None)


class FilesystemResource:
    def __init__(
        self,
        root,
        cgi=False,
        mime_types=None,
        default_mime_type="application/octet-stream",
    ):

        self.log = logging.getLogger("amethyst.resource.FilesystemResource")
        self.cgi_log = logging.getLogger("amethyst.resource.FilesystemResource.cgi")

        self.cgi = cgi

        self.default_mime_type = default_mime_type
        self.root = os.path.abspath(root)

    def send_file(self, filename: str, mime_type: Optional[str] = None) -> Response:
        if mime_type is None:
            mime_type = self.default_mime_type

            candidate_mime_type, _encoding = mimetypes.guess_type(
                filename, strict=False
            )
            self.log.debug(f"mimetypes says {filename=} has {candidate_mime_type=}")
            if candidate_mime_type is not None:
                mime_type = candidate_mime_type

        with open(filename, "rb") as f:
            contents = f.read()

        self.log.debug(
            f"Sending file {filename} ({len(contents)} bytes) as {mime_type}"
        )

        return Response(Status.SUCCESS, mime_type, contents)

    async def do_cgi(self, ctx: Context, path_info: PathInfo) -> Response:
        # TODO: signal client certificates here
        env = {
            "GATEWAY_INTERFACE": "CGI/1.1",
            "QUERY_STRING": ctx.query or "",
            "REMOTE_ADDR": ctx.conn.peer_addr[0],
            "SCRIPT_NAME": "/".join([""] + path_info.original_path_components),
            "PATH_INFO": path_info.extra,
            "SERVER_NAME": ctx.host,
            "SERVER_PORT": str(ctx.conn.server.config.port),
            "SERVER_PROTOCOL": "Gemini/0.16.0",
            "SERVER_SOFTWARE": "Amethyst",
        }

        self.log.debug(f"Starting CGI script {path_info.path}")

        proc = await asyncio.create_subprocess_exec(
            path_info.path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=(os.environ | env),
        )

        stdout, stderr = await proc.communicate()

        self.cgi_log.info(
            f"{path_info.path} returned {proc.returncode} "
            f"(stdout bytes {len(stdout)}, "
            f"stderr bytes {len(stderr)})"
        )

        if proc.returncode != 0:
            self.cgi_log.warn("Script stderr:")
            self.cgi_log.warn(stderr)
            return Response(
                Status.CGI_ERROR, f"Script returned {proc.returncode} (see logs)"
            )

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

    # Flow should be:
    # - Find what file (or directory) we are actually processing
    # - Find the appropriate meta file, if one exists
    # - Do dirindex processing if it's a directory and that's allowed
    # - Determine if the file is CGI-eligible and process as CGI
    # - Otherwise, serve the file

    def _find_path(self, ctx: Context) -> PathInfo:
        normalized: List[str] = []

        for component in ctx.path.strip("/").split("/"):
            if component == ".":
                continue

            elif component == "..":
                if not normalized:
                    raise InvalidPathException()

                normalized.pop()

            else:
                normalized.append(component)

        logging.debug(f"find_path: {normalized=}")

        for up_to in range(len(normalized) + 1, 0, -1):
            original_path_components = normalized[:up_to]
            path = os.path.join(self.root, *normalized[:up_to])
            extra = "/".join(normalized[up_to:])

            logging.debug(f"find_path: test {path=}")

            if os.path.exists(path):
                break

        file_type = FileType.FILE
        if os.path.isdir(path):
            file_type = FileType.DIRECTORY

        return PathInfo(original_path_components, path, extra, file_type)

    @staticmethod
    def _find_meta(info: PathInfo) -> Tuple[Optional[str], List[str]]:
        if info.file_type == FileType.DIRECTORY:
            dir_name = info.path
        elif info.file_type == FileType.FILE:
            dir_name = os.path.dirname(info.path)

        dir_inherited_meta_filenames = []

        exact_meta_candidate = os.path.join(dir_name, ".meta")
        exact_meta: Optional[str] = None
        if os.path.exists(exact_meta_candidate):
            exact_meta = exact_meta_candidate

        # Walk up the tree until we run out of directories
        for component in info.original_path_components:
            # Guaranteed that there's no / at the end of the dir_name
            dir_name = dir_name[: dir_name.rindex("/")]

            candidate = os.path.join(dir_name, ".meta")
            if os.path.exists(candidate):
                dir_inherited_meta_filenames.append(candidate)

        # order returned in the order we should load them (last wins)
        return exact_meta, dir_inherited_meta_filenames[::-1]

    @classmethod
    def _load_meta(cls, info: PathInfo) -> Dict[str, Meta]:
        def _load_inner(f: str):
            result = {}

            p = configparser.ConfigParser()
            p.read(f)

            result["."] = Meta()

            for sec in p.sections():
                result[sec] = Meta()

                # XXX: Load dynamically later?
                result[sec].cgi = p.getboolean(sec, "cgi", fallback=None)
                result[sec].autoindex = p.getboolean(sec, "autoindex", fallback=None)

                # this is to satisfy the typechecker
                index_candidate = p.get(sec, "index", fallback=None)
                if index_candidate is not None:
                    result[sec].index = str(index_candidate)

                mime_type_candidate = p.get(sec, "mime", fallback=None)
                if mime_type_candidate is not None:
                    result[sec].mime_type = str(mime_type_candidate)

            return result

        exact_meta_file, inherited_meta_files = cls._find_meta(info)

        inherited_meta = Meta()
        for filename in inherited_meta_files:
            inherited_meta.merge_from(_load_inner(filename)["."])

        exact_metas = {".": Meta()}

        if exact_meta_file is not None:
            exact_metas.update(_load_inner(exact_meta_file))

        exact_metas["."].merge_from(inherited_meta)

        for key, meta in exact_metas.items():
            meta.merge_from(DEFAULT_META)

        return exact_metas

    async def __call__(self, ctx: Context) -> Response:
        try:
            path_info = self._find_path(ctx)
            logging.debug(f"{path_info=}")
        except InvalidPathException:
            self.log.warn(f"_find_path threw for invalid path {ctx.path=}!")
            return Response(Status.BAD_REQUEST, "Invalid path")

        # this should never happen - just writing defensively
        if not (path_info.path + os.sep).startswith(self.root + os.sep):
            self.log.warn(f"Tried to handle from disallowed path {path_info.path=}!")
            return Response(Status.BAD_REQUEST, "Invalid path")

        meta = self._load_meta(path_info)
        dir_meta = meta["."]

        logging.debug(f"{dir_meta=}")

        if path_info.file_type == FileType.DIRECTORY:
            # do dirindex processing if needed
            index = dir_meta.index
            if index is None:
                # should never happen
                index = "index.gmi"

            filename = os.path.join(path_info.path, index)
            if os.path.exists(filename):
                # rewrite path info for index
                path_info = PathInfo(
                    original_path_components=path_info.original_path_components
                    + [os.path.basename(filename)],
                    path=filename,
                    extra="",
                    file_type=FileType.FILE,
                )

            # else handle autoindex right now
            elif dir_meta.autoindex:
                self.log.debug(
                    f"Performing directory listing of {path_info.path} for request to {ctx.orig_path}"
                )

                lines = [f"# Directory listing of {ctx.orig_path}", ""]

                for filename in sorted(os.listdir(path_info.path)):
                    if os.path.isdir(os.path.join(path_info.path, filename)):
                        lines.append(f"=> {filename}/")
                    elif filename != ".meta":
                        lines.append(f"=> {filename}")

                listing = "\n".join(lines).encode()
                return Response(Status.SUCCESS, "text/gemini", listing)

            else:
                self.log.debug(f"{path_info.path} not found")
                return Response(
                    Status.NOT_FOUND, f"{ctx.orig_path} was not found on this server."
                )

        # .meta itself can never ever be processed as a file
        if path_info.original_path_components[-1] == ".meta":
            logging.warn(
                "Directly accessing .meta is not supported and will always return NOT_FOUND"
            )
            return Response(
                Status.NOT_FOUND, f"{ctx.orig_path} was not found on this server."
            )

        file_meta = meta.get(path_info.original_path_components[-1])
        if file_meta is None:
            logging.debug("file_meta is falling back to dir_meta")
            file_meta = dir_meta

        logging.debug(f"{file_meta=}")

        # _not_ elif, since we might've rewritten path_info above
        if path_info.file_type == FileType.FILE and os.path.isfile(path_info.path):
            if self.cgi and file_meta.cgi and os.access(path_info.path, os.X_OK):
                return await self.do_cgi(ctx, path_info)

            return self.send_file(path_info.path, mime_type=file_meta.mime_type)

        self.log.debug(f"{path_info.path} not found")
        return Response(
            Status.NOT_FOUND, f"{ctx.orig_path} was not found on this server."
        )
