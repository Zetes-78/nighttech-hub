"""Start the Night Tech Hub with a production-grade server (works on Windows, Mac and Linux)."""
import os
from waitress import serve
from app import app

host = os.environ.get("NTHUB_HOST", "127.0.0.1")
port = int(os.environ.get("NTHUB_PORT", "5000"))
print("Night Tech Hub is running at http://%s:%d  (press Ctrl+C to stop)" % (host, port))
if host != "127.0.0.1":
    print("WARNING: the Hub is reachable from other devices. Only do this on a network you trust, or use a private tunnel.")
serve(app, host=host, port=port, threads=6)
