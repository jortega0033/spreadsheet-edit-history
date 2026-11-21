import io
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from sheet_history import __main__ as cli


def run(argv):
    err, out = io.StringIO(), io.StringIO()
    with redirect_stderr(err), redirect_stdout(out):
        code = cli.main(argv)
    return code, err.getvalue(), out.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name

    def test_empty_data_dir_exits_2_single_line(self):
        code, err, _ = run(["--data-dir", "", "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_file_as_data_dir_exits_2(self):
        path = os.path.join(self.root, "f")
        with open(path, "w") as fh:
            fh.write("x")
        code, err, _ = run(["--data-dir", path, "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_uncreatable_data_dir_exits_2(self):
        blocker = os.path.join(self.root, "f")
        with open(blocker, "w") as fh:
            fh.write("x")
        code, err, _ = run(["--data-dir", os.path.join(blocker, "sub"), "--port", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_bad_ports_exit_2(self):
        for port in ("-1", "65536", "70000", "abc", ""):
            with self.subTest(port=port):
                code, err, _ = run(["--data-dir", self.root, "--port", port])
                self.assertEqual(code, 2)

    def test_missing_data_dir_arg_exits_2(self):
        code, _, _ = run(["--port", "0"])
        self.assertEqual(code, 2)

    def test_bind_failure_exits_1(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(blocker.close)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        code, err, _ = run(["--data-dir", os.path.join(self.root, "d"), "--port", str(port)])
        self.assertEqual(code, 1)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_ctrl_c_shuts_down_cleanly(self):
        fake = mock.Mock()
        fake.server_address = ("127.0.0.1", 12345)
        fake.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch.object(cli, "make_server", return_value=fake) as made:
            code, _, out = run(["--data-dir", self.root, "--port", "0"])
        self.assertEqual(code, 0)
        made.assert_called_once_with(self.root, 0)
        fake.shutdown.assert_called_once()
        fake.server_close.assert_called_once()
        self.assertIn("127.0.0.1:12345", out)


if __name__ == "__main__":
    unittest.main()
