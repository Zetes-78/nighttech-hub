"""Night Tech Hub: database, constants and starter content."""
import os
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("NTHUB_DATA", os.path.join(BASE, "data"))
UPLOADS = os.path.join(DATA, "uploads")
DB_PATH = os.path.join(DATA, "hub.db")

SHOP = {
    "name": "Night Tech Solutions",
    "phone": "(864) 381-8510",
    "email": "nighttechsolutions1@gmail.com",
    "web": "nighttech.solutions",
    "area": "Serving all of the Upstate, SC",
}

DEFAULT_SETTINGS = {
    "shop_name": SHOP["name"], "shop_phone": SHOP["phone"], "shop_email": SHOP["email"], "shop_web": SHOP["web"],
    "shop_area": SHOP["area"], "shop_hours": "Evenings 6-11 PM, weekends 9 AM-6 PM",
    "services": "\n".join(["PC or Mac repair", "Virus or malware removal", "Data recovery", "Game console repair",
                           "Phone or tablet screen repair", "Network or Wi-Fi", "Secure data wipe", "Old computer drop-off",
                           "New computer setup", "Website or social media", "Business IT", "Other"]),
    "storage_locations": "",
    "dropoff_note": "Please keep this receipt. Call or text {phone} with your ticket number to check on your repair.\nPhone, tablet and game console repair is drop-off only. Please back up anything important.",
    "tax_rate": "6.0",
    "estimate_note": "This is an estimate. The final total may change if the repair needs different work or parts.",
    "text_received": "Hi {first}, this is {shop}. We received your {device} (ticket {ticket}). We'll text you as soon as we know more.",
    "text_quote": "Hi {first}, your estimate for ticket {ticket} is {quote}. Reply YES to go ahead, or call or text {phone} with any questions.",
    "text_parts": "Hi {first}, ticket {ticket} is waiting on a part. We'll let you know as soon as it arrives.",
    "text_ready": "Hi {first}, good news: your {device} (ticket {ticket}) is ready for pickup. Text {phone} to set a pickup time.{paylink}",
    "text_custom": "Hi {first}, this is {shop} about ticket {ticket}. ",
}

# Customer text templates: (setting key, label shown on the ticket)
TEXT_TEMPLATES = [("text_received", "We received it"), ("text_quote", "Estimate ready"), ("text_parts", "Waiting on parts"),
                  ("text_ready", "Ready for pickup"), ("text_custom", "Custom message")]
TEXT_FIELDS = ["first", "name", "shop", "phone", "ticket", "device", "quote", "paylink", "status"]

TOPICS = ["Deals and discounts", "Tech news and tips", "Monthly newsletter"]
INTERESTS = ["Everything", "Home and family tech", "Gaming and consoles", "Small business IT"]
SUB_SOURCES = ["Website form", "In person", "Phone or text", "Customer", "Import", "Other"]

STATUSES = ["New", "Checked in", "In progress", "Waiting on customer", "Waiting on parts",
            "Ready for pickup", "Completed", "Closed", "Cancelled"]
OPEN_STATUSES = ["New", "Checked in", "In progress", "Waiting on customer", "Waiting on parts", "Ready for pickup"]
PRIORITIES = ["Normal", "High", "Low"]
SERVICES = ["PC or Mac repair", "Virus or malware removal", "Data recovery", "Game console repair",
            "Phone or tablet screen repair", "Network or Wi-Fi", "Secure data wipe", "Old computer drop-off",
            "New computer setup", "Website or social media", "Business IT", "Other"]
DEVICE_TYPES = ["Desktop", "Laptop", "Phone", "Tablet", "Game console", "Hard drive or SSD",
                "Router or network gear", "Other"]
STORAGE_TYPES = ["", "Hard drive", "SSD", "Phone or tablet memory", "Other", "None"]
DISPOSITIONS = ["", "Returned to customer", "Refurbish", "Parts", "Drive removed", "Recycled",
                "Handed off for reuse or recycling"]
FILE_CATEGORIES = ["General", "Photo", "Receipt", "Quote or invoice", "Certificate or release", "Signature", "Recovery report",
                   "Vendor or recycler", "Template", "Other"]
ALLOWED_UPLOADS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
                   "webp": "image/webp", "pdf": "application/pdf", "txt": "text/plain",
                   "csv": "text/csv", "json": "application/json", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'staff', active INTEGER NOT NULL DEFAULT 1,
  failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, notes TEXT,
  ok_to_text INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY, number TEXT UNIQUE, customer_id INTEGER NOT NULL REFERENCES customers(id),
  service_type TEXT NOT NULL, problem TEXT, status TEXT NOT NULL DEFAULT 'New', priority TEXT NOT NULL DEFAULT 'Normal',
  quote_amount REAL, invoice_link TEXT, storage_location TEXT, assigned_to INTEGER REFERENCES users(id), due_date TEXT,
  wipe_method TEXT, wipe_started TEXT, wipe_finished TEXT, wipe_checked INTEGER NOT NULL DEFAULT 0, handoff_to TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT);
CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), customer_id INTEGER NOT NULL REFERENCES customers(id),
  device_type TEXT, make_model TEXT, serial TEXT, storage_type TEXT, disposition TEXT, disposition_date TEXT, notes TEXT,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER REFERENCES users(id),
  body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER REFERENCES users(id),
  kind TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parts (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), name TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 1, cost REAL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS time_entries (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER REFERENCES users(id),
  minutes INTEGER NOT NULL, note TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY, ticket_id INTEGER REFERENCES tickets(id), customer_id INTEGER REFERENCES customers(id),
  category TEXT, description TEXT, original_name TEXT NOT NULL, stored_name TEXT NOT NULL, content_type TEXT,
  size INTEGER, uploaded_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wiki_pages (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  updated_by INTEGER REFERENCES users(id), updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, interest TEXT, source TEXT, consent_at TEXT, consent_note TEXT,
  status TEXT NOT NULL DEFAULT 'active', unsubscribed_at TEXT, created_at TEXT NOT NULL, topics TEXT);
CREATE TABLE IF NOT EXISTS quote_lines (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), description TEXT NOT NULL,
  qty REAL NOT NULL DEFAULT 1, unit_price REAL NOT NULL DEFAULT 0, taxable INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_reports (
  id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), attachment_id INTEGER REFERENCES attachments(id),
  case_name TEXT, status TEXT, source TEXT, serial TEXT, bytes_total INTEGER, bytes_good INTEGER, bytes_bad INTEGER,
  bad_sectors INTEGER, sha256 TEXT, finished TEXT, tool_version TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_quote_lines_ticket ON quote_lines(ticket_id);
CREATE INDEX IF NOT EXISTS idx_recovery_ticket ON recovery_reports(ticket_id);
CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_devices_ticket ON devices(ticket_id);
CREATE INDEX IF NOT EXISTS idx_devices_serial ON devices(serial);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON events(ticket_id);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect():
    os.makedirs(UPLOADS, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Columns added after the first release: (table, column, definition)
ADDED_COLUMNS = [
    ("subscribers", "topics", "TEXT"),
    ("tickets", "intake_condition", "TEXT"),
    ("tickets", "intake_accessories", "TEXT"),
    ("tickets", "intake_signed_name", "TEXT"),
    ("tickets", "intake_signed_at", "TEXT"),
    ("tickets", "intake_signature", "TEXT"),
    ("tickets", "intake_by", "INTEGER"),
]
NEW_TABLES = ["quote_lines", "recovery_reports"]


def _pending_upgrades(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "tickets" not in tables:
        return []  # brand-new database, nothing to upgrade
    todo = [t for t in NEW_TABLES if t not in tables]
    for table, col, _ in ADDED_COLUMNS:
        if table in tables and col not in [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]:
            todo.append("%s.%s" % (table, col))
    return todo


def backup_before_upgrade(conn):
    """Copy the whole database to data/backups before changing its structure. Returns the backup path."""
    folder = os.path.join(DATA, "backups")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "hub-before-upgrade-%s.db" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    dest = sqlite3.connect(path)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return path


def init_db():
    conn = connect()
    if _pending_upgrades(conn):
        backup_before_upgrade(conn)
    conn.executescript(SCHEMA)
    for table, col, definition in ADDED_COLUMNS:
        if col not in [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, definition))
    if conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0] == 0:
        t = now()
        for slug, title, body in WIKI_SEED:
            conn.execute("INSERT INTO wiki_pages(slug,title,body,updated_at) VALUES (?,?,?,?)", (slug, title, body, t))
    conn.commit()
    conn.close()


WIKI_SEED = [
("start-here", "Start here", """# Welcome to the Night Tech Hub

This is the shop's home base: customers, tickets, devices, files and procedures in one place.

## How a job flows
1. **Intake.** Create a ticket, add the customer and every device, and print the label.
2. **Work.** Update the status, add notes, parts and time. Everything is logged.
3. **Paperwork.** Print the Certificate of Data Wipe or the Drop-Off Release from the ticket.
4. **Finish.** Mark it Ready for pickup, then Completed. Record payment in Square.

## Good habits
- Log where every device is stored.
- Add a photo when a device comes in.
- Never type customer passwords or passcodes into notes.
- Back up from Settings every week.
"""),
("drop-off-procedure", "Drop-off procedure", """# Drop-off procedure

## When a customer drops something off
1. Customer calls or texts first. We give the drop-off location.
2. Device goes in the white drop box on the porch with name, phone and a note.
3. Customer texts when it is in the box.
4. Collect it, take a photo, and create the ticket right away.
5. Put it on the locked shelf and record the storage location on the ticket.
6. Text the customer that it was received.

## Notes
- Phones, tablets and consoles are drop-off only.
- Check the box at least once a day in the evening.
"""),
("secure-wipe-procedure", "Secure wipe procedure", """# Secure wipe procedure

Use this page to write down exactly how we wipe each type of device. The Certificate of Data Wipe repeats whatever method is entered on the ticket.

## Before the wipe
- Confirm the customer backed up what they want to keep.
- Confirm accounts are signed out and Find My, Activation Lock or similar are off.
- Check the serial number against the ticket.

## Methods we use (fill this in)
- Hard drives: (write the method here)
- SSDs: (write the method here)
- Phones and tablets: (write the method here)

## After the wipe
- Confirm the wipe finished and check the result.
- Record start and finish times on the ticket.
- Print the Certificate of Data Wipe and keep a copy.
"""),
("old-computer-intake", "Old computer drop-off and recycling", """# Old computer drop-off and recycling

## Intake
1. Customer arranges the drop-off by appointment.
2. Create a ticket (service: Old computer drop-off) and add each computer.
3. Print the Computer Drop-Off and Donation Release, and have the customer sign it.
4. Lock the computers in the shop and record the storage location.

## Processing
- **Refurbish:** securely wipe, test, and set up again.
- **Parts:** pull useful parts and log them.
- **Recycle:** remove the storage drive first, then hand off the rest to the recycler.

## Records
- Update each device's disposition and date on the ticket.
- Record who the devices were handed off to.
"""),
("console-repair-checklist", "Game console repair checklist", """# Game console repair checklist

1. Photo of the console as received, including ports.
2. Record serial number and any damage.
3. Check the problem: no picture, charging, overheating, loud fan, controller.
4. Open only after confirming the warranty situation with the customer.
5. After repair, test picture, charging, fan and controller.
6. Photo after repair and note the work done.
"""),
("price-list", "Price list", """# Price list

Only one price is published right now: the **$50 PC cleanup special**.

Add your other prices here when you set them. Do not publish a price on the website or in an ad until it is listed here.

## Sales tax
Square handles tax on invoices. Check your rate with the SC Department of Revenue or your accountant.
"""),
("vendors-and-recyclers", "Vendors and recyclers", """# Vendors and recyclers

Keep contact details and what each one is used for.

## Recycler
- Name:
- What they take:
- Contact:
- Our account or drop-off terms:

## Parts suppliers
- Name:
- What we buy:

## Specialist labs (failed drives)
- Name:
- Contact:
"""),
("accounts-and-links", "Accounts and links", """# Accounts and links

**Do not store passwords here.** Use a password manager.

- Website: [nighttech.solutions](https://nighttech.solutions)
- Facebook Page: [Night Tech Solutions](https://www.facebook.com/profile.php?id=61595228504921)
- Instagram: [@nighttechsolutions1](https://www.instagram.com/nighttechsolutions1/)
- LinkedIn: [Night Tech Solutions](https://www.linkedin.com/company/nighttech-solutions)
- X: [@NightTechSol](https://x.com/NightTechSol)
- Square: [dashboard](https://app.squareup.com/dashboard/)
- Google Voice: [voice.google.com](https://voice.google.com)
- Business email: nighttechsolutions1@gmail.com
"""),
]
