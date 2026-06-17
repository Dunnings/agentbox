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
import shutil
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
    used = {n.split("-", 1)[0] for n in session_names()}
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
    """Only allow same-site redirect targets. Rejects protocol-relative URLs:
    `//evil`, and `/\\evil` (and its percent-encoded form) — browsers treat a
    backslash after the leading slash as a second slash, making it offsite."""
    if dest.startswith("/") and not dest.startswith(("//", "/\\", "/%5C", "/%5c")):
        return dest
    return "/"


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    resp = await call_next(request)
    # Static assets (settings.js, common.css, …) are baked into the image and
    # change on every rebuild. Force the browser to revalidate so it never runs
    # a stale settings.js after an upgrade — the dropdown would otherwise keep
    # the pre-upgrade command list. ETag (set by StaticFiles) keeps the
    # revalidation a cheap 304 when nothing changed.
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# Content-Security-Policy for the control plane. Everything is same-origin and
# vendored (xterm, fonts) — no third-party CDN — so 'self' covers scripts,
# styles, fonts, images, and the terminal WebSocket. The pages carry a few
# inline <script>/<style> blocks, hence 'unsafe-inline'. frame-ancestors 'none'
# blocks clickjacking of a UI that can spawn/kill sessions and run commands.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Content-Security-Policy", _CSP)
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    if not AUTH_ENABLED:
        return await call_next(request)
    path = request.url.path
    if path.startswith(_PUBLIC_PREFIXES) or path in ("/favicon.ico", "/healthz"):
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


# --- Login brute-force throttle ---------------------------------------------
# The login is a single shared password, so slow online guessing down. We keep
# recent failure timestamps per client IP and, before evaluating an attempt,
# sleep for a delay that grows with the count (capped). A legitimate user who
# mistypes once waits a fraction of a second; an attacker is throttled to a
# trickle. We deliberately add delay rather than hard-lock, so nobody can lock
# the real user out by spamming bad passwords. In-memory only — a control-plane
# restart clears it, which is fine for this purpose.
_LOGIN_FAILURES: dict[str, list[float]] = {}
_LOGIN_WINDOW = 15 * 60  # seconds a failure counts toward the delay
_LOGIN_MAX_DELAY = 5.0   # cap so a wedged client can't stall a worker for long


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _recent_failures(ip: str) -> int:
    cutoff = time.monotonic() - _LOGIN_WINDOW
    fails = [t for t in _LOGIN_FAILURES.get(ip, []) if t > cutoff]
    if fails:
        _LOGIN_FAILURES[ip] = fails
    else:
        _LOGIN_FAILURES.pop(ip, None)
    return len(fails)


@app.post("/login")
async def login_submit(
    request: Request,
    password: str = Form(...),
    dest: str = Form("/", alias="next"),
):
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)
    dest = _safe_next(dest)
    ip = _client_ip(request)
    # Throttle before evaluating, so repeated guesses each pay the growing delay.
    prior = _recent_failures(ip)
    if prior:
        await asyncio.sleep(min(_LOGIN_MAX_DELAY, 0.25 * 2 ** min(prior, 5)))
    if not hmac.compare_digest(password.encode(), AUTH_PASSWORD.encode()):
        _LOGIN_FAILURES.setdefault(ip, []).append(time.monotonic())
        return RedirectResponse(f"/login?error=1&next={quote(dest)}", status_code=303)
    _LOGIN_FAILURES.pop(ip, None)  # clear the penalty on success
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

# Default session commands offered in the UI, keyed by the binary that must be
# on PATH for the command to make sense. agentbox installs its toolchains
# opt-in (the INSTALL_* build flags), so the launchable set differs per
# container — /api/commands filters this catalog down to what's actually here.
# Order here is the order the dropdown shows them.
COMMAND_CATALOG = [
    # AI coding agents
    ("claude",    "claude --dangerously-skip-permissions"),
    ("opencode",  "opencode"),
    ("codex",     "codex"),
    ("gemini",    "gemini"),
    ("copilot",   "copilot"),
    ("aider",     "aider"),
    # Shells
    ("bash",     "bash -l"),
    ("zsh",      "zsh -l"),
    ("fish",     "fish -l"),
    # Language runtimes / REPLs
    ("node",     "node"),
    ("python3",  "python3"),
    ("ipython",  "ipython"),
    ("bun",      "bun repl"),
    ("deno",     "deno"),
    ("irb",      "irb"),
]


def detected_commands() -> list[str]:
    """Launch commands whose underlying tool is installed in this container.

    Lets the front end default the new-session command dropdown to what this
    box can actually run rather than a hardcoded list. Always returns at least
    a login shell so the dropdown is never empty.
    """
    cmds = [cmd for binary, cmd in COMMAND_CATALOG if shutil.which(binary)]
    return cmds or ["bash -l"]


CLAUDE_IDLE_HINTS = ("shift+tab", "? for shortcuts", "Bypass permissions")
QUESTION_RE = re.compile(r"❯\s+1\.")

# Every tmux call gets a timeout so a wedged tmux server can't hang a request
# (read endpoints run in FastAPI's threadpool; without a bound, a stuck server
# would slowly exhaust it under the 5s polling from the sessions page).
TMUX_TIMEOUT = 5


def _tmux_text(args: list[str]) -> str | None:
    """Run a read-only tmux command; decoded stdout, or None on any failure."""
    try:
        out = subprocess.check_output(
            ["tmux", *args], stderr=subprocess.DEVNULL, timeout=TMUX_TIMEOUT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.decode("utf-8", errors="replace")


def _tmux_run(args: list[str]) -> subprocess.CompletedProcess:
    """Run a mutating tmux command, capturing output. Translates a hung or
    missing tmux into an HTTP error instead of letting it block the worker."""
    try:
        return subprocess.run(
            ["tmux", *args], capture_output=True, timeout=TMUX_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "tmux timed out")
    except FileNotFoundError:
        raise HTTPException(500, "tmux not available")


def pane_text(name: str) -> str:
    return _tmux_text(["capture-pane", "-p", "-t", name]) or ""


def pane_current_command(name: str) -> str:
    out = _tmux_text(["display-message", "-p", "-t", name, "#{pane_current_command}"])
    return out.strip() if out else ""


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


def session_names() -> list[str]:
    """Just the session names — no per-pane status probing. Used by name
    suggestion, which only needs to know which animals are already taken."""
    out = _tmux_text(["list-sessions", "-F", "#{session_name}"])
    return out.splitlines() if out else []


def tmux_sessions():
    out = _tmux_text([
        "list-sessions", "-F",
        "#{session_name}\t#{session_attached}\t#{session_windows}\t#{session_created}",
    ])
    if out is None:
        return []
    out = out.strip()
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


@app.get("/healthz")
def healthz():
    """Liveness probe for the compose healthcheck. Public (no auth) and cheap —
    it only confirms the FastAPI process is serving, not that tmux is healthy."""
    return {"ok": True}


@app.get("/api/sessions")
def list_sessions():
    return {"sessions": tmux_sessions()}


@app.get("/api/suggest-name")
def api_suggest_name():
    return {"name": suggest_name()}


@app.get("/api/commands")
def api_commands():
    """The default session commands available in this container."""
    return {"commands": detected_commands()}


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
    res = _tmux_run(["new-session", "-d", "-s", name, "-c", cwd, command])
    if res.returncode != 0:
        msg = res.stderr.decode().strip() or "tmux failed"
        raise HTTPException(400, msg)
    return {"ok": True, "name": name}


@app.delete("/api/sessions/{name}")
def kill_session(name: str):
    if not NAME_RE.match(name):
        raise HTTPException(400, "invalid name")
    res = _tmux_run(["kill-session", "-t", name])
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
    res = _tmux_run(["rename-session", "-t", name, new_name])
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

    `-S -5000` caps the replay at the last 5000 lines — the same scrollback
    depth the client's xterm.js keeps — so we never ship history the browser
    would immediately drop. `-E -1` stops one line above the visible screen so
    the live `tmux attach` that follows can repaint it without overlap.
    """
    alt = _tmux_text(["display-message", "-p", "-t", name, "#{alternate_on}"])
    if alt is None or alt.strip() != "0":
        return b""
    try:
        out = subprocess.check_output(
            ["tmux", "capture-pane", "-p", "-e", "-S", "-5000", "-E", "-1", "-t", name],
            stderr=subprocess.DEVNULL, timeout=TMUX_TIMEOUT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
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

    # Client→pty writes. The fd is non-blocking, so a single os.write can write
    # fewer bytes than asked (or raise EAGAIN) when the pty buffer fills — which
    # is exactly what a large paste does. A bare os.write would silently drop the
    # tail or kill the task. Buffer the unwritten remainder and flush it from an
    # add_writer callback as the pty drains, preserving every byte and its order.
    write_buf = bytearray()
    writer_registered = False
    WRITE_BUF_CAP = 4 * 1024 * 1024  # backstop against an unbounded buffer

    def flush_writes():
        nonlocal writer_registered
        while write_buf:
            try:
                n = os.write(fd, write_buf)
            except (BlockingIOError, InterruptedError):
                break  # pty full / interrupted — retry on the next writable event
            except OSError:
                write_buf.clear()
                queue.put_nowait(None)  # pty gone; unblock the read side too
                break
            if n <= 0:
                break
            del write_buf[:n]
        if write_buf and not writer_registered:
            loop.add_writer(fd, flush_writes)
            writer_registered = True
        elif not write_buf and writer_registered:
            loop.remove_writer(fd)
            writer_registered = False

    def feed_write(data: bytes):
        # Drop input rather than grow without bound if the pty stalls hard — far
        # past any real paste, so in practice this never trips.
        if len(write_buf) + len(data) > WRITE_BUF_CAP:
            return
        write_buf.extend(data)
        flush_writes()

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
                feed_write(msg["bytes"])
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
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        # Retrieve any exception from the finished task so asyncio doesn't log a
        # spurious "Task exception was never retrieved" when a pump raises (e.g.
        # the socket dies mid-write). The connection is tearing down regardless.
        for t in done:
            t.exception()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass
        if writer_registered:
            try:
                loop.remove_writer(fd)
            except Exception:
                pass
        try:
            os.close(fd)
        except OSError:
            pass
        # Tear down the per-connection tmux client and reap it so it doesn't
        # linger as a zombie (the server process is long-lived and never wait()s
        # again). It exits promptly on SIGHUP; poll briefly, then SIGKILL as a
        # backstop so a wedged client can't accumulate across reconnects.
        try:
            os.kill(pid, signal.SIGHUP)
        except ProcessLookupError:
            pid = None
        if pid is not None:
            for _ in range(50):  # up to ~0.5s
                try:
                    if os.waitpid(pid, os.WNOHANG)[0] != 0:
                        break
                except ChildProcessError:
                    break
                await asyncio.sleep(0.01)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                except (ProcessLookupError, ChildProcessError):
                    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9119, log_level="info")
