import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


JOURNAL = Path("/data/events.jsonl")


class Receiver(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok\n")
        else: self.send_error(404)
    def do_POST(self):
        if self.path != "/events": self.send_error(404); return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        print("\n==============================\nDEBEZIUM CDC EVENT\n==============================")
        print("Content-Type:", self.headers.get("Content-Type")); print("Content-Length:", length)
        try:
            event = json.loads(body)
            print(json.dumps(event, indent=2, sort_keys=True))
            with JOURNAL.open("a", encoding="utf-8") as output:
                output.write(json.dumps(event) + "\n")
                output.flush()
                os.fsync(output.fileno())
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("[non-JSON body]"); print(body[:1000])
        except OSError as exc:
            self.send_error(503, f"Journal write failed: {exc}")
            return
        self.send_response(200); self.end_headers(); self.wfile.write(b"accepted\n")
    def log_message(self, format, *args): pass

JOURNAL.parent.mkdir(parents=True, exist_ok=True)
JOURNAL.touch(exist_ok=True)
print(f"CDC receiver listening on 0.0.0.0:3000; journal: {JOURNAL}")
HTTPServer(("0.0.0.0", 3000), Receiver).serve_forever()
