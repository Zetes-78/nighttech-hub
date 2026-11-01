"""Finding and bringing in data from an older (unzipped, start.bat) copy of the Hub."""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importer  # noqa: E402


def make_hub_data(folder, customers=2, tickets=1):
    os.makedirs(os.path.join(folder, "uploads"), exist_ok=True)
    conn = sqlite3.connect(os.path.join(folder, "hub.db"))
    conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, number TEXT)")
    for i in range(customers):
        conn.execute("INSERT INTO customers(name) VALUES (?)", ("Customer %d" % i,))
    for i in range(tickets):
        conn.execute("INSERT INTO tickets(number) VALUES (?)", ("NT-%04d" % (i + 1),))
    conn.commit(); conn.close()
    with open(os.path.join(folder, "secret.key"), "w") as fh:
        fh.write("k")
    with open(os.path.join(folder, "uploads", "photo.jpg"), "wb") as fh:
        fh.write(b"\xff\xd8\xff")


class ImporterTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="nthub-home-")
        self.target = os.path.join(self.home, "AppData", "Local", "Night Tech Hub", "data")
        self.old = os.path.join(self.home, "Downloads", "nighttech-hub", "data")
        make_hub_data(self.old)
        os.environ.pop("NTHUB_NO_IMPORT", None)

    def test_imports_when_installed_copy_is_empty(self):
        make_hub_data(self.target, customers=0, tickets=0)  # fresh install where owner made a new account
        src = importer.bring_in_old_data(self.target, roots=[self.home], say=lambda m: None)
        self.assertEqual(os.path.normcase(src), os.path.normcase(self.old))
        self.assertEqual(importer.record_count(os.path.join(self.target, "hub.db")), 3)
        self.assertTrue(os.path.exists(os.path.join(self.target, "uploads", "photo.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.target, "secret.key")))
        self.assertTrue(os.path.exists(os.path.join(self.old, "hub.db")), "the original is left in place")
        kept = [d for d in os.listdir(os.path.dirname(self.target)) if d.startswith("data-before-import-")]
        self.assertEqual(len(kept), 1, "the empty install data is kept, not deleted")

    def test_imports_when_nothing_installed_yet(self):
        importer.bring_in_old_data(self.target, roots=[self.home], say=lambda m: None)
        self.assertEqual(importer.record_count(os.path.join(self.target, "hub.db")), 3)

    def test_leaves_real_data_alone(self):
        make_hub_data(self.target, customers=1, tickets=0)
        self.assertIsNone(importer.bring_in_old_data(self.target, roots=[self.home], say=lambda m: None))
        self.assertEqual(importer.record_count(os.path.join(self.target, "hub.db")), 1)

    def test_picks_most_recent_copy(self):
        older = os.path.join(self.home, "Desktop", "nighttech-hub-old", "data")
        make_hub_data(older, customers=5)
        past = time.time() - 86400
        os.utime(os.path.join(older, "hub.db"), (past, past))
        copies = importer.find_old_copies(self.target, roots=[self.home])
        self.assertEqual(len(copies), 2)
        self.assertEqual(os.path.normcase(copies[0][0]), os.path.normcase(self.old))

    def test_opt_out(self):
        os.environ["NTHUB_NO_IMPORT"] = "1"
        try:
            self.assertIsNone(importer.bring_in_old_data(self.target, roots=[self.home], say=lambda m: None))
        finally:
            del os.environ["NTHUB_NO_IMPORT"]


if __name__ == "__main__":
    unittest.main()
