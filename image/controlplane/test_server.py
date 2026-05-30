"""Unit tests for the control plane's security-critical pure logic and the
HTTP surface that's easy to regress (auth tokens, redirect safety, name
validation, security headers, login throttle). Run: `pytest` from this dir.

These run with auth disabled (no AGENTBOX_PASSWORD in the env), which is the
default and keeps the endpoints reachable without a cookie.
"""
import hashlib
import hmac
import os
import sys
import time
from pathlib import Path

# Pin auth OFF before importing server (it reads AGENTBOX_PASSWORD once at
# import) so the suite is deterministic regardless of the ambient environment.
os.environ.pop("AGENTBOX_PASSWORD", None)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(server.app)


# --- _safe_next: same-site redirect targets only ----------------------------

def test_safe_next_allows_local_paths():
    assert server._safe_next("/") == "/"
    assert server._safe_next("/t/panda-30-05-26") == "/t/panda-30-05-26"
    assert server._safe_next("/t/foo?x=1") == "/t/foo?x=1"


def test_safe_next_rejects_offsite():
    for bad in ["//evil.com", "/\\evil", "/%5Cevil", "/%5cevil",
                "http://evil.com", "https://evil.com", "javascript:alert(1)", ""]:
        assert server._safe_next(bad) == "/", bad


# --- HMAC auth token --------------------------------------------------------

def test_token_roundtrip_valid():
    assert server._token_valid(server._make_token())


def test_token_rejects_tampered_and_garbage():
    tok = server._make_token()
    exp, _, sig = tok.partition(".")
    # Flip the last signature char to a guaranteed-different hex digit. (A bare
    # "...0" was flaky: when the signature already ended in 0 it was a no-op and
    # the untampered token validated.)
    flipped = sig[:-1] + ("1" if sig[-1] == "0" else "0")
    assert not server._token_valid(f"{exp}.{flipped}")  # flipped signature
    assert not server._token_valid(f"{exp}.")
    assert not server._token_valid("garbage")
    assert not server._token_valid(None)
    assert not server._token_valid("")


def test_token_rejects_expired():
    exp = str(int(time.time()) - 10)
    sig = hmac.new(server._AUTH_KEY, exp.encode(), hashlib.sha256).hexdigest()
    assert not server._token_valid(f"{exp}.{sig}")


# --- session-name validation ------------------------------------------------

def test_name_re_accepts_valid():
    for ok in ["a", "A1", "panda-30-05-26", "x_y-Z", "a" * 64]:
        assert server.NAME_RE.match(ok), ok


def test_name_re_rejects_invalid():
    for bad in ["", "-leading", "_leading", "has space", "a" * 65,
                "<img src=x>", "foo.bar", "foo:bar", "foo/bar"]:
        assert not server.NAME_RE.match(bad), bad


# --- security headers -------------------------------------------------------

def test_security_headers_present():
    r = client.get("/healthz")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_static_revalidates_and_carries_headers():
    r = client.get("/static/settings.js")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-cache"
    assert r.headers["X-Frame-Options"] == "DENY"


# --- create-session input validation (short-circuits before tmux) -----------

def test_create_session_rejects_bad_name():
    r = client.post("/api/sessions", data={"name": "bad name", "command": "bash"})
    assert r.status_code == 400


def test_create_session_rejects_missing_cwd():
    r = client.post("/api/sessions",
                    data={"name": "ok", "command": "bash", "cwd": "/no/such/dir"})
    assert r.status_code == 400


# --- login brute-force throttle helper --------------------------------------

def test_recent_failures_counts_and_prunes():
    server._LOGIN_FAILURES.clear()
    ip = "203.0.113.7"
    assert server._recent_failures(ip) == 0
    server._LOGIN_FAILURES[ip] = [time.monotonic(), time.monotonic()]
    assert server._recent_failures(ip) == 2
    # Entries older than the window are pruned and the key drops out entirely.
    server._LOGIN_FAILURES[ip] = [time.monotonic() - server._LOGIN_WINDOW - 1]
    assert server._recent_failures(ip) == 0
    assert ip not in server._LOGIN_FAILURES


# --- detected commands ------------------------------------------------------

def test_detected_commands_never_empty():
    cmds = server.detected_commands()
    assert isinstance(cmds, list) and cmds
