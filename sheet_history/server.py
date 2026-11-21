"""Loopback-only HTTP server: JSON API plus an exact static allowlist."""

import json
import os
import re
import socket
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import sheet as sh
from .storage import ConflictError, LimitError, NotFoundError, Storage

MAX_BODY = 65536
MAX_DRAIN = 1024 * 1024
HOST = "127.0.0.1"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# URL path -> (file name inside STATIC_DIR, content type). Nothing else is served.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

SECURITY_HEADERS = (
    (
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'",
    ),
    ("X-Content-Type-Options", "nosniff"),
    ("Cache-Control", "no-store"),
    ("Referrer-Policy", "no-referrer"),
)

SHEET_PATH_RE = re.compile(r"\A/api/v1/sheets/([0-9]{1,18})\Z")
LENGTH_RE = re.compile(r"\A[0-9]{1,10}\Z")

STATUS_CODES = {
    400: "invalid",
    403: "forbidden_origin",
    404: "not_found",
    405: "method_not_allowed",
    411: "invalid",
    413: "too_large",
    415: "unsupported_media_type",
    422: "limit_reached",
}


class ApiError(Exception):
    def __init__(self, status, code, message, extra=None, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra
        self.headers = headers


def _reject_constant(name):
    raise ValueError("invalid JSON constant")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SheetHistory"
    sys_version = ""
    timeout = 10
    _body_consumed = True  # class default so early parser errors can respond safely

    # ---- plumbing -------------------------------------------------------
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        status = code if code in STATUS_CODES else 400
        try:
            self._send_error_json(
                status, STATUS_CODES.get(status, "invalid"), "Request could not be handled"
            )
        except OSError:
            pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def _dispatch(self, method):
        self.close_connection = True
        self._body_consumed = method not in ("POST", "PUT")
        try:
            try:
                self._handle(method)
            except ApiError as exc:
                self._send_error_json(exc.status, exc.code, exc.message, exc.extra, exc.headers)
            except sh.ValidationError as exc:
                self._send_error_json(400, "invalid", str(exc))
            except NotFoundError:
                self._send_error_json(404, "not_found", "Sheet not found")
            except LimitError as exc:
                self._send_error_json(422, "limit_reached", str(exc))
            except ConflictError as exc:
                self._send_error_json(
                    409,
                    "conflict",
                    "The sheet changed on the server (revision %d). Nothing was merged."
                    % exc.current["revision"],
                    {"current": exc.current},
                )
        except OSError:
            self.close_connection = True  # client went away or timed out
        except Exception:  # noqa: BLE001 - last-resort handler, generic message only
            traceback.print_exc(file=sys.stderr)
            try:
                self._send_error_json(500, "internal", "Internal server error")
            except OSError:
                pass

    # ---- checks ---------------------------------------------------------
    def _handle(self, method):
        hosts = self.server.allowed_hosts
        host_values = self.headers.get_all("Host") or []
        if len(host_values) != 1 or host_values[0] not in hosts:
            raise ApiError(403, "forbidden_origin", "Host not allowed")
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        handlers = self._route(path)
        if handlers is None:
            raise ApiError(404, "not_found", "Not found")
        if method not in handlers:
            raise ApiError(
                405,
                "method_not_allowed",
                "Method not allowed",
                headers={"Allow": ", ".join(sorted(handlers))},
            )
        if method in ("POST", "PUT"):
            origins = self.headers.get_all("Origin")
            if origins is not None:
                allowed = {"http://" + h for h in hosts}
                if len(origins) != 1 or origins[0] not in allowed:
                    raise ApiError(403, "forbidden_origin", "Origin not allowed")
        handlers[method]()

    def _route(self, path):
        if path in STATIC_FILES:
            return {"GET": lambda: self._static(path)}
        if path == "/api/v1/health":
            return {"GET": lambda: self._send_json(200, {"status": "ok", "schema": 1})}
        if path == "/api/v1/sheets":
            return {"GET": self._list, "POST": self._create}
        m = SHEET_PATH_RE.match(path)
        if m:
            sheet_id = int(m.group(1))
            return {
                "GET": lambda: self._send_json(200, self.server.storage.get_sheet(sheet_id)),
                "PUT": lambda: self._put(sheet_id),
            }
        return None

    # ---- endpoints ------------------------------------------------------
    def _static(self, url_path):
        name, ctype = STATIC_FILES[url_path]
        try:
            data = (STATIC_DIR / name).read_bytes()
        except OSError:
            raise ApiError(404, "not_found", "Not found")
        self._send(200, data, ctype)

    def _list(self):
        self._send_json(200, {"sheets": self.server.storage.list_sheets()})

    def _create(self):
        obj = self._read_json_object()
        if set(obj) != {"title"}:
            raise sh.ValidationError("body must contain exactly: title")
        self._send_json(201, self.server.storage.create_sheet(obj["title"]))

    def _put(self, sheet_id):
        obj = self._read_json_object()
        if set(obj) != {"base_revision", "title", "cells"}:
            raise sh.ValidationError("body must contain exactly: base_revision, title, cells")
        base = obj["base_revision"]
        if isinstance(base, bool) or not isinstance(base, int) or not 1 <= base <= 2**62:
            raise sh.ValidationError("base_revision must be a positive integer")
        sheet = self.server.storage.update_sheet(sheet_id, base, obj["title"], obj["cells"])
        self._send_json(200, sheet)

    # ---- request body ---------------------------------------------------
    def _read_json_object(self):
        media = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
        if self.headers.get("Transfer-Encoding") is not None:
            raise ApiError(411, "invalid", "Content-Length is required")
        length = self.headers.get("Content-Length")
        if length is None:
            raise ApiError(411, "invalid", "Content-Length is required")
        if not LENGTH_RE.match(length):
            raise ApiError(400, "invalid", "Invalid Content-Length")
        n = int(length)
        if n > MAX_BODY:
            raise ApiError(413, "too_large", "Body exceeds %d bytes" % MAX_BODY)
        data = self.rfile.read(n) if n else b""
        self._body_consumed = True
        if len(data) != n:
            raise ApiError(400, "invalid", "Incomplete body")
        try:
            obj = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ApiError(400, "invalid", "Body is not valid UTF-8 JSON")
        if not isinstance(obj, dict):
            raise ApiError(400, "invalid", "Body must be a JSON object")
        return obj

    def _drain(self):
        """Discard an unread request body so closing does not reset the client."""
        if self._body_consumed:
            return
        self._body_consumed = True
        try:
            length = self.headers.get("Content-Length", "")
            if not LENGTH_RE.match(length):
                return
            remaining = int(length)
            if remaining > MAX_DRAIN:
                return
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, AttributeError):
            pass

    # ---- responses ------------------------------------------------------
    def _send(self, status, body, content_type, headers=None):
        self._drain()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in SECURITY_HEADERS:
            self.send_header(key, value)
        self.send_header("Connection", "close")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status, obj, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", headers)

    def _send_error_json(self, status, code, message, extra=None, headers=None):
        payload = {"error": {"code": code, "message": message}}
        if extra:
            payload.update(extra)
        self._send_json(status, payload, headers)


class SheetServer(ThreadingHTTPServer):
    daemon_threads = True
    # POSIX: SO_REUSEADDR lets a restart rebind during TIME_WAIT.
    # Windows: SO_REUSEADDR would allow port sharing, so bind exclusively.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(data_dir, port=0):
    """Open storage and bind 127.0.0.1:port. Raises StorageError or OSError."""
    storage = Storage(data_dir)
    server = SheetServer((HOST, port), Handler)
    bound = server.server_address[1]
    server.storage = storage
    server.allowed_hosts = frozenset(("127.0.0.1:%d" % bound, "localhost:%d" % bound))
    return server
