"""CLI entry point: python -m sheet_history --data-dir <path> --port <port>."""

import argparse
import sys

from .server import make_server
from .storage import StorageError


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print("sheet_history: error: %s" % message, file=sys.stderr)
        raise SystemExit(2)


def _port(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer 0-65535")
    if not 0 <= value <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer 0-65535")
    return value


def main(argv=None):
    parser = _Parser(prog="sheet_history", description="Local spreadsheet edit history")
    parser.add_argument("--data-dir", required=True, help="directory for sheets.sqlite")
    parser.add_argument("--port", type=_port, default=8765, help="port on 127.0.0.1")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    try:
        server = make_server(args.data_dir, args.port)
    except StorageError as exc:
        print("sheet_history: error: %s" % " ".join(str(exc).split()), file=sys.stderr)
        return 2
    except OSError as exc:
        print(
            "sheet_history: error: cannot listen on 127.0.0.1:%d: %s"
            % (args.port, " ".join(str(exc).split())),
            file=sys.stderr,
        )
        return 1

    host, port = server.server_address[:2]
    print("Serving on http://%s:%d (Ctrl-C to stop)" % (host, port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
