"""FastAPI leaderboard. Run with ``python -m client.leaderboard --open``.

The game uses start_server(), which returns an already running local server.
Use its actual ``url`` (the requested port may be busy), then shutdown() and
server_close() on exit. Both cleanup methods may be called more than once.
"""

import argparse
from contextlib import asynccontextmanager
import errno
from pathlib import Path
import socket
import sqlite3
import sys
import threading
import time
from typing import Literal
from uuid import UUID
import webbrowser

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
import uvicorn

from client import database


WEB_PATH = Path(__file__).resolve().parents[1] / "web"


class ScoreSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player: StrictStr = Field(min_length=1, max_length=24)
    score: int = Field(strict=True, ge=0, le=1_000_000_000)
    level: int = Field(default=1, strict=True, ge=1, le=3)
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    won: bool = Field(default=False, strict=True)
    run_id: UUID | None = None

    @field_validator("player", mode="before")
    @classmethod
    def clean_player(cls, value):
        if isinstance(value, str):
            value = " ".join(value.split())
            if any(ord(character) < 32 for character in value):
                raise ValueError("Player name contains an invalid character.")
        return value


@asynccontextmanager
async def lifespan(_app):
    database.initialize_database()
    yield


def create_app():
    application = FastAPI(
        title="Towers of Chance Leaderboard",
        description="Local saved scores, top defenses, and player statistics.",
        version="1.0.0", lifespan=lifespan,
    )
    templates = Jinja2Templates(directory=str(WEB_PATH / "templates"))
    application.mount("/static", StaticFiles(directory=WEB_PATH / "static", check_dir=False), name="static")

    @application.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
    def homepage(request: Request):
        records = database.top_scores(30)
        records = [dict(record, name=record["player"]) for record in records]
        return templates.TemplateResponse(request=request, name="leaderboard.html", context={"scores": records})

    @application.post("/scores", status_code=201, summary="Save a completed game")
    def submit_score(submission: ScoreSubmission, response: Response):
        record = submission.model_dump()
        record["run_id"] = str(submission.run_id) if submission.run_id is not None else None
        try:
            saved, created = database.add_score(record)
        except database.RunConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        response.status_code = 201 if created else 200
        return saved

    @application.get("/scores/top", summary="Get scores from highest to lowest")
    def top_scores(limit: int = Query(default=30, ge=1, le=100)):
        return database.top_scores(limit)

    @application.get("/players/{name:path}/stats", summary="Get a player's saved statistics")
    def player_stats(name: str):
        name = " ".join(name.split())
        if not name or len(name) > 24:
            raise HTTPException(status_code=422, detail="Player name must contain 1 to 24 characters.")
        stats = database.player_stats(name)
        if stats is None:
            raise HTTPException(status_code=404, detail="No saved scores for this player.")
        return stats

    @application.get("/api/scores", summary="Get scores in the game's display format")
    def compatible_scores():
        return {"scores": [
            {"name": record["player"], **{key: record[key] for key in ("score", "level", "difficulty", "won", "date")}}
            for record in database.top_scores(30)
        ]}

    return application


app = create_app()


class LeaderboardServer:
    """A small game-friendly lifecycle wrapper around a local Uvicorn server."""

    def __init__(self, listener):
        self._listener = listener
        self.server_address = listener.getsockname()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.server_address[1],
            log_config=None, access_log=False, log_level="error",
            server_header=False, timeout_graceful_shutdown=2,
        )
        self._server = uvicorn.Server(config)
        self._startup_error = None
        self.thread = threading.Thread(target=self._run, name="leaderboard", daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/"

    def _run(self):
        try:
            self._server.run(sockets=[self._listener])
        except BaseException as error:
            self._startup_error = error

    def shutdown(self):
        self._server.should_exit = True
        if self.thread.ident is not None and threading.current_thread() is not self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self._server.force_exit = True
                self.thread.join(timeout=1)

    def server_close(self):
        self.shutdown()
        self._listener.close()


def _bind_listener(port):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        listener.setblocking(False)
    except OSError:
        listener.close()
        raise
    return listener


def start_server(port=8000):
    """Return a running localhost server, choosing a free port if needed."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer from 0 to 65535.")
    try:
        database.initialize_database()
    except sqlite3.Error as error:
        raise OSError("The leaderboard database could not be opened.") from error
    try:
        listener = _bind_listener(port)
    except OSError as error:
        busy = error.errno in (errno.EADDRINUSE, errno.EACCES, 10013, 10048)
        if not port or not busy:
            raise
        listener = _bind_listener(0)
    server = LeaderboardServer(listener)
    try:
        server.thread.start()
        deadline = time.monotonic() + 10
        while not server._server.started and server.thread.is_alive() and time.monotonic() < deadline:
            server.thread.join(timeout=0.01)
        if not server._server.started:
            raise OSError("The local leaderboard could not start.") from server._startup_error
    except (OSError, RuntimeError):
        server.server_close()
        raise
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
    parser.add_argument("--port", type=_port, default=8000, help="preferred local port (default: 8000)")
    parser.add_argument("--open", action="store_true", help="open the leaderboard in your browser")
    args = parser.parse_args()
    try:
        server = start_server(args.port)
    except OSError as error:
        parser.exit(1, f"Could not start the local leaderboard: {error}\n")
    if sys.stdout is not None:
        print(f"Leaderboard: {server.url}\nPress Ctrl+C to stop.", flush=True)
    try:
        if args.open:
            webbrowser.open(server.url)
        server.thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
