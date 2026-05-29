from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
PORT = 8787


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/ping":
            self._send_json(200, {"ok": True, "service": "00919-dashboard"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/update":
            self._send_json(404, {"ok": False, "error": "unknown endpoint"})
            return

        try:
            result = subprocess.run(
                [sys.executable, "fetch_data.py"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except Exception as exc:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return

        payload = {
            "ok": result.returncode == 0,
            "returnCode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
        self._send_json(200 if result.returncode == 0 else 500, payload)


def main() -> None:
    server = ThreadingHTTPServer(("localhost", PORT), DashboardHandler)
    print(f"00919 dashboard server running at http://localhost:{PORT}/index.html")
    print("POST /api/update will run fetch_data.py and refresh all dashboard data.")
    server.serve_forever()


if __name__ == "__main__":
    main()
