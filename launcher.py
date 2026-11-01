"""Night Tech Hub launcher for the Windows installer.

Starts the Hub on this computer and opens it in the browser. Data is kept in
%LOCALAPPDATA%\\Night Tech Hub\\data, outside the program folder, so updating or
uninstalling the program never touches your customers, tickets or settings.
"""
import os
import sys
import socket
import threading
import time
import webbrowser
import urllib.request

HOST = os.environ.get("NTHUB_HOST", "127.0.0.1")
PORT = int(os.environ.get("NTHUB_PORT", "5000"))
URL = "http://127.0.0.1:%d" % PORT


def data_folder():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Night Tech Hub", "data")


if "NTHUB_DATA" not in os.environ:
    os.environ["NTHUB_DATA"] = data_folder()
os.makedirs(os.environ["NTHUB_DATA"], exist_ok=True)


def hub_already_running():
    try:
        with urllib.request.urlopen(URL + "/login", timeout=2) as r:
            return r.status == 200 and b"Night Tech" in r.read(20000)
    except Exception:
        return False


def port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def open_when_ready():
    for _ in range(60):
        if port_in_use():
            webbrowser.open(URL)
            return
        time.sleep(0.5)


def main():
    if os.name == "nt":
        os.system("title Night Tech Hub")
    if hub_already_running():
        print("Night Tech Hub is already running. Opening it in your browser...")
        webbrowser.open(URL)
        time.sleep(2)
        return
    if port_in_use():
        print("Another program is using port %d, so the Hub can't start." % PORT)
        print("Close that program, or ask for help changing the Hub's port.")
        input("Press Enter to close this window.")
        return

    try:
        from importer import bring_in_old_data
        bring_in_old_data(os.environ["NTHUB_DATA"])
    except Exception as e:  # never stop the Hub from starting
        print("Couldn't check for older data: %s" % e)

    from waitress import serve
    from app import app

    print("Night Tech Hub is running at %s" % URL)
    print("Your data is saved in: %s" % os.environ["NTHUB_DATA"])
    print()
    print("Keep this window open while you work. Close it to stop the Hub.")
    if HOST != "127.0.0.1":
        print("WARNING: the Hub is reachable from other devices. Only do this on a network you trust.")
    threading.Thread(target=open_when_ready, daemon=True).start()
    serve(app, host=HOST, port=PORT, threads=6)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Night Tech Hub stopped because of an error:")
        print(e)
        input("Press Enter to close this window.")
        sys.exit(1)
