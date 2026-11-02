"""Tests for the 1.1 features: check-in with signature, quote builder, customer texts,
Recovery report import, and upgrading a database made by Hub 1.0 without losing data.

Run from the repository root:  python -m unittest discover -s tests -v
"""
import base64
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A tiny valid PNG (1x1 pixel)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def csrf(html):
    m = re.search(r'name="_csrf" value="([0-9a-f]+)"', html)
    return m.group(1) if m else ""


class HubFeatureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NTHUB_DATA"] = tempfile.mkdtemp(prefix="nthub-feat-")
        sys.path.insert(0, ROOT)
        import importlib
        import db
        importlib.reload(db)
        import app as appmod
        importlib.reload(appmod)
        cls.appmod = appmod
        cls.c = appmod.app.test_client()
        r = cls.c.get("/setup")
        r = cls.c.post("/setup", data={"_csrf": csrf(r.get_data(as_text=True)), "display_name": "Jason", "username": "owner",
                                       "password": "correct-horse-9", "password2": "correct-horse-9"}, follow_redirects=True)
        r = cls.c.post("/login", data={"_csrf": csrf(r.get_data(as_text=True)), "username": "owner", "password": "correct-horse-9"},
                       follow_redirects=True)
        cls.tok = csrf(r.get_data(as_text=True))
        r = cls.c.post("/tickets/new", data={"_csrf": cls.tok, "customer_id": "new", "name": "Pat Example", "phone": "864-555-0123",
                                             "email": "", "notes": "", "ok_to_text": "1", "service_type": "PC or Mac repair",
                                             "problem": "Slow", "priority": "Normal", "dev_type": "Laptop",
                                             "dev_model": "Dell Inspiron", "dev_serial": "SN123", "dev_storage": "SSD"},
                       follow_redirects=True)
        assert r.status_code == 200
        cls.tid = int(re.search(r"/tickets/(\d+)", r.request.path).group(1))

    def post(self, path, **data):
        data["_csrf"] = self.tok
        return self.c.post(path, data=data, follow_redirects=True)

    def ticket(self):
        with self.appmod.app.app_context():
            return self.appmod.get_db().execute("SELECT * FROM tickets WHERE id=?", (self.tid,)).fetchone()

    def test_1_ticket_page_shows_new_cards(self):
        html = self.c.get("/tickets/%d" % self.tid).get_data(as_text=True)
        for section in ['id="intake"', 'id="quote"', 'id="texts"', 'id="recovery"', 'class="sigpad"']:
            self.assertIn(section, html)

    def test_2_checkin_with_signature(self):
        sig = "data:image/png;base64," + base64.b64encode(PNG).decode()
        r = self.post("/tickets/%d/intake" % self.tid, intake_condition="Scratch on lid", intake_accessories="Charger",
                      intake_signed_name="Pat Example", signature=sig)
        self.assertEqual(r.status_code, 200)
        t = self.ticket()
        self.assertEqual(t["intake_condition"], "Scratch on lid")
        self.assertEqual(t["intake_signed_name"], "Pat Example")
        self.assertTrue(t["intake_signature"])
        self.assertEqual(t["status"], "Checked in")
        pdf = self.c.get("/tickets/%d/dropoff-receipt.pdf" % self.tid)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

    def test_3_bad_signature_rejected(self):
        r = self.post("/tickets/%d/intake" % self.tid, intake_signed_name="X", signature="data:image/png;base64,bm90IGEgcG5n")
        self.assertEqual(r.status_code, 400)

    def test_4_quote_totals_and_tax(self):
        self.post("/tickets/%d/quote/add" % self.tid, description="PC cleanup", qty="1", unit_price="50", taxable="1")
        self.post("/tickets/%d/quote/add" % self.tid, description="Data transfer", qty="2", unit_price="12.50")  # not taxed
        with self.appmod.app.test_request_context():
            self.appmod.g.user = {"id": 1}
            lines, tot = self.appmod.quote_totals(self.tid)
        self.assertEqual(len(lines), 2)
        self.assertEqual(tot["subtotal"], 75.0)
        self.assertEqual(tot["taxable"], 50.0)
        self.assertEqual(tot["tax"], 3.0)      # 6% of $50
        self.assertEqual(tot["total"], 78.0)
        self.assertEqual(self.ticket()["quote_amount"], 78.0)
        pdf = self.c.get("/tickets/%d/estimate.pdf" % self.tid)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

    def test_5_texts_fill_in(self):
        html = self.c.get("/tickets/%d" % self.tid).get_data(as_text=True)
        self.assertIn("Hi Pat", html)
        self.assertIn("sms:+18645550123", html)
        r = self.post("/tickets/%d/texted" % self.tid, template="text_received", body="Hi Pat, we got it")
        self.assertIn("Customer texted", self.c.get("/tickets/%d" % self.tid).get_data(as_text=True))

    def test_6_recovery_report_import(self):
        rep = {"tool": "Night Tech Recovery", "toolVersion": "0.1.0", "caseName": "NT-0001-SN123", "status": "CompletedWithBadSectors",
               "source": {"description": "Test SSD (USB)", "serial": "SN123", "length": 1000000, "sectorSize": 512},
               "bytesGood": 998976, "bytesBad": 1024, "bytesPending": 0, "badSectorCount": 2,
               "imageSha256": "ab" * 32, "finished": "2026-11-01T20:00:00"}
        data = ("﻿" + json.dumps(rep)).encode("utf-8")  # .NET writes a BOM
        r = self.c.post("/tickets/%d/recovery" % self.tid, data={"_csrf": self.tok, "file": (io.BytesIO(data), "case-report.json")},
                        content_type="multipart/form-data", follow_redirects=True)
        html = r.get_data(as_text=True)
        self.assertIn("Recovery report added", html)
        self.assertIn("2 unreadable sector(s)", html)
        bad = self.c.post("/tickets/%d/recovery" % self.tid, data={"_csrf": self.tok, "file": (io.BytesIO(b'{"tool":"x"}'), "x.json")},
                          content_type="multipart/form-data", follow_redirects=True)
        self.assertIn("a Night Tech Recovery report.", bad.get_data(as_text=True))

    def _wipe(self, **over):
        rep = {"tool": "Night Tech Wipe", "toolVersion": "0.1.0", "ticket": "NT-0001", "status": "Completed",
               "fullyVerified": True, "verified": True, "method": "Overwrite, 1 pass of zeros, every sector read back and checked",
               "disk": {"model": "WDC WD10EZEX", "serial": "SN123", "sizeBytes": 1000000, "sectorSize": 512, "mediaType": "HDD"},
               "started": "2026-11-01T18:00:00", "finished": "2026-11-01T20:30:00", "bytesWritten": 1000000, "bytesVerified": 1000000,
               "writeErrorSectors": 0, "verifyMismatchSectors": 0, "verifyReadErrorSectors": 0}
        for k, v in over.items():
            if k == "disk": rep["disk"].update(v)
            else: rep[k] = v
        data = ("\ufeff" + json.dumps(rep)).encode("utf-8")
        return self.c.post("/tickets/%d/wipe" % self.tid, data={"_csrf": self.tok, "file": (io.BytesIO(data), "wipe.json")},
                           content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)

    def test_8_wipe_record_fills_the_certificate(self):
        html = self._wipe()
        self.assertIn("Wipe recorded. The Certificate of Data Wipe is filled in.", html)
        t = self.ticket()
        self.assertEqual(t["wipe_checked"], 1)
        self.assertIn("every sector read back and checked on WDC WD10EZEX (S/N SN123)", t["wipe_method"])
        self.assertEqual(t["wipe_started"], "2026-11-01 18:00")
        self.assertEqual(t["wipe_finished"], "2026-11-01 20:30")
        self.assertTrue(self.c.get("/tickets/%d/certificate.pdf" % self.tid).data.startswith(b"%PDF-"))

        # A second drive that didn't finish cleanly turns the "checked" box off for the ticket.
        html = self._wipe(status="CompletedWithErrors", fullyVerified=False, writeErrorSectors=3, disk={"serial": "SN999", "model": "Old HDD"})
        self.assertIn("did NOT finish cleanly", html)
        self.assertEqual(self.ticket()["wipe_checked"], 0)
        self.assertIn("Not fully erased", self.c.get("/tickets/%d" % self.tid).get_data(as_text=True))

    def test_9_wipe_record_that_contradicts_itself_isnt_trusted(self):
        before = self.ticket()["wipe_checked"]
        html = self._wipe(verifyMismatchSectors=2, disk={"serial": "SN777"})   # claims fullyVerified but lists bad sectors
        self.assertIn("did NOT finish cleanly", html)
        html = self._wipe(bytesVerified=500, disk={"serial": "SN778"})          # didn't check the whole drive
        self.assertIn("did NOT finish cleanly", html)
        bad = self.c.post("/tickets/%d/wipe" % self.tid, data={"_csrf": self.tok, "file": (io.BytesIO(b'{"tool":"Night Tech Recovery"}'), "x.json")},
                          content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
        self.assertIn("a Night Tech Wipe record.", bad)

    def test_7_settings_save(self):
        r = self.post("/settings/texts", tax_rate="7", estimate_note="Estimate only.", text_received="Got it, {first}!",
                      text_quote="q", text_parts="p", text_ready="r", text_custom="c")
        self.assertIn("Quotes and customer texts saved", r.get_data(as_text=True))
        self.assertIn("Got it, Pat!", self.c.get("/tickets/%d" % self.tid).get_data(as_text=True))


OLD_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'staff', active INTEGER NOT NULL DEFAULT 1,
  failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT NOT NULL);
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, notes TEXT,
  ok_to_text INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE tickets (id INTEGER PRIMARY KEY, number TEXT UNIQUE, customer_id INTEGER NOT NULL REFERENCES customers(id),
  service_type TEXT NOT NULL, problem TEXT, status TEXT NOT NULL DEFAULT 'New', priority TEXT NOT NULL DEFAULT 'Normal',
  quote_amount REAL, invoice_link TEXT, storage_location TEXT, assigned_to INTEGER REFERENCES users(id), due_date TEXT,
  wipe_method TEXT, wipe_started TEXT, wipe_finished TEXT, wipe_checked INTEGER NOT NULL DEFAULT 0, handoff_to TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT);
CREATE TABLE subscribers (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, interest TEXT, source TEXT, consent_at TEXT,
  consent_note TEXT, status TEXT NOT NULL DEFAULT 'active', unsubscribed_at TEXT, created_at TEXT NOT NULL);
INSERT INTO customers VALUES (1,'Old Customer','8645550000','',NULL,1,'2026-10-20 18:00:00','2026-10-20 18:00:00');
INSERT INTO tickets(id,number,customer_id,service_type,status,created_at,updated_at) VALUES (1,'NT-0001',1,'Data recovery','In progress','2026-10-20 18:00:00','2026-10-20 18:00:00');
"""


class UpgradeTest(unittest.TestCase):
    def test_old_database_is_backed_up_and_upgraded(self):
        data = tempfile.mkdtemp(prefix="nthub-upg-")
        conn = sqlite3.connect(os.path.join(data, "hub.db")); conn.executescript(OLD_SCHEMA); conn.commit(); conn.close()
        code = textwrap.dedent("""
            import sys; sys.path.insert(0, %r)
            import db; db.init_db()
        """ % ROOT)
        env = dict(os.environ, NTHUB_DATA=data)
        subprocess.run([sys.executable, "-c", code], check=True, env=env)
        backups = os.listdir(os.path.join(data, "backups"))
        self.assertEqual(len(backups), 1, "a backup is made before upgrading")
        b = sqlite3.connect(os.path.join(data, "backups", backups[0]))
        self.assertEqual(b.execute("SELECT name FROM customers").fetchone()[0], "Old Customer")
        b.close()
        conn = sqlite3.connect(os.path.join(data, "hub.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets)")]
        for col in ("intake_condition", "intake_signature", "intake_signed_at"):
            self.assertIn(col, cols)
        self.assertEqual(conn.execute("SELECT number, status FROM tickets").fetchone(), ("NT-0001", "In progress"))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"quote_lines", "recovery_reports", "wipe_reports"} <= tables)
        conn.close()
        # Second start: nothing left to upgrade, so no extra backup
        subprocess.run([sys.executable, "-c", code], check=True, env=env)
        self.assertEqual(len(os.listdir(os.path.join(data, "backups"))), 1)
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
