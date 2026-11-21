"""Shared helpers: disposable data dir, threaded server on port 0, raw HTTP client."""

import http.client
import json
import os
import tempfile
import threading
import unittest

from sheet_history.server import make_server


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers}
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    @property
    def error_code(self):
        return self.json()["error"]["code"]


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = os.path.join(tmp.name, "data")
        self.server = None
        self.start()

    def start(self):
        self.server = make_server(self.data_dir, 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        if self.server is None:
            return
        server, self.server = self.server, None
        server.shutdown()
        server.server_close()
        self.thread.join(5)

    def request(self, method, path, body=None, json_body=None, headers=None,
                host=None, content_type="application/json"):
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        hdrs = {}
        if method in ("POST", "PUT") and content_type is not None:
            hdrs["Content-Type"] = content_type
        if body is not None:
            hdrs["Content-Length"] = str(len(body))
        hdrs.update(headers or {})
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", host if host is not None else "127.0.0.1:%d" % self.port)
            for key, value in hdrs.items():
                if value is not None:
                    conn.putheader(key, value)
            conn.endheaders(body)
            resp = conn.getresponse()
            return Response(resp.status, resp.getheaders(), resp.read())
        finally:
            conn.close()

    def create(self, title="Sheet"):
        resp = self.request("POST", "/api/v1/sheets", json_body={"title": title})
        self.assertEqual(resp.status, 201, resp.body)
        return resp.json()

    def put(self, sheet_id, base, title, cells):
        return self.request(
            "PUT", "/api/v1/sheets/%d" % sheet_id,
            json_body={"base_revision": base, "title": title, "cells": cells},
        )
