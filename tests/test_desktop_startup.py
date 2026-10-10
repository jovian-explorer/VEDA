"""Desktop launcher start-up checks (veda.desktop, veda.server)."""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from veda import desktop
from veda.server import free_port


def test_free_port_skips_a_port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        taken = s.getsockname()[1]
        assert free_port(taken, tries=3) != taken


def test_startup_wait_ends_when_the_server_thread_dies():
    """Bug: a server that could not bind (port taken) died silently and the launcher waited
    the full two minutes before saying the server did not start."""
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    t0 = time.time()
    assert not desktop._wait_until_up("http://127.0.0.1:9/api/health", "abc", dead, timeout=30)
    assert time.time() - t0 < 5


def test_startup_wait_ignores_another_program_on_the_port():
    """Another server answering /api/health with 200 was taken for this launch's backend."""
    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "launch_id": "someone-else"}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    alive = threading.Thread(target=time.sleep, args=(10,), daemon=True)
    alive.start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/api/health"
        assert not desktop._wait_until_up(url, "mine", alive, timeout=1.5)
        assert desktop._wait_until_up(url, "someone-else", alive, timeout=5)
    finally:
        srv.shutdown()
        srv.server_close()                 # (its listening socket: ResourceWarning otherwise)


def test_health_reports_the_launch_id(monkeypatch):
    from fastapi.testclient import TestClient
    from veda.api.app import create_app
    monkeypatch.setenv("VEDA_LAUNCH_ID", "launch-123")
    assert TestClient(create_app()).get("/api/health").json()["launch_id"] == "launch-123"


def test_backend_moves_to_the_next_port_when_its_port_is_taken_first(monkeypatch):
    """Two launches at once: both found 8765 free and the second's server could not bind
    it, so that launch stopped with 'could not start on port 8765' (the frozen-build launch
    tests failed this way when two runs overlapped)."""
    tried = []

    def serve(host, port):
        tried.append(port)
        if len(tried) == 1:
            desktop._server_error.append(SystemExit(3))       # the other launch bound it first

    monkeypatch.setattr(desktop, "_serve", serve)
    monkeypatch.setattr(desktop, "free_port", lambda p: p)
    monkeypatch.setattr(desktop, "_wait_until_up", lambda url, lid, server, **k: (server.join() or not desktop._server_error))
    assert desktop._start_backend("127.0.0.1", 8765, False, "x") == (8766, True)
    assert tried == [8765, 8766]
    tried.clear()
    assert desktop._start_backend("127.0.0.1", 8765, True, "x") == (8765, False)       # --port: no other port
