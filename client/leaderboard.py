"""Read-only leaderboard on this computer. Run with python -m client.leaderboard.

start_server() returns a running server. Its ``url`` always identifies the server
we started, including when the preferred port was busy. Call shutdown() followed
by server_close() when the game exits. No Pygame or third-party package is needed.
"""

import argparse
import errno
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit
import webbrowser

from client.scores import load_scores


INDEX_PATH = Path(__file__).resolve().parents[1] / "web" / "index.html"


class LeaderboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._serve(send_body=True)

    def do_HEAD(self):
        self._serve(send_body=False)

    def _serve(self, send_body):
        try:
            path = urlsplit(self.path).path
        except ValueError:
            self._respond(400, b"Invalid request.", "text/plain; charset=utf-8", send_body)
            return
        if path in ("/", "/index.html"):
            try:
                body = INDEX_PATH.read_bytes()
            except OSError:
                self._respond(500, b"Leaderboard page unavailable.", "text/plain; charset=utf-8", send_body)
                return
            self._respond(200, body, "text/html; charset=utf-8", send_body)
        elif path == "/api/scores":
            try:
                body = json.dumps({"scores": load_scores()}, ensure_ascii=False).encode("utf-8")
            except (OSError, ValueError, TypeError):
                self._respond(500, b'{"error":"Scores unavailable."}', "application/json; charset=utf-8", send_body)
                return
            self._respond(200, body, "application/json; charset=utf-8", send_body)
        else:
            self._respond(404, b"Not found.", "text/plain; charset=utf-8", send_body)

    def _respond(self, status, body, content_type, send_body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, _format, *_args):
        # The game starts this server in the background; polling needs no log.
        pass


class LeaderboardServer(ThreadingHTTPServer):
    daemon_threads = True

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/"


def start_server(port=8765):
    """Start a daemon server bound only to 127.0.0.1 and return it.

    If the preferred port is occupied/reserved, ask the OS for a free port.
    Opening ``server.url`` is safe even when another app already owns port 8765.
    """
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer from 0 to 65535.")
    try:
        server = LeaderboardServer(("127.0.0.1", port), LeaderboardHandler)
    except OSError as error:
        busy = error.errno in (errno.EADDRINUSE, errno.EACCES, 10013, 10048)
        if not port or not busy:
            raise
        server = LeaderboardServer(("127.0.0.1", 0), LeaderboardHandler)
    thread = threading.Thread(target=server.serve_forever, name="leaderboard", daemon=True)
    try:
        thread.start()
    except RuntimeError:
        server.server_close()
        raise
    server.thread = thread
    return server


def _port(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be a number.") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be from 0 to 65535.")
    return port


def main():
    parser = argparse.ArgumentParser(description="Open the local Towers of Chance leaderboard.")
    parser.add_argument("--port", type=_port, default=8765, help="preferred local port (default: 8765)")
    parser.add_argument("--open", action="store_true", help="open the leaderboard in your browser")
    args = parser.parse_args()
    try:
        server = start_server(args.port)
    except OSError as error:
        parser.exit(1, f"Could not start the local leaderboard: {error}\n")
    print(f"Leaderboard: {server.url}\nPress Ctrl+C to stop.", flush=True)
    try:
        if args.open:
            webbrowser.open(server.url)
        server.thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
