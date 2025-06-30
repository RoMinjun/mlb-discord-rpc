import os
import json
import sys
import time
import subprocess
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from pypresence import Presence
from pypresence.exceptions import PipeClosed

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
if not CLIENT_ID:
    print("CLIENT_ID is not set. Please add it to your .env file.")
    exit(1)


def connect_rpc():
    while True:
        try:
            rpc = Presence(CLIENT_ID)
            rpc.response_timeout = 5
            rpc.connect()
            print("Connected to Discord RPC.")
            return rpc
        except Exception:
            print("Waiting for Discord... retrying in 5s.")
            time.sleep(5)


rpc = connect_rpc()


settings = {
    "mode": "remote",
    "remote_url": "",
    "team": "",
    "timezone": "",
    "live_only": False,
}

process = None


def start_local():
    global process
    if process or not settings["team"]:
        return
    args = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "mlb-discord-rpc.py"),
        "--team",
        settings["team"],
    ]
    if settings["timezone"]:
        args += ["--tz", settings["timezone"]]
    if settings["live_only"]:
        args.append("--live-only")
    if settings["remote_url"]:
        args += ["--remote-url", settings["remote_url"]]
    process = subprocess.Popen(args)


def stop_local():
    global process
    if process:
        process.terminate()
        process.wait()
        process = None


def apply_settings():
    if settings["mode"] == "local":
        start_local()
    else:
        stop_local()


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
        remote_sel = "selected" if settings["mode"] == "remote" else ""
        local_sel = "selected" if settings["mode"] == "local" else ""
        html = (
            "<html><body>\n"
            "<h1>RPC Server</h1>\n"
            "<form method='post' action='/config'>\n"
            "Mode: <select name='mode'>\n"
            f"<option value='remote' {remote_sel}>remote</option>\n"
            f"<option value='local' {local_sel}>local</option>\n"
            "</select><br/>\n"
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
            settings["mode"] = params.get("mode", ["remote"])[0]
            settings["remote_url"] = params.get("remote_url", [""])[0]
            settings["team"] = params.get("team", [""])[0].upper()
            settings["timezone"] = params.get("timezone", [""])[0]
            settings["live_only"] = "live_only" in params
            apply_settings()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        try:
            payload = json.loads(data.decode()) if data else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        try:
            if self.path == "/update":
                rpc.update(**payload)
            elif self.path == "/clear":
                rpc.clear()
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(204)
        except PipeClosed:
            print("Lost Discord RPC connection. Reconnecting...")
            global rpc
            rpc = connect_rpc()
            self.send_response(204)
        except Exception as e:
            print("Error handling request:", e)
            self.send_response(500)
        self.end_headers()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discord RPC bridge server")
    parser.add_argument("--host", default="0.0.0.0", help="listen host")
    parser.add_argument("--port", type=int, default=6463, help="listen port")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    apply_settings()
    print(f"Listening on {args.host}:{args.port}")
    server.serve_forever()
