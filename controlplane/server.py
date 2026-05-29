#!/usr/bin/env python3
"""Control plane for agentbox.

Lists, creates, and renders interactive terminals for tmux sessions running
inside this container. Authentication is delegated to whatever reverse proxy
sits in front of port 9119 (Cloudflare Access, Tailscale, basic auth, etc.).
"""
import asyncio
import datetime as _dt
import fcntl
import hashlib
import hmac
import json
import os
import pty
import random
import re
import signal
import struct
import subprocess
import termios
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")

ANIMALS = [
    "aardvark", "alligator", "antelope", "armadillo", "badger", "bandicoot",
    "bat", "bear", "beaver", "bison", "boar", "buffalo", "camel", "capybara",
    "caribou", "cat", "cheetah", "chinchilla", "chipmunk", "cobra", "cougar",
    "coyote", "crab", "crane", "crocodile", "deer", "dingo", "dolphin",
    "donkey", "eagle", "echidna", "eel", "elephant", "elk", "falcon",
    "ferret", "finch", "flamingo", "fox", "frog", "gazelle", "gecko",
    "gerbil", "giraffe", "goat", "goose", "gopher", "gorilla", "hamster",
    "hare", "hawk", "hedgehog", "heron", "hippo", "horse", "hyena", "ibex",
    "ibis", "iguana", "jackal", "jaguar", "jay", "kangaroo", "kingfisher",
    "kiwi", "koala", "lemur", "leopard", "lion", "llama", "lobster", "lynx",
    "magpie", "manatee", "marmot", "meerkat", "mole", "mongoose", "monkey",
    "moose", "mouse", "narwhal", "newt", "ocelot", "octopus", "okapi",
    "opossum", "orca", "oryx", "ostrich", "otter", "owl", "panda", "panther",
    "parrot", "peacock", "pelican", "penguin", "platypus", "porcupine",
    "possum", "puffin", "puma", "quail", "quokka", "rabbit", "raccoon",
    "raven", "reindeer", "rhino", "salamander", "seal", "seahorse", "shark",
    "skunk", "sloth", "snail", "sparrow", "squid", "squirrel", "starfish",
    "stingray", "stork", "swan", "tapir", "tiger", "toad", "tortoise",
    "toucan", "turkey", "turtle", "viper", "vole", "vulture", "wallaby",
    "walrus", "warthog", "weasel", "whale", "wolf", "wolverine", "wombat",
    "woodpecker", "yak", "zebra",
]


def suggest_name() -> str:
    today = _dt.date.today().strftime("%d-%m-%y")
    used = {s["name"].split("-", 1)[0] for s in tmux_sessions()}
    pool = [a for a in ANIMALS if a not in used] or ANIMALS
    return f"{random.choice(pool)}-{today}"


app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# --- Optional password gate --------------------------------------------------
# Set AGENTBOX_PASSWORD in the environment to require a login. When unset, access is
# open and authentication is left entirely to whatever proxy sits in front
# (Cloudflare Access, Tailscale, etc.). The login issues an HMAC-signed,
# HttpOnly cookie that expires after AUTH_TTL — the password itself is never
# stored in the cookie, and changing it invalidates every outstanding cookie.
AUTH_PASSWORD = os.environ.get("AGENTBOX_PASSWORD", "").strip()
AUTH_ENABLED = bool(AUTH_PASSWORD)
AUTH_COOKIE = "agentbox_auth"
AUTH_TTL = 24 * 60 * 60  # 24h
_AUTH_KEY = hashlib.sha256(b"agentbox-auth-v1:" + AUTH_PASSWORD.encode()).digest()
# Paths reachable without a session: the login flow itself and static assets
# (CSS/JS reveal nothing and the login page needs them to render).
_PUBLIC_PREFIXES = ("/login", "/logout", "/static")


def _make_token() -> str:
    exp = str(int(time.time()) + AUTH_TTL)
    sig = hmac.new(_AUTH_KEY, exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _token_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp_s, _, sig = token.partition(".")
    try:
        if int(exp_s) < time.time():
            return False
    except ValueError:
        return False
    expect = hmac.new(_AUTH_KEY, exp_s.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expect)


def _safe_next(dest: str) -> str:
    """Only allow same-site redirect targets (no protocol-relative `//evil`)."""
    return dest if dest.startswith("/") and not dest.startswith("//") else "/"


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    if not AUTH_ENABLED:
        return await call_next(request)
    path = request.url.path
    if path.startswith(_PUBLIC_PREFIXES) or path == "/favicon.ico":
        return await call_next(request)
    if _token_valid(request.cookies.get(AUTH_COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "auth required"}, status_code=401)
    nxt = path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?next={quote(nxt)}", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page():
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)
    return (STATIC / "login.html").read_text()


@app.post("/login")
def login_submit(
    request: Request,
    password: str = Form(...),
    dest: str = Form("/", alias="next"),
):
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)
    dest = _safe_next(dest)
    if not hmac.compare_digest(password.encode(), AUTH_PASSWORD.encode()):
        return RedirectResponse(f"/login?error=1&next={quote(dest)}", status_code=303)
    resp = RedirectResponse(dest, status_code=303)
    # Secure when the client is on HTTPS (trust the tunnel's forwarded proto);
    # plain http on localhost stays non-Secure so local login still works.
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(
        AUTH_COOKIE, _make_token(), max_age=AUTH_TTL,
        httponly=True, samesite="lax", secure=secure, path="/",
    )
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login" if AUTH_ENABLED else "/", status_code=303)
    resp.delete_cookie(AUTH_COOKIE, path="/")
    return resp


SHELL_CMDS = {"bash", "zsh", "sh", "fish", "ash", "dash", "csh", "tcsh", "ksh", "login"}
CLAUDE_IDLE_HINTS = ("shift+tab", "? for shortcuts", "Bypass permissions")
QUESTION_RE = re.compile(r"❯\s+1\.")


def pane_text(name: str) -> str:
    try:
        out = subprocess.check_output(
            ["tmux", "capture-pane", "-p", "-t", name],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return out.decode("utf-8", errors="replace")


def pane_current_command(name: str) -> str:
    try:
        out = subprocess.check_output(
            ["tmux", "display-message", "-p", "-t", name, "#{pane_current_command}"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return out.decode().strip()


def session_status(name: str) -> str:
    """Detect what the foreground process in the session is doing.

    Returns one of "running", "question", or "idle". Claude's TUI footer
    is the primary signal — "esc to interrupt" while mid-response, a
    "❯ 1." numbered-menu cursor while awaiting a confirmation. Outside
    those, fall back to the pane's foreground command: shells (or no
    process) mean idle; any other long-running binary means something is
    happening (e.g. `npm install` from bash). Claude sitting at its own
    input prompt also reports idle, detected via the mode-hint strings
    it renders below the input box.
    """
    text = pane_text(name)
    if "esc to interrupt" in text:
        return "running"
    if QUESTION_RE.search(text):
        return "question"
    cmd = pane_current_command(name)
    if not cmd or cmd in SHELL_CMDS:
        return "idle"
    if any(hint in text for hint in CLAUDE_IDLE_HINTS):
        return "idle"
    return "running"


def tmux_sessions():
    try:
        out = subprocess.check_output(
            [
                "tmux", "list-sessions", "-F",
                "#{session_name}\t#{session_attached}\t#{session_windows}\t#{session_created}",
            ],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    sessions = []
    for line in out.splitlines():
        if not line:
            continue
        name, attached, windows, created = line.split("\t")
        sessions.append({
            "name": name,
            "attached": int(attached),
            "windows": int(windows),
            "created": int(created),
            "status": session_status(name),
        })
    sessions.sort(key=lambda s: -s["created"])
    return sessions


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text()


@app.get("/api/sessions")
def list_sessions():
    return {"sessions": tmux_sessions()}


@app.get("/api/suggest-name")
def api_suggest_name():
    return {"name": suggest_name()}


@app.post("/api/sessions")
def create_session(
    name: str = Form(...),
    cwd: str = Form("/work"),
    command: str = Form(...),
):
    if not NAME_RE.match(name):
        raise HTTPException(400, "invalid name (alnum, dash, underscore; must start with alnum)")
    command = command.strip()
    if not command:
        raise HTTPException(400, "command is required")
    if not Path(cwd).is_dir():
        raise HTTPException(400, f"cwd does not exist: {cwd}")
    res = subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "-c", cwd, command],
        capture_output=True,
    )
    if res.returncode != 0:
        msg = res.stderr.decode().strip() or "tmux failed"
        raise HTTPException(400, msg)
    return {"ok": True, "name": name}


@app.delete("/api/sessions/{name}")
def kill_session(name: str):
    if not NAME_RE.match(name):
        raise HTTPException(400, "invalid name")
    res = subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True)
    if res.returncode != 0:
        raise HTTPException(404, "no such session")
    return {"ok": True}


@app.patch("/api/sessions/{name}")
def rename_session(name: str, new_name: str = Form(...)):
    if not NAME_RE.match(name):
        raise HTTPException(400, "invalid name")
    if not NAME_RE.match(new_name):
        raise HTTPException(400, "invalid new name (alnum, dash, underscore; must start with alnum)")
    if new_name == name:
        return {"ok": True, "name": new_name}
    res = subprocess.run(
        ["tmux", "rename-session", "-t", name, new_name],
        capture_output=True,
    )
    if res.returncode != 0:
        msg = res.stderr.decode().strip() or "tmux failed"
        raise HTTPException(400, msg)
    return {"ok": True, "name": new_name}


@app.get("/t/{name}", response_class=HTMLResponse)
def terminal_page(name: str):
    if not NAME_RE.match(name):
        raise HTTPException(400, "invalid name")
    return (STATIC / "terminal.html").read_text().replace("{{SESSION}}", name)


def capture_scrollback(name: str) -> bytes:
    """Pre-visible pane history with ANSI escapes, ready to send to xterm.js.

    Returns b"" while alt-screen is active (Claude Code, vim, less) — tmux
    holds no scrollback for the alt buffer, and the regular pane's history is
    stale bash output from before the alt-screen app launched.

    `-E -1` stops one line above the visible screen so the live `tmux attach`
    that follows can repaint the visible region without overlap.
    """
    try:
        alt = subprocess.check_output(
            ["tmux", "display-message", "-p", "-t", name, "#{alternate_on}"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return b""
    if alt != "0":
        return b""
    try:
        out = subprocess.check_output(
            ["tmux", "capture-pane", "-p", "-e", "-S", "-", "-E", "-1", "-t", name],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return b""
    # capture-pane separates lines with \n; xterm.js needs \r\n in raw mode.
    return out.replace(b"\n", b"\r\n")


@app.websocket("/ws/{name}")
async def ws_terminal(websocket: WebSocket, name: str):
    if not NAME_RE.match(name):
        await websocket.close(code=4400)
        return
    if AUTH_ENABLED and not _token_valid(websocket.cookies.get(AUTH_COOKIE)):
        await websocket.close(code=4401)
        return
    await websocket.accept()

    # Replay pane history into xterm.js scrollback on first attach. The client
    # sets ?history=1 on initial page load and omits it on auto-reconnects to
    # avoid duplicating what's already in the browser's scrollback.
    if websocket.query_params.get("history") == "1":
        # Blocking tmux calls — run off the event loop.
        scrollback = await asyncio.to_thread(capture_scrollback, name)
        if scrollback:
            await websocket.send_bytes(scrollback)

    pid, fd = pty.fork()
    if pid == 0:
        # Child: become the tmux client. execvp only returns on failure, so
        # _exit hard rather than unwinding back into the async server code.
        os.environ["TERM"] = "xterm-256color"
        try:
            os.execvp("tmux", ["tmux", "attach-session", "-t", name])
        except OSError:
            os._exit(127)

    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_readable():
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            return
        except OSError:
            loop.remove_reader(fd)
            queue.put_nowait(None)
            return
        if not data:
            loop.remove_reader(fd)
            queue.put_nowait(None)
            return
        queue.put_nowait(data)

    loop.add_reader(fd, on_readable)

    async def pump_to_client():
        while True:
            data = await queue.get()
            if data is None:
                return
            await websocket.send_bytes(data)

    async def pump_to_pty():
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes"):
                os.write(fd, msg["bytes"])
            elif msg.get("text"):
                try:
                    obj = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "resize":
                    try:
                        rows = max(1, min(int(obj.get("rows", 24)), 1000))
                        cols = max(1, min(int(obj.get("cols", 80)), 1000))
                    except (TypeError, ValueError):
                        continue
                    fcntl.ioctl(
                        fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0),
                    )

    tasks = [asyncio.create_task(pump_to_client()), asyncio.create_task(pump_to_pty())]
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9119, log_level="info")
