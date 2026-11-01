"""Find and bring in data from an older copy of Night Tech Hub.

The first versions of the Hub ran from an unzipped folder (start.bat) and kept
their data in a "data" folder next to app.py. The installed version keeps data
in %LOCALAPPDATA%\\Night Tech Hub\\data. If the installed copy starts with no
customers or tickets, this looks for an older copy's data on the same PC and
copies it in. Nothing is ever deleted: the old folder is copied, not moved, and
any existing installed data is renamed and kept.
"""
import os
import pathlib
import shutil
import sqlite3
from datetime import datetime

MAX_DEPTH = 4
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "appdata",
             "node_modules", ".git", ".venv", "venv", "__pycache__", "system volume information"}


def ro_uri(path):
    """Read-only SQLite URI, safe for spaces and odd characters in folder names."""
    return pathlib.Path(os.path.abspath(path)).as_uri() + "?mode=ro"


def record_count(db_path):
    """Customers plus tickets in a Hub database, or -1 if it can't be read as one."""
    try:
        conn = sqlite3.connect(ro_uri(db_path), uri=True, timeout=5)
        try:
            n = 0
            for table in ("customers", "tickets"):
                n += conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
            return n
        finally:
            conn.close()
    except Exception:
        return -1


def is_empty(data_dir):
    db_path = os.path.join(data_dir, "hub.db")
    return not os.path.exists(db_path) or record_count(db_path) <= 0


def search_roots():
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    roots = [home]
    for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(env):
            roots.append(os.environ[env])
    if os.name == "nt":
        drive = os.environ.get("SystemDrive", "C:") + "\\"
        roots.append(drive)
    seen, out = set(), []
    for r in roots:
        key = os.path.normcase(os.path.abspath(r))
        if key not in seen and os.path.isdir(r):
            seen.add(key)
            out.append(r)
    return out


def find_old_copies(exclude, roots=None, max_depth=MAX_DEPTH):
    """Return [(path_to_data_folder, records, modified_time)] for older Hub data folders, best first."""
    exclude = os.path.normcase(os.path.abspath(exclude))
    found, seen = [], set()
    for root in roots if roots is not None else search_roots():
        root = os.path.abspath(root)
        base_depth = root.rstrip("\\/").count(os.sep)
        for cur, dirs, files in os.walk(root):
            depth = cur.rstrip("\\/").count(os.sep) - base_depth
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")] if depth < max_depth else []
            if os.path.basename(cur).lower() == "data" and "hub.db" in files:
                key = os.path.normcase(os.path.abspath(cur))
                if key == exclude or key in seen:
                    continue
                seen.add(key)
                db_path = os.path.join(cur, "hub.db")
                n = record_count(db_path)
                if n > 0:
                    found.append((cur, n, os.path.getmtime(db_path)))
    found.sort(key=lambda x: x[2], reverse=True)  # most recently used first
    return found


def import_from(source, target):
    """Copy an older data folder into target. Any existing target folder is renamed and kept."""
    kept = None
    if os.path.exists(target):
        kept = "%s-before-import-%s" % (target, datetime.now().strftime("%Y%m%d-%H%M%S"))
        os.rename(target, kept)
    os.makedirs(target)
    src_db = sqlite3.connect(ro_uri(os.path.join(source, "hub.db")), uri=True, timeout=10)
    dst_db = sqlite3.connect(os.path.join(target, "hub.db"))
    try:
        src_db.backup(dst_db)  # consistent copy even if the journal is mid-write
    finally:
        dst_db.close()
        src_db.close()
    for name in os.listdir(source):
        if name in ("hub.db", "hub.db-journal", "hub.db-wal", "hub.db-shm"):
            continue
        s, d = os.path.join(source, name), os.path.join(target, name)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    with open(os.path.join(target, "imported-from.txt"), "w", encoding="utf-8") as fh:
        fh.write("Data copied on %s from:\n%s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), source))
        fh.write("The original folder was left in place.\n")
        if kept:
            fh.write("The data that was here before was kept in:\n%s\n" % kept)
    return kept


def bring_in_old_data(target, roots=None, say=print):
    """If the installed Hub has no records yet, find an older copy's data and copy it in. Returns the source or None."""
    if os.environ.get("NTHUB_NO_IMPORT") or not is_empty(target):
        return None
    say("Looking for customer data from an older copy of Night Tech Hub...")
    copies = find_old_copies(target, roots)
    if not copies:
        say("None found. Starting with a new, empty Hub.")
        return None
    source, n, _ = copies[0]
    say("Found %d customers and tickets in: %s" % (n, source))
    kept = import_from(source, target)
    say("Copied it into: %s (the original was left where it was)." % target)
    if kept:
        say("The empty data that was here was kept in: %s" % kept)
    if len(copies) > 1:
        say("Other copies were also found and left alone:")
        for other, m, _ in copies[1:]:
            say("  %s (%d records)" % (other, m))
    say("Sign in with the username and password from that copy.")
    return source
