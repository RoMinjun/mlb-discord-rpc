import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pypresence import Presence
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")

rpc = None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode()) if body else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        if rpc is None:
            self.send_response(500)
            self.end_headers()
            return

        if self.path == "/update":
            rpc.update(**payload)
            self.send_response(204)
        elif self.path == "/clear":
            rpc.clear()
            self.send_response(204)
        else:
            self.send_response(404)
        self.end_headers()


def run(host="0.0.0.0", port=6463):
    global rpc
    if not CLIENT_ID:
        raise ValueError("CLIENT_ID is not set in the environment")
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    server = HTTPServer((host, port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    run()
