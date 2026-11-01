"""Smoke tests for Night Tech Hub: setup, sign-in, every page, and every printable form.

Run from the repository root:  python -m unittest discover -s tests -v
"""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp(prefix="nthub-test-")
os.environ["NTHUB_DATA"] = DATA
sys.path.insert(0, ROOT)

from app import app, FORMS  # noqa: E402

PAGES = ["/", "/customers", "/customers/new", "/tickets", "/tickets/new", "/forms", "/files",
         "/wiki", "/settings", "/team", "/mailing-list", "/search?q=test"]


def csrf(html):
    m = re.search(r'name="_csrf" value="([0-9a-f]+)"', html)
    return m.group(1) if m else ""


class HubSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.c = app.test_client()
        r = cls.c.get("/setup")
        r = cls.c.post("/setup", data={"_csrf": csrf(r.get_data(as_text=True)), "display_name": "Test Owner",
                                       "username": "owner", "password": "correct-horse-9",
                                       "password2": "correct-horse-9"}, follow_redirects=True)
        r = cls.c.post("/login", data={"_csrf": csrf(r.get_data(as_text=True)), "username": "owner",
                                       "password": "correct-horse-9"}, follow_redirects=True)
        assert r.status_code == 200

    def test_pages_load(self):
        for p in PAGES:
            with self.subTest(page=p):
                self.assertEqual(self.c.get(p).status_code, 200)

    def test_blank_forms_are_pdfs(self):
        kinds = list(FORMS.keys()) if isinstance(FORMS, dict) else [
            f[0] if isinstance(f, (list, tuple)) else f.get("kind") for f in FORMS]
        self.assertTrue(kinds)
        for k in kinds:
            with self.subTest(form=k):
                r = self.c.get(f"/forms/{k}.pdf")
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.data.startswith(b"%PDF-"))

    def test_backup_download(self):
        r = self.c.get("/backup.zip")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
