import os
import sys
import subprocess
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer


def start_script():
    global process
    if process:
        process.terminate()
        process.wait()
        process = None
    if not settings["team"] or not settings["remote_url"]:
        return
    args = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "mlb-discord-rpc.py"),
        "--team",
        settings["team"],
        "--remote-url",
        settings["remote_url"],
    ]
    if settings["timezone"]:
        args += ["--tz", settings["timezone"]]
    if settings["live_only"]:
        args.append("--live-only")
    process = subprocess.Popen(args)


settings = {
    "remote_url": "",
    "team": "",
    "timezone": "",
    "live_only": False,
}
process = None


class Handler(BaseHTTPRequestHandler):
    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        live_checked = "checked" if settings["live_only"] else ""
        html = (
            "<html><body>\n"
            "<h1>RPC Remote Control</h1>\n"
            "<form method='post' action='/config'>\n"
            "Remote URL: <input name='remote_url' value='"
            f"{settings['remote_url']}'/><br/>\n"
            f"Team: <input name='team' value='{settings['team']}'/><br/>\n"
            "Timezone: <input name='timezone' value='"
            f"{settings['timezone']}'/><br/>\n"
            "Live only: <input type='checkbox' name='live_only' "
            f"{live_checked}/><br/>\n"
            "<input type='submit' value='Save'/>\n"
            "</form></body></html>"
        )
        self._send_html(html)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else b""
        if self.path == "/config":
            params = parse_qs(data.decode()) if data else {}
            settings["remote_url"] = params.get("remote_url", [""])[0]
            settings["team"] = params.get("team", [""])[0].upper()
            settings["timezone"] = params.get("timezone", [""])[0]
            settings["live_only"] = "live_only" in params
            start_script()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run RPC script with web UI")
    parser.add_argument("--host", default="0.0.0.0", help="listen host")
    parser.add_argument("--port", type=int, default=8080, help="listen port")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"Listening on {args.host}:{args.port}")
    server.serve_forever()
