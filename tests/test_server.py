import json
import re
import threading
import unittest
from contextlib import redirect_stderr
from io import StringIO

from tests.support import ServerTestCase

API = "/api/v1/sheets"

REQUIRED_IDS = [
    "sheet-title", "save-btn", "new-btn", "load-sample-btn", "project-list",
    "status", "conflict", "conflict-reload", "conflict-retry", "grid",
]


class BasicApiTests(ServerTestCase):
    def test_bound_to_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_health(self):
        resp = self.request("GET", "/api/v1/health")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.json(), {"status": "ok", "schema": 1})
        self.assertTrue(resp.headers["content-type"].startswith("application/json"))

    def test_query_string_ignored_for_routing(self):
        self.assertEqual(self.request("GET", "/api/v1/health?x=1").status, 200)

    def test_empty_list_then_create(self):
        self.assertEqual(self.request("GET", API).json(), {"sheets": []})
        sheet = self.create("My sheet")
        self.assertEqual(sheet["revision"], 1)
        self.assertEqual(sheet["cells"], {})
        listing = self.request("GET", API).json()["sheets"]
        self.assertEqual([(s["id"], s["title"], s["revision"]) for s in listing],
                         [(1, "My sheet", 1)])

    def test_get_missing_and_malformed_ids(self):
        for path in (API + "/99", API + "/abc", API + "/", API + "/-1", API + "/1/x",
                     API + "/" + "9" * 40):
            with self.subTest(path=path):
                resp = self.request("GET", path)
                self.assertEqual(resp.status, 404)
                self.assertEqual(resp.error_code, "not_found")

    def test_put_missing_sheet_404(self):
        resp = self.put(42, 1, "t", {})
        self.assertEqual(resp.status, 404)
        self.assertEqual(resp.error_code, "not_found")

    def test_smoke_formula_flow(self):
        sheet = self.create("S")
        resp = self.put(sheet["id"], 1, "S", {"A1": "3", "B1": "4", "C1": "=A1+B1"})
        self.assertEqual(resp.status, 200)
        body = resp.json()
        self.assertEqual(body["revision"], 2)
        self.assertEqual(body["computed"], {"C1": "7"})
        self.assertEqual(body["cells"]["C1"], "=A1+B1")
        self.assertEqual((body["rows"], body["cols"]), (8, 6))

    def test_value_error_and_nested_over_http(self):
        sheet = self.create("S")
        body = self.put(sheet["id"], 1, "S", {
            "A1": "abc", "B1": "1", "C1": "=A1+B1", "D1": "=C1+B1", "E1": "=E1+E1",
            "F1": "=1+2",
        }).json()
        self.assertEqual(body["computed"],
                         {"C1": "#VALUE!", "D1": "#NESTED", "E1": "#NESTED"})
        self.assertEqual(body["cells"]["F1"], "=1+2")

    def test_literal_leading_chars_stored_verbatim(self):
        sheet = self.create("S")
        cells = {"A1": "=1+2", "B1": "+5x", "C1": "-q", "D1": "@sum"}
        body = self.put(sheet["id"], 1, "S", cells).json()
        self.assertEqual(body["cells"], cells)
        self.assertEqual(body["computed"], {})

    def test_utf8_round_trip(self):
        text = "héllo ✓ 日本"
        sheet = self.create(text)
        resp = self.put(sheet["id"], 1, text, {"A1": text, "B1": "😀"})
        self.assertEqual(resp.status, 200)
        raw = self.request("GET", "%s/%d" % (API, sheet["id"])).body
        self.assertIn(text.encode("utf-8"), raw)  # not \u-escaped
        got = json.loads(raw.decode("utf-8"))
        self.assertEqual(got["title"], text)
        self.assertEqual(got["cells"], {"A1": text, "B1": "😀"})

    def test_content_type_with_charset_accepted(self):
        resp = self.request("POST", API, json_body={"title": "x"},
                            content_type="application/json; charset=utf-8")
        self.assertEqual(resp.status, 201)

    def test_omitted_cells_cleared_and_empty_dropped(self):
        sheet = self.create("S")
        self.put(sheet["id"], 1, "S", {"A1": "1", "B1": "2"})
        body = self.put(sheet["id"], 2, "S", {"B1": "5", "C1": ""}).json()
        self.assertEqual(body["cells"], {"B1": "5"})

    def test_restart_persistence(self):
        sheet = self.create("Persist")
        self.put(sheet["id"], 1, "Persist", {"A1": "3", "B1": "4", "C1": "=A1+B1"})
        before = self.request("GET", "%s/1" % API).json()
        self.stop()
        self.start()
        after = self.request("GET", "%s/1" % API).json()
        self.assertEqual(after, before)
        self.assertEqual(after["computed"], {"C1": "7"})
        self.assertEqual(self.request("GET", API).json()["sheets"][0]["revision"], 2)


class ConflictTests(ServerTestCase):
    def test_stale_put_409_with_current_and_no_change(self):
        sheet = self.create("S")
        sid = sheet["id"]
        self.assertEqual(self.put(sid, 1, "S", {"A1": "server"}).status, 200)
        resp = self.put(sid, 1, "mine", {"A1": "mine"})
        self.assertEqual(resp.status, 409)
        body = resp.json()
        self.assertEqual(body["error"]["code"], "conflict")
        self.assertEqual(body["current"]["revision"], 2)
        self.assertEqual(body["current"]["cells"], {"A1": "server"})
        self.assertEqual(body["current"]["title"], "S")
        now = self.request("GET", "%s/%d" % (API, sid)).json()
        self.assertEqual((now["revision"], now["cells"]), (2, {"A1": "server"}))

    def test_explicit_retry_with_current_revision(self):
        sid = self.create("S")["id"]
        self.put(sid, 1, "S", {"A1": "server"})
        current = self.put(sid, 1, "S", {"A1": "mine"}).json()["current"]
        resp = self.put(sid, current["revision"], "S", {"A1": "mine"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.json()["revision"], 3)

    def test_future_base_revision_conflicts(self):
        sid = self.create("S")["id"]
        self.assertEqual(self.put(sid, 7, "S", {}).status, 409)

    def test_concurrent_puts_exactly_one_wins(self):
        sid = self.create("S")["id"]
        results = []
        lock = threading.Lock()

        def worker(n):
            resp = self.put(sid, 1, "t%d" % n, {"A1": str(n)})
            with lock:
                results.append(resp.status)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(sorted(results), [200] + [409] * 5)
        self.assertEqual(self.request("GET", "%s/%d" % (API, sid)).json()["revision"], 2)


class ValidationTests(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.sid = self.create("S")["id"]

    def assert_unchanged(self):
        got = self.request("GET", "%s/%d" % (API, self.sid)).json()
        self.assertEqual((got["revision"], got["cells"], got["title"]), (1, {}, "S"))

    def put_json(self, obj):
        return self.request("PUT", "%s/%d" % (API, self.sid), json_body=obj)

    def test_bad_put_bodies_are_400_invalid(self):
        good = {"base_revision": 1, "title": "S", "cells": {}}
        bad_bodies = {
            "unknown key": dict(good, extra=1),
            "missing cells": {"base_revision": 1, "title": "S"},
            "missing title": {"base_revision": 1, "cells": {}},
            "missing base": {"title": "S", "cells": {}},
            "string revision": dict(good, base_revision="1"),
            "bool revision": dict(good, base_revision=True),
            "float revision": dict(good, base_revision=1.0),
            "zero revision": dict(good, base_revision=0),
            "negative revision": dict(good, base_revision=-1),
            "huge revision": dict(good, base_revision=2 ** 70),
            "unknown cell": dict(good, cells={"G9": "x"}),
            "row 0": dict(good, cells={"A0": "x"}),
            "lowercase cell": dict(good, cells={"a1": "x"}),
            "too long cell": dict(good, cells={"A1": "x" * 201}),
            "control char": dict(good, cells={"A1": "a\u0000b"}),
            "newline": dict(good, cells={"A1": "a\nb"}),
            "DEL": dict(good, cells={"A1": "\u007f"}),
            "non-string cell": dict(good, cells={"A1": 5}),
            "cells list": dict(good, cells=[]),
            "empty title": dict(good, title=""),
            "long title": dict(good, title="t" * 81),
            "title control": dict(good, title="a\tb"),
            "title not string": dict(good, title=7),
        }
        for name, obj in bad_bodies.items():
            with self.subTest(name):
                resp = self.put_json(obj)
                self.assertEqual(resp.status, 400, resp.body)
                self.assertEqual(resp.error_code, "invalid")
        self.assert_unchanged()

    def test_malformed_json_bodies(self):
        raw_bodies = [
            b"", b"not json", b"[]", b"3", b"null", b'"s"', b"{",
            b'{"base_revision":NaN,"title":"S","cells":{}}',
            b'\xef\xbb\xbf{"base_revision":1,"title":"S","cells":{}}',
            b'{"base_revision":1,"title":"\xff","cells":{}}',
            b'{"base_revision":1,"title":"S","cells":{"A1":"\\ud800"}}',
            b"[" * 5000,
        ]
        for raw in raw_bodies:
            with self.subTest(raw=raw[:30]):
                resp = self.request("PUT", "%s/%d" % (API, self.sid), body=raw)
                self.assertEqual(resp.status, 400, resp.body)
                self.assertEqual(resp.error_code, "invalid")
        self.assert_unchanged()

    def test_post_validation(self):
        for obj in ({}, {"title": ""}, {"title": "x" * 81}, {"title": 1},
                    {"title": "x", "cells": {}}, {"title": "a\nb"}):
            with self.subTest(obj=obj):
                resp = self.request("POST", API, json_body=obj)
                self.assertEqual(resp.status, 400)
                self.assertEqual(resp.error_code, "invalid")
        self.assertEqual(len(self.request("GET", API).json()["sheets"]), 1)

    def test_error_body_shape(self):
        body = self.put_json({"nope": 1}).json()
        self.assertEqual(set(body), {"error"})
        self.assertEqual(set(body["error"]), {"code", "message"})

    def test_server_recovers_after_bad_requests(self):
        self.put_json({"nope": 1})
        self.assertEqual(self.put(self.sid, 1, "S", {"A1": "ok"}).status, 200)


class CapTests(ServerTestCase):
    def test_cell_200_ok_201_rejected(self):
        sid = self.create("S")["id"]
        self.assertEqual(self.put(sid, 1, "S", {"A1": "x" * 200}).status, 200)
        self.assertEqual(self.put(sid, 2, "S", {"A1": "x" * 201}).status, 400)

    def test_cell_cap_counts_code_points_not_bytes(self):
        sid = self.create("S")["id"]
        self.assertEqual(self.put(sid, 1, "S", {"A1": "日" * 200}).status, 200)
        self.assertEqual(self.put(sid, 2, "S", {"A1": "日" * 201}).status, 400)

    def test_title_80_ok_81_rejected(self):
        self.assertEqual(self.request("POST", API, json_body={"title": "t" * 80}).status, 201)
        self.assertEqual(self.request("POST", API, json_body={"title": "t" * 81}).status, 400)

    def test_body_limit(self):
        base = b'{"title":"x"}'
        ok = base + b" " * (65536 - len(base))
        self.assertEqual(len(ok), 65536)
        self.assertEqual(self.request("POST", API, body=ok).status, 201)
        too_big = base + b" " * (65537 - len(base))
        resp = self.request("POST", API, body=too_big)
        self.assertEqual(resp.status, 413)
        self.assertEqual(resp.error_code, "too_large")
        self.assertEqual(len(self.request("GET", API).json()["sheets"]), 1)

    def test_declared_huge_length_rejected_without_reading(self):
        resp = self.request("POST", API, body=b"{}",
                            headers={"Content-Length": "999999999"})
        # server must answer 413 immediately rather than wait for the body
        self.assertEqual(resp.status, 413)

    def test_fifty_sheet_limit(self):
        for i in range(50):
            self.create("s%d" % i)
        resp = self.request("POST", API, json_body={"title": "51"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.error_code, "limit_reached")
        self.assertEqual(len(self.request("GET", API).json()["sheets"]), 50)
        # existing sheets stay editable at the cap
        self.assertEqual(self.put(1, 1, "s0", {"A1": "1"}).status, 200)


class HeaderAndRequestGuardTests(ServerTestCase):
    def test_security_headers_on_all_response_kinds(self):
        responses = [
            self.request("GET", "/api/v1/health"),
            self.request("GET", "/nope"),
            self.request("POST", API, body=b"{}"),  # 400
            self.request("OPTIONS", API),
            self.request("GET", "/api/v1/health", host="evil.example"),
            self.request("POST", API, body=b"x", content_type="text/plain"),
        ]
        for resp in responses:
            with self.subTest(status=resp.status):
                h = resp.headers
                self.assertEqual(h["x-content-type-options"], "nosniff")
                self.assertEqual(h["cache-control"], "no-store")
                self.assertEqual(h["referrer-policy"], "no-referrer")
                csp = h["content-security-policy"]
                self.assertIn("default-src 'self'", csp)
                self.assertIn("frame-ancestors 'none'", csp)
                self.assertIn("base-uri 'none'", csp)
                self.assertFalse([k for k in h if k.startswith("access-control-")])

    def test_options_and_other_methods_405(self):
        for method in ("OPTIONS", "DELETE", "PATCH", "HEAD"):
            for path in (API, API + "/1", "/api/v1/health", "/"):
                with self.subTest(method=method, path=path):
                    resp = self.request(method, path, headers={
                        "Origin": "http://evil.example",
                        "Access-Control-Request-Method": "PUT"})
                    self.assertEqual(resp.status, 405)
                    self.assertFalse([k for k in resp.headers if k.startswith("access-control-")])
                    if method != "HEAD":
                        self.assertEqual(resp.error_code, "method_not_allowed")

    def test_wrong_method_on_known_paths_405(self):
        self.assertEqual(self.request("POST", "/api/v1/health", body=b"{}").status, 405)
        self.assertEqual(self.request("PUT", API, body=b"{}").status, 405)
        self.assertEqual(self.request("POST", API + "/1", body=b"{}").status, 405)
        self.assertEqual(self.request("POST", "/", body=b"{}").status, 405)

    def test_bad_host_rejected_everywhere(self):
        bad_hosts = ["evil.example", "127.0.0.1", "localhost", "127.0.0.1:1",
                     "localhost:1", "127.0.0.1.evil.example:%d" % self.port,
                     "[::1]:%d" % self.port, "", "0.0.0.0:%d" % self.port,
                     "127.0.0.1:%d@evil.example" % self.port]
        for host in bad_hosts:
            for path in ("/api/v1/health", API, "/", "/static/app.js"):
                with self.subTest(host=host, path=path):
                    resp = self.request("GET", path, host=host)
                    self.assertEqual(resp.status, 403)
                    self.assertEqual(resp.error_code, "forbidden_origin")

    def test_bad_host_on_mutation_rejected_and_nothing_created(self):
        resp = self.request("POST", API, json_body={"title": "x"}, host="evil.example")
        self.assertEqual(resp.status, 403)
        self.assertEqual(self.request("GET", API).json(), {"sheets": []})

    def test_localhost_host_accepted(self):
        resp = self.request("GET", "/api/v1/health", host="localhost:%d" % self.port)
        self.assertEqual(resp.status, 200)

    def test_origin_rejected_on_mutations(self):
        p = self.port
        for origin in ("http://evil.example", "null", "http://127.0.0.1:1",
                       "https://127.0.0.1:%d" % p, "http://127.0.0.1", "http://localhost",
                       "http://127.0.0.1:%d.evil.example" % p, "http://127.0.0.1:%d/" % p, ""):
            with self.subTest(origin=origin, method="POST"):
                resp = self.request("POST", API, json_body={"title": "x"},
                                    headers={"Origin": origin})
                self.assertEqual(resp.status, 403)
                self.assertEqual(resp.error_code, "forbidden_origin")
        self.assertEqual(self.request("GET", API).json(), {"sheets": []})
        sid = self.create("S")["id"]
        resp = self.request("PUT", "%s/%d" % (API, sid),
                            json_body={"base_revision": 1, "title": "x", "cells": {}},
                            headers={"Origin": "http://evil.example"})
        self.assertEqual(resp.status, 403)
        self.assertEqual(self.request("GET", "%s/%d" % (API, sid)).json()["revision"], 1)

    def test_loopback_origins_accepted(self):
        for origin in ("http://127.0.0.1:%d" % self.port, "http://localhost:%d" % self.port):
            with self.subTest(origin=origin):
                resp = self.request("POST", API, json_body={"title": "x"},
                                    headers={"Origin": origin})
                self.assertEqual(resp.status, 201)

    def test_media_type_415(self):
        for ctype in ("text/plain", "application/x-www-form-urlencoded",
                      "application/jsonx", "text/json", "multipart/form-data", None):
            with self.subTest(ctype=ctype):
                resp = self.request("POST", API, body=b'{"title":"x"}', content_type=ctype)
                self.assertEqual(resp.status, 415)
                self.assertEqual(resp.error_code, "unsupported_media_type")
        sid = self.create("S")["id"]
        resp = self.request(
            "PUT", "%s/%d" % (API, sid), content_type="text/plain",
            body=b'{"base_revision":1,"title":"x","cells":{}}')
        self.assertEqual(resp.status, 415)
        self.assertEqual(self.request("GET", "%s/%d" % (API, sid)).json()["revision"], 1)

    def test_missing_or_bad_length(self):
        resp = self.request("POST", API)  # no body, no Content-Length
        self.assertEqual(resp.status, 411)
        resp = self.request("POST", API, headers={"Content-Length": "abc"})
        self.assertEqual(resp.status, 400)
        resp = self.request("POST", API, headers={"Content-Length": "-5"})
        self.assertEqual(resp.status, 400)
        self.assertEqual(self.request("GET", API).json(), {"sheets": []})

    def test_internal_error_is_generic(self):
        def boom():
            raise RuntimeError("secret-detail")

        self.server.storage.list_sheets = boom
        with redirect_stderr(StringIO()):
            resp = self.request("GET", API)
        self.assertEqual(resp.status, 500)
        self.assertEqual(resp.error_code, "internal")
        text = resp.body.decode()
        self.assertNotIn("secret-detail", text)
        self.assertNotIn("Traceback", text)
        # server keeps serving other routes
        self.assertEqual(self.request("GET", "/api/v1/health").status, 200)


class StaticTests(ServerTestCase):
    def test_traversal_and_non_allowlisted_paths_404(self):
        paths = [
            "/static/../server.py", "/static/%2e%2e/server.py", "/static/%2E%2E/server.py",
            "/static/..%2fserver.py", "/static/%2e%2e%2fserver.py", "/static/..%5cserver.py",
            "/static/../sheet_history/server.py", "/static/../../sheet_history/storage.py",
            "/%2e%2e/%2e%2e/etc/passwd", "/static/", "/static", "/static/index.html",
            "/static/app.js/", "/static//app.js", "/static/app.js%00", "/static/APP.JS",
            "/index.html", "/server.py", "/sheet_history/server.py", "/.git/config",
            "/static/app.js/../app.css", "/sheets.sqlite", "/static/__init__.py",
        ]
        for path in paths:
            with self.subTest(path=path):
                resp = self.request("GET", path)
                self.assertEqual(resp.status, 404)
                self.assertEqual(resp.error_code, "not_found")
                self.assertNotIn(b"make_server", resp.body)

    def test_allowlisted_static_files_when_present(self):
        for path, ctype in (("/static/app.css", "text/css"), ("/static/app.js", "javascript")):
            with self.subTest(path=path):
                resp = self.request("GET", path)
                self.assertEqual(resp.status, 200)
                self.assertIn(ctype, resp.headers["content-type"])
                self.assertEqual(resp.headers["x-content-type-options"], "nosniff")

    def test_app_js_avoids_innerhtml(self):
        resp = self.request("GET", "/static/app.js")
        self.assertEqual(resp.status, 200)
        self.assertNotIn(b"innerHTML", resp.body)

    def test_index_serves_required_ids(self):
        resp = self.request("GET", "/")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.headers["content-type"].startswith("text/html"))
        html = resp.body.decode("utf-8")
        for ident in REQUIRED_IDS:
            with self.subTest(id=ident):
                self.assertRegex(html, r"""id\s*=\s*["']%s["']""" % re.escape(ident))
        self.assertNotRegex(html, r"(?i)<script(?![^>]*\bsrc=)[^>]*>\s*\S")
        self.assertNotRegex(html, r"(?i)\b(?:src|href)\s*=\s*[\"']https?://")


if __name__ == "__main__":
    unittest.main()
