from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json

HOST = "127.0.0.1"
PORT = 8000

class Handler(BaseHTTPRequestHandler):
    def _send(self, status=200, data=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/health":
            self._send(200, {
                "ok": True,
                "status": "online"
            })
            return

        if path == "/tools":
            self._send(200, [])
            return

        if path == "/logs":
            lines = 200
            try:
                lines = int(query.get("lines", ["200"])[0])
            except Exception:
                pass

            items = [
                f"ARIA local API online",
                f"Health check OK",
                f"Requested last {lines} lines"
            ]
            self._send(200, items)
            return

        self._send(404, {"error": "not found", "path": path})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._json_body()

        if path == "/chat":
            text = (
                data.get("message")
                or data.get("text")
                or data.get("prompt")
                or ""
            )

            reply = f"ARIA: ты написал '{text}'"

            # ЧАТУ НУЖЕН Map<String, dynamic>
            self._send(200, {
                "ok": True,
                "status": "online",
                "response": reply,
                "reply": reply,
                "message": reply
            })
            return

        self._send(404, {"error": "not found", "path": path})

    def log_message(self, format, *args):
        parsed = urlparse(self.path)
        print(f"REQ: {self.command} {parsed.path}")

if __name__ == "__main__":
    print(f"Running on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
