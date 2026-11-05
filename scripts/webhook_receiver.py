"""Tiny local webhook receiver for verifying SmartOps notifications.

Usage: python scripts/webhook_receiver.py <port> <secret> <output.jsonl>
Appends one JSON line per POST with the arrival time, path, whether the
X-SmartOps-Signature header matched the secret, and the parsed body.
"""
import hashlib
import hmac
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

port, secret, output = int(sys.argv[1]), sys.argv[2], sys.argv[3]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        record = {
            "receivedAt": time.time(),
            "path": self.path,
            "signatureValid": hmac.compare_digest(expected, self.headers.get("X-SmartOps-Signature", "")),
            "body": json.loads(body or b"{}"),
        }
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", port), Handler).serve_forever()
