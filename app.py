"""Night Tech Hub: customers, tickets, devices, files and know-how for Night Tech Solutions."""
import csv
import hmac
import io
import os
import re
import secrets
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db
import pdfs
import wiki as wikimod

os.makedirs(db.DATA, exist_ok=True)
os.makedirs(db.UPLOADS, exist_ok=True)
db.init_db()

app = Flask(__name__)


def _secret():
    p = os.path.join(db.DATA, "secret.key")
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(secrets.token_bytes(32))
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    with open(p, "rb") as f:
        return f.read()


app.secret_key = _secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("NTHUB_SECURE_COOKIES") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,
)

PUBLIC = {"login", "setup", "static"}


# ---------------------------------------------------------------- helpers
def get_db():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def fmt_dt(s):
    if not s:
        return ""
    try:
        return datetime.strptime(s[:16], "%Y-%m-%d %H:%M").strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
    except ValueError:
        return s


def fmt_date(s):
    if not s:
        return ""
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return s


def money(v):
    return "" if v is None else "${:,.2f}".format(v)


app.jinja_env.globals.update(csrf_token=csrf_token, STATUSES=db.STATUSES,
                             PRIORITIES=db.PRIORITIES, DEVICE_TYPES=db.DEVICE_TYPES, STORAGE_TYPES=db.STORAGE_TYPES,
                             DISPOSITIONS=db.DISPOSITIONS, FILE_CATEGORIES=db.FILE_CATEGORIES,
                             OPEN_STATUSES=db.OPEN_STATUSES, INTERESTS=db.INTERESTS, SUB_SOURCES=db.SUB_SOURCES, TOPICS=db.TOPICS)
app.jinja_env.filters.update(dt=fmt_dt, dateonly=fmt_date, money=money,
                             slug=lambda s: re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-"))


def shop_settings():
    if "shop_cfg" not in g:
        cfg = dict(db.DEFAULT_SETTINGS)
        cfg.update({r["key"]: r["value"] for r in get_db().execute("SELECT key, value FROM settings")})
        g.shop_cfg = cfg
    return g.shop_cfg


def _lines(text, limit=60, maxn=60):
    out = []
    for ln in (text or "").replace("\r", "").split("\n"):
        ln = ln.strip()[:limit]
        if ln and ln not in out:
            out.append(ln)
    return out[:maxn]


def services_list():
    return _lines(shop_settings()["services"]) or list(db.SERVICES)


def locations_list():
    return _lines(shop_settings()["storage_locations"], 80, 100)


def configure_pdfs():
    c = shop_settings()
    pdfs.configure({"name": c["shop_name"], "phone": c["shop_phone"], "email": c["shop_email"], "web": c["shop_web"],
                    "area": c["shop_area"], "dropoff_note": c["dropoff_note"]})


@app.context_processor
def inject_shop():
    c = shop_settings()
    return dict(shop=dict(name=c["shop_name"], phone=c["shop_phone"], email=c["shop_email"], web=c["shop_web"],
                          area=c["shop_area"], hours=c["shop_hours"]),
                SERVICES=services_list(), LOCATIONS=locations_list())


def user_count():
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") and "\\" not in target else url_for("dashboard")


@app.before_request
def guard():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        tok = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        if not tok or not hmac.compare_digest(tok, session.get("_csrf", "")):
            abort(400, "Your session expired or the form was not valid. Go back, refresh the page and try again.")
    if request.endpoint in PUBLIC:
        return
    if user_count() == 0:
        return redirect(url_for("setup"))
    uid = session.get("uid")
    row = get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone() if uid else None
    if row is None:
        session.clear()
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    g.user = row


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                                              "object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.endpoint != "static":
        resp.headers["Cache-Control"] = "no-store"
    return resp


def owner_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if g.user["role"] != "owner":
            abort(403, "Only the owner can do that.")
        return fn(*a, **kw)
    return wrapper


def log_event(ticket_id, kind, detail=""):
    get_db().execute("INSERT INTO events(ticket_id,user_id,kind,detail,created_at) VALUES (?,?,?,?,?)",
                     (ticket_id, g.user["id"], kind, detail[:500], db.now()))


def clean(v, n=500):
    return (v or "").strip()[:n]


def get_ticket_or_404(tid):
    t = get_db().execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
    if t is None:
        abort(404)
    return t


def ticket_bundle(tid):
    d = get_db()
    t = get_ticket_or_404(tid)
    c = d.execute("SELECT * FROM customers WHERE id=?", (t["customer_id"],)).fetchone()
    devs = d.execute("SELECT * FROM devices WHERE ticket_id=? ORDER BY id", (tid,)).fetchall()
    return t, c, devs


# ---------------------------------------------------------------- auth
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if user_count() > 0:
        return redirect(url_for("login"))
    if request.method == "POST":
        name, username, pw, pw2 = clean(request.form.get("display_name"), 80), clean(request.form.get("username"), 40).lower(), request.form.get("password", ""), request.form.get("password2", "")
        if not name or not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
            flash("Enter your name and a username of 3 to 40 letters or numbers.", "error")
        elif len(pw) < 10:
            flash("Use a password with at least 10 characters.", "error")
        elif pw != pw2:
            flash("The two passwords don't match.", "error")
        else:
            get_db().execute("INSERT INTO users(username,password_hash,display_name,role,created_at) VALUES (?,?,?,?,?)",
                             (username, generate_password_hash(pw), name, "owner", db.now()))
            get_db().commit()
            flash("Owner account created. Please sign in.", "ok")
            return redirect(url_for("login"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if user_count() == 0:
        return redirect(url_for("setup"))
    if request.method == "POST":
        username = clean(request.form.get("username"), 40).lower()
        pw = request.form.get("password", "")
        d = get_db()
        u = d.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        locked = bool(u and u["locked_until"] and u["locked_until"] > db.now())
        ok = check_password_hash(u["password_hash"], pw) if u else check_password_hash(generate_password_hash("x"), pw)
        if u and ok and u["active"] and not locked:
            d.execute("UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?", (u["id"],)); d.commit()
            session.clear(); session["uid"] = u["id"]; session.permanent = True; csrf_token()
            return redirect(safe_next(request.args.get("next")))
        if u and not ok:
            n = u["failed_logins"] + 1
            until = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S") if n >= 5 else None
            d.execute("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?", (0 if until else n, until, u["id"])); d.commit()
        flash("Too many tries. Wait 15 minutes and try again." if locked else "That username or password isn't right.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- dashboard + search
@app.route("/")
def dashboard():
    d = get_db()
    counts = {r["status"]: r["n"] for r in d.execute("SELECT status, COUNT(*) n FROM tickets GROUP BY status")}
    ph = ",".join("?" * len(db.OPEN_STATUSES))
    ready = d.execute("SELECT t.*, c.name cname FROM tickets t JOIN customers c ON c.id=t.customer_id WHERE t.status='Ready for pickup' ORDER BY t.updated_at", ()).fetchall()
    cutoff = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    stale = d.execute("SELECT t.*, c.name cname FROM tickets t JOIN customers c ON c.id=t.customer_id WHERE t.status IN (%s) AND t.status!='Ready for pickup' AND t.updated_at < ? ORDER BY t.updated_at LIMIT 8" % ph, (*db.OPEN_STATUSES, cutoff)).fetchall()
    recent = d.execute("SELECT e.*, t.number, t.id tid, c.name cname, u.display_name uname FROM events e JOIN tickets t ON t.id=e.ticket_id JOIN customers c ON c.id=t.customer_id LEFT JOIN users u ON u.id=e.user_id ORDER BY e.id DESC LIMIT 12").fetchall()
    in_shop = d.execute("SELECT COUNT(*) FROM devices dv JOIN tickets t ON t.id=dv.ticket_id WHERE t.status IN (%s)" % ph, db.OPEN_STATUSES).fetchone()[0]
    stats = {"open": sum(counts.get(s, 0) for s in db.OPEN_STATUSES), "customers": d.execute("SELECT COUNT(*) FROM customers").fetchone()[0], "in_shop": in_shop}
    team_size = d.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
    list_count = d.execute("SELECT COUNT(*) FROM subscribers WHERE status='active'").fetchone()[0]
    return render_template("dashboard.html", counts=counts, ready=ready, stale=stale, recent=recent, stats=stats, team_size=team_size, list_count=list_count)


@app.route("/search")
def search():
    q = clean(request.args.get("q"), 80)
    cust, tix, devs = [], [], []
    if q:
        like = "%" + q.replace("%", "").replace("_", "") + "%"
        d = get_db()
        cust = d.execute("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? ORDER BY name LIMIT 25", (like, like, like)).fetchall()
        tix = d.execute("SELECT t.*, c.name cname FROM tickets t JOIN customers c ON c.id=t.customer_id WHERE t.number LIKE ? OR t.problem LIKE ? OR t.storage_location LIKE ? ORDER BY t.id DESC LIMIT 25", (like, like, like)).fetchall()
        devs = d.execute("SELECT dv.*, t.number, c.name cname FROM devices dv JOIN tickets t ON t.id=dv.ticket_id JOIN customers c ON c.id=dv.customer_id WHERE dv.serial LIKE ? OR dv.make_model LIKE ? ORDER BY dv.id DESC LIMIT 25", (like, like)).fetchall()
    return render_template("search.html", q=q, cust=cust, tix=tix, devs=devs)


# ---------------------------------------------------------------- customers
def read_customer_form():
    name = clean(request.form.get("name"), 120)
    email = clean(request.form.get("email"), 120)
    errs = []
    if not name:
        errs.append("Enter the customer's name.")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errs.append("That email address doesn't look right.")
    return dict(name=name, phone=clean(request.form.get("phone"), 40), email=email, notes=clean(request.form.get("notes"), 2000),
                ok_to_text=1 if request.form.get("ok_to_text") else 0), errs


@app.route("/customers")
def customers():
    q = clean(request.args.get("q"), 80)
    like = "%" + q.replace("%", "").replace("_", "") + "%"
    rows = get_db().execute("SELECT c.*, (SELECT COUNT(*) FROM tickets t WHERE t.customer_id=c.id) tickets FROM customers c WHERE (?='' OR c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ?) ORDER BY c.name COLLATE NOCASE LIMIT 300", (q, like, like, like)).fetchall()
    return render_template("customers.html", rows=rows, q=q)


@app.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    form = {}
    if request.method == "POST":
        form, errs = read_customer_form()
        if errs:
            for e in errs:
                flash(e, "error")
        else:
            t = db.now()
            cur = get_db().execute("INSERT INTO customers(name,phone,email,notes,ok_to_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                                   (form["name"], form["phone"], form["email"], form["notes"], form["ok_to_text"], t, t))
            get_db().commit()
            flash("Customer added.", "ok")
            return redirect(url_for("customer_view", cid=cur.lastrowid))
    return render_template("customer_form.html", c=form, mode="new")


@app.route("/customers/<int:cid>")
def customer_view(cid):
    d = get_db()
    c = d.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone() or abort(404)
    tix = d.execute("SELECT * FROM tickets WHERE customer_id=? ORDER BY id DESC", (cid,)).fetchall()
    devs = d.execute("SELECT dv.*, t.number FROM devices dv JOIN tickets t ON t.id=dv.ticket_id WHERE dv.customer_id=? ORDER BY dv.id DESC", (cid,)).fetchall()
    files = d.execute("SELECT * FROM attachments WHERE customer_id=? AND ticket_id IS NULL ORDER BY id DESC", (cid,)).fetchall()
    return render_template("customer.html", c=c, tix=tix, devs=devs, files=files)


@app.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
def customer_edit(cid):
    d = get_db()
    c = d.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone() or abort(404)
    if request.method == "POST":
        form, errs = read_customer_form()
        if errs:
            for e in errs:
                flash(e, "error")
            c = dict(form, id=cid)
        else:
            d.execute("UPDATE customers SET name=?,phone=?,email=?,notes=?,ok_to_text=?,updated_at=? WHERE id=?",
                      (form["name"], form["phone"], form["email"], form["notes"], form["ok_to_text"], db.now(), cid))
            d.commit(); flash("Customer saved.", "ok")
            return redirect(url_for("customer_view", cid=cid))
    return render_template("customer_form.html", c=c, mode="edit")


# ---------------------------------------------------------------- tickets
@app.route("/tickets")
def tickets():
    status = clean(request.args.get("status"), 40) or "open"
    service = clean(request.args.get("service"), 60)
    q = clean(request.args.get("q"), 80)
    sql = "SELECT t.*, c.name cname, (SELECT COUNT(*) FROM devices dv WHERE dv.ticket_id=t.id) ndev FROM tickets t JOIN customers c ON c.id=t.customer_id WHERE 1=1"
    args = []
    if status == "open":
        sql += " AND t.status IN (%s)" % ",".join("?" * len(db.OPEN_STATUSES)); args += db.OPEN_STATUSES
    elif status in db.STATUSES:
        sql += " AND t.status=?"; args.append(status)
    if service in services_list():
        sql += " AND t.service_type=?"; args.append(service)
    if q:
        like = "%" + q.replace("%", "").replace("_", "") + "%"
        sql += " AND (t.number LIKE ? OR c.name LIKE ? OR t.problem LIKE ?)"; args += [like, like, like]
    sql += " ORDER BY t.id DESC LIMIT 300"
    rows = get_db().execute(sql, args).fetchall()
    return render_template("tickets.html", rows=rows, status=status, service=service, q=q)


@app.route("/tickets/new", methods=["GET", "POST"])
def ticket_new():
    d = get_db()
    if request.method == "POST":
        errs = []
        cid = request.form.get("customer_id", "")
        service = request.form.get("service_type", "")
        if service not in services_list():
            errs.append("Choose a service.")
        customer_id = None
        if cid == "new":
            form, cerrs = read_customer_form()
            errs += cerrs
            if not cerrs:
                t = db.now()
                customer_id = d.execute("INSERT INTO customers(name,phone,email,notes,ok_to_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                                        (form["name"], form["phone"], form["email"], form["notes"], form["ok_to_text"], t, t)).lastrowid
        elif cid.isdigit() and d.execute("SELECT 1 FROM customers WHERE id=?", (cid,)).fetchone():
            customer_id = int(cid)
        else:
            errs.append("Choose a customer or add a new one.")
        if errs:
            d.rollback()
            for e in errs:
                flash(e, "error")
        else:
            t = db.now()
            tid = d.execute("INSERT INTO tickets(customer_id,service_type,problem,status,priority,storage_location,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (customer_id, service, clean(request.form.get("problem"), 3000), "New",
                             request.form.get("priority") if request.form.get("priority") in db.PRIORITIES else "Normal",
                             clean(request.form.get("storage_location"), 120), t, t)).lastrowid
            number = "NT-%04d" % tid
            d.execute("UPDATE tickets SET number=? WHERE id=?", (number, tid))
            types, models, serials, stores = (request.form.getlist(k) for k in ("dev_type", "dev_model", "dev_serial", "dev_storage"))
            n = 0
            for i in range(min(len(types), 25)):
                m, s = clean(models[i] if i < len(models) else "", 120), clean(serials[i] if i < len(serials) else "", 80)
                dtype = types[i] if types[i] in db.DEVICE_TYPES else ""
                if not (m or s or dtype):
                    continue
                st = stores[i] if i < len(stores) and stores[i] in db.STORAGE_TYPES else ""
                d.execute("INSERT INTO devices(ticket_id,customer_id,device_type,make_model,serial,storage_type,created_at) VALUES (?,?,?,?,?,?,?)",
                          (tid, customer_id, dtype, m, s, st, t))
                n += 1
            d.commit()
            log_event(tid, "Ticket created", "%s, %d device(s)" % (service, n)); d.commit()
            flash("Ticket %s created." % number, "ok")
            return redirect(url_for("ticket_view", tid=tid))
    custs = d.execute("SELECT id, name, phone FROM customers ORDER BY name COLLATE NOCASE").fetchall()
    return render_template("ticket_new.html", custs=custs, pre=request.args.get("customer", ""))


@app.route("/tickets/<int:tid>")
def ticket_view(tid):
    d = get_db()
    t, c, devs = ticket_bundle(tid)
    notes = d.execute("SELECT n.*, u.display_name uname FROM notes n LEFT JOIN users u ON u.id=n.user_id WHERE ticket_id=? ORDER BY n.id DESC", (tid,)).fetchall()
    events = d.execute("SELECT e.*, u.display_name uname FROM events e LEFT JOIN users u ON u.id=e.user_id WHERE ticket_id=? ORDER BY e.id DESC", (tid,)).fetchall()
    parts = d.execute("SELECT * FROM parts WHERE ticket_id=? ORDER BY id", (tid,)).fetchall()
    times = d.execute("SELECT te.*, u.display_name uname FROM time_entries te LEFT JOIN users u ON u.id=te.user_id WHERE ticket_id=? ORDER BY te.id DESC", (tid,)).fetchall()
    files = d.execute("SELECT * FROM attachments WHERE ticket_id=? ORDER BY id DESC", (tid,)).fetchall()
    users = d.execute("SELECT id, display_name FROM users WHERE active=1 ORDER BY display_name").fetchall()
    parts_total = sum((p["cost"] or 0) * p["qty"] for p in parts)
    minutes = sum(x["minutes"] for x in times)
    return render_template("ticket.html", t=t, c=c, devs=devs, notes=notes, events=events, parts=parts, times=times, files=files,
                           users=users, parts_total=parts_total, minutes=minutes)


@app.route("/tickets/<int:tid>/status", methods=["POST"])
def ticket_status(tid):
    d = get_db(); t = get_ticket_or_404(tid)
    new = request.form.get("status", "")
    if new not in db.STATUSES:
        abort(400, "Unknown status.")
    if new != t["status"]:
        closed = db.now() if new in ("Completed", "Closed", "Cancelled") else None
        d.execute("UPDATE tickets SET status=?, updated_at=?, closed_at=? WHERE id=?", (new, db.now(), closed, tid))
        log_event(tid, "Status changed", "%s to %s" % (t["status"], new))
    note = clean(request.form.get("note"), 2000)
    if note:
        d.execute("INSERT INTO notes(ticket_id,user_id,body,created_at) VALUES (?,?,?,?)", (tid, g.user["id"], note, db.now()))
    d.commit(); flash("Status updated.", "ok")
    return redirect(url_for("ticket_view", tid=tid) + "#top")


@app.route("/tickets/<int:tid>/update", methods=["POST"])
def ticket_update(tid):
    d = get_db(); t = get_ticket_or_404(tid)
    f = request.form
    quote = f.get("quote_amount", "").strip().replace("$", "").replace(",", "")
    try:
        quote_val = float(quote) if quote else None
        if quote_val is not None and (quote_val < 0 or quote_val > 1000000):
            raise ValueError
    except ValueError:
        flash("Enter the quote as a number, like 85 or 85.50.", "error")
        return redirect(url_for("ticket_view", tid=tid))
    link = clean(f.get("invoice_link"), 300)
    if link and not re.match(r"^https?://", link):
        flash("The invoice link must start with http:// or https://", "error")
        return redirect(url_for("ticket_view", tid=tid))
    due = clean(f.get("due_date"), 10)
    if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        flash("Use the date picker for the due date.", "error")
        return redirect(url_for("ticket_view", tid=tid))
    assigned = f.get("assigned_to", "")
    assigned = int(assigned) if assigned.isdigit() and d.execute("SELECT 1 FROM users WHERE id=? AND active=1", (assigned,)).fetchone() else None
    new = dict(service_type=f.get("service_type") if (f.get("service_type") in services_list() or f.get("service_type") == t["service_type"]) else t["service_type"],
               problem=clean(f.get("problem"), 3000), priority=f.get("priority") if f.get("priority") in db.PRIORITIES else t["priority"],
               quote_amount=quote_val, invoice_link=link, storage_location=clean(f.get("storage_location"), 120), assigned_to=assigned,
               due_date=due or None, wipe_method=clean(f.get("wipe_method"), 300), wipe_started=clean(f.get("wipe_started"), 40),
               wipe_finished=clean(f.get("wipe_finished"), 40), wipe_checked=1 if f.get("wipe_checked") else 0, handoff_to=clean(f.get("handoff_to"), 200))
    labels = {"storage_location": "Storage location", "wipe_method": "Wipe method", "wipe_started": "Wipe started", "wipe_finished": "Wipe finished",
              "wipe_checked": "Wipe checked", "handoff_to": "Handed off to", "priority": "Priority", "service_type": "Service", "assigned_to": "Assigned to",
              "quote_amount": "Quote"}
    for k, label in labels.items():
        if (t[k] or None) != (new[k] or None) and not (k == "wipe_checked" and int(t[k] or 0) == int(new[k])):
            log_event(tid, label + " changed", "%s to %s" % (t[k] if t[k] not in (None, "") else "none", new[k] if new[k] not in (None, "") else "none"))
    sets = ", ".join("%s=?" % k for k in new)
    d.execute("UPDATE tickets SET %s, updated_at=? WHERE id=?" % sets, (*new.values(), db.now(), tid))
    d.commit(); flash("Ticket saved.", "ok")
    return redirect(url_for("ticket_view", tid=tid))


@app.route("/tickets/<int:tid>/note", methods=["POST"])
def ticket_note(tid):
    d = get_db(); get_ticket_or_404(tid)
    body = clean(request.form.get("body"), 4000)
    if body:
        d.execute("INSERT INTO notes(ticket_id,user_id,body,created_at) VALUES (?,?,?,?)", (tid, g.user["id"], body, db.now()))
        d.execute("UPDATE tickets SET updated_at=? WHERE id=?", (db.now(), tid)); d.commit()
    return redirect(url_for("ticket_view", tid=tid) + "#notes")


@app.route("/tickets/<int:tid>/part", methods=["POST"])
def ticket_part(tid):
    d = get_db(); get_ticket_or_404(tid)
    name = clean(request.form.get("name"), 120)
    try:
        qty = max(1, min(999, int(request.form.get("qty") or 1)))
        cost = float((request.form.get("cost") or "0").replace("$", "").replace(",", ""))
        if cost < 0 or cost > 100000:
            raise ValueError
    except ValueError:
        flash("Enter the part cost as a number.", "error")
        return redirect(url_for("ticket_view", tid=tid) + "#parts")
    if name:
        d.execute("INSERT INTO parts(ticket_id,name,qty,cost,created_at) VALUES (?,?,?,?,?)", (tid, name, qty, cost, db.now()))
        log_event(tid, "Part added", "%s x%d" % (name, qty)); d.commit()
    return redirect(url_for("ticket_view", tid=tid) + "#parts")


@app.route("/tickets/<int:tid>/time", methods=["POST"])
def ticket_time(tid):
    d = get_db(); get_ticket_or_404(tid)
    try:
        minutes = int(request.form.get("minutes") or 0)
        if not 1 <= minutes <= 1440:
            raise ValueError
    except ValueError:
        flash("Enter the time in minutes, from 1 to 1440.", "error")
        return redirect(url_for("ticket_view", tid=tid) + "#time")
    d.execute("INSERT INTO time_entries(ticket_id,user_id,minutes,note,created_at) VALUES (?,?,?,?,?)",
              (tid, g.user["id"], minutes, clean(request.form.get("note"), 300), db.now())); d.commit()
    return redirect(url_for("ticket_view", tid=tid) + "#time")


@app.route("/tickets/<int:tid>/devices/add", methods=["POST"])
def device_add(tid):
    d = get_db(); t = get_ticket_or_404(tid)
    f = request.form
    dtype = f.get("device_type") if f.get("device_type") in db.DEVICE_TYPES else ""
    m, s = clean(f.get("make_model"), 120), clean(f.get("serial"), 80)
    if dtype or m or s:
        st = f.get("storage_type") if f.get("storage_type") in db.STORAGE_TYPES else ""
        d.execute("INSERT INTO devices(ticket_id,customer_id,device_type,make_model,serial,storage_type,created_at) VALUES (?,?,?,?,?,?,?)",
                  (tid, t["customer_id"], dtype, m, s, st, db.now()))
        log_event(tid, "Device added", "%s %s %s" % (dtype, m, s)); d.commit()
    return redirect(url_for("ticket_view", tid=tid) + "#devices")


@app.route("/tickets/<int:tid>/devices/<int:did>", methods=["POST"])
def device_update(tid, did):
    d = get_db(); get_ticket_or_404(tid)
    dv = d.execute("SELECT * FROM devices WHERE id=? AND ticket_id=?", (did, tid)).fetchone() or abort(404)
    f = request.form
    disp = f.get("disposition") if f.get("disposition") in db.DISPOSITIONS else dv["disposition"]
    ddate = clean(f.get("disposition_date"), 10)
    if ddate and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ddate):
        ddate = ""
    if disp and not ddate:
        ddate = datetime.now().strftime("%Y-%m-%d")
    if not disp:
        ddate = ""
    dtype = f.get("device_type") if f.get("device_type") in db.DEVICE_TYPES else dv["device_type"]
    st = f.get("storage_type") if f.get("storage_type") in db.STORAGE_TYPES else dv["storage_type"]
    d.execute("UPDATE devices SET device_type=?, make_model=?, serial=?, storage_type=?, disposition=?, disposition_date=?, notes=? WHERE id=?",
              (dtype, clean(f.get("make_model"), 120), clean(f.get("serial"), 80), st, disp, ddate, clean(f.get("notes"), 500), did))
    if disp != (dv["disposition"] or ""):
        log_event(tid, "Device disposition", "%s (%s): %s" % (dv["make_model"] or dv["device_type"] or "device", dv["serial"] or "no serial", disp or "cleared"))
    d.execute("UPDATE tickets SET updated_at=? WHERE id=?", (db.now(), tid)); d.commit()
    flash("Device saved.", "ok")
    return redirect(url_for("ticket_view", tid=tid) + "#devices")


# ---------------------------------------------------------------- paperwork
def _pdf(fn, name, tid):
    configure_pdfs()
    t, c, devs = ticket_bundle(tid)
    data = fn(t, c, devs)
    log_event(tid, "Paperwork printed", name); get_db().commit()
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": 'inline; filename="%s-%s.pdf"' % (name, t["number"])})


@app.route("/tickets/<int:tid>/certificate.pdf")
def pdf_certificate(tid):
    return _pdf(pdfs.certificate, "certificate-of-data-wipe", tid)


@app.route("/tickets/<int:tid>/release.pdf")
def pdf_release(tid):
    return _pdf(pdfs.release, "dropoff-release", tid)


@app.route("/tickets/<int:tid>/label.pdf")
def pdf_label(tid):
    return _pdf(pdfs.label, "label", tid)


# ---------------------------------------------------------------- mailing list
EMAIL_RE = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")


def normalize_topics(value):
    """Keep only known topics. Blank means all three."""
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = re.split(r"[,;|]", value or "")
    chosen = [t for t in db.TOPICS if any(t.lower() == (i or "").strip().lower() for i in items)]
    return ", ".join(chosen or db.TOPICS)


def add_subscriber(email, name, interest, source, note="", topics=None):
    """Returns 'added', 'duplicate', 'unsub' (previously unsubscribed, never re-added) or 'invalid'."""
    d = get_db()
    email = (email or "").strip().lower()
    if len(email) > 120 or not EMAIL_RE.fullmatch(email):
        return "invalid"
    row = d.execute("SELECT status FROM subscribers WHERE email=?", (email,)).fetchone()
    if row:
        return "unsub" if row["status"] == "unsubscribed" else "duplicate"
    interest = interest if interest in db.INTERESTS else "Everything"
    source = source if source in db.SUB_SOURCES else "Other"
    t = db.now()
    consent = ("Agreed to receive email. Recorded by %s. %s" % (g.user["display_name"], clean(note, 200))).strip()
    d.execute("INSERT INTO subscribers(email,name,interest,source,consent_at,consent_note,status,created_at,topics) VALUES (?,?,?,?,?,?,'active',?,?)",
              (email, clean(name, 80), interest, source, t, consent, t, normalize_topics(topics)))
    return "added"


def _tally(results):
    labels = {"added": "added", "duplicate": "already on the list", "unsub": "skipped because they unsubscribed before", "invalid": "skipped (not a valid email)"}
    counts = {k: results.count(k) for k in labels}
    return ", ".join("%d %s" % (counts[k], labels[k]) for k in labels if counts[k]) or "Nothing to add."


@app.route("/mailing-list")
def mailing_list():
    d = get_db()
    q = clean(request.args.get("q"), 80)
    status = request.args.get("status", "active")
    status = status if status in ("active", "unsubscribed", "all") else "active"
    like = "%" + q.replace("%", "").replace("_", "") + "%"
    sql = "SELECT * FROM subscribers WHERE (?='' OR email LIKE ? OR name LIKE ?)"
    args = [q, like, like]
    if status != "all":
        sql += " AND status=?"; args.append(status)
    rows = d.execute(sql + " ORDER BY id DESC LIMIT 500", args).fetchall()
    n_active = d.execute("SELECT COUNT(*) FROM subscribers WHERE status='active'").fetchone()[0]
    n_unsub = d.execute("SELECT COUNT(*) FROM subscribers WHERE status='unsubscribed'").fetchone()[0]
    prefill = {"email": clean(request.args.get("email"), 120), "name": clean(request.args.get("name"), 80)}
    return render_template("mailing.html", rows=rows, q=q, status=status, n_active=n_active, n_unsub=n_unsub, prefill=prefill)


@app.route("/mailing-list/add", methods=["POST"])
def mailing_add():
    f = request.form
    if not f.get("consent"):
        flash("Check the box to confirm this person agreed to receive emails.", "error")
    elif not f.getlist("topics"):
        flash("Pick at least one thing they want to get.", "error")
    else:
        res = add_subscriber(f.get("email"), f.get("name"), f.get("interest"), f.get("source"), f.get("note"), f.getlist("topics"))
        get_db().commit()
        flash({"added": "Added to the mailing list.", "duplicate": "That email is already on the list.",
               "unsub": "That person unsubscribed before, so they can't be added again unless the owner re-subscribes them at their request.",
               "invalid": "That email address doesn't look right."}[res], "ok" if res == "added" else "error")
    return redirect(url_for("mailing_list"))


@app.route("/mailing-list/paste", methods=["POST"])
def mailing_paste():
    f = request.form
    if not f.get("consent"):
        flash("Check the box to confirm these people agreed to receive emails.", "error")
        return redirect(url_for("mailing_list"))
    results = []
    for line in (f.get("lines") or "")[:20000].splitlines()[:300]:
        parts = [p.strip() for p in re.split(r"[,\t]", line)]
        if not parts or not parts[0]:
            continue
        results.append(add_subscriber(parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else "", f.get("source"), "Pasted in bulk", "|".join(parts[3:])))
    get_db().commit()
    flash(_tally(results), "ok")
    return redirect(url_for("mailing_list"))


@app.route("/mailing-list/<int:sid>/unsubscribe", methods=["POST"])
def mailing_unsubscribe(sid):
    d = get_db()
    d.execute("UPDATE subscribers SET status='unsubscribed', unsubscribed_at=? WHERE id=?", (db.now(), sid)); d.commit()
    flash("Unsubscribed. They will never be emailed or re-added by accident.", "ok")
    return redirect(request.form.get("back") if (request.form.get("back") or "").startswith("/") and not (request.form.get("back") or "").startswith("//") else url_for("mailing_list"))


@app.route("/mailing-list/<int:sid>/resubscribe", methods=["POST"])
@owner_required
def mailing_resubscribe(sid):
    if not request.form.get("consent"):
        flash("Check the box to confirm this person asked to rejoin.", "error")
    else:
        d = get_db()
        d.execute("UPDATE subscribers SET status='active', unsubscribed_at=NULL, consent_at=?, consent_note=? WHERE id=?",
                  (db.now(), "Asked to rejoin. Recorded by %s." % g.user["display_name"], sid)); d.commit()
        flash("Re-subscribed.", "ok")
    return redirect(url_for("mailing_list", status="unsubscribed"))


@app.route("/mailing-list/import", methods=["POST"])
@owner_required
def mailing_import():
    if not request.form.get("consent"):
        flash("Check the box to confirm everyone in this file agreed to receive emails.", "error")
        return redirect(url_for("mailing_list"))
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"):
        flash("Choose a .csv file.", "error")
        return redirect(url_for("mailing_list"))
    raw = f.stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        flash("That file is too big (limit 2 MB).", "error")
        return redirect(url_for("mailing_list"))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Save the file as CSV (UTF-8) and try again.", "error")
        return redirect(url_for("mailing_list"))
    reader = csv.DictReader(io.StringIO(text))
    cols = {(c or "").strip().lower(): c for c in (reader.fieldnames or [])}
    email_col = cols.get("email") or cols.get("email address")
    if not email_col:
        flash("The first row of the file must have an Email column.", "error")
        return redirect(url_for("mailing_list"))
    name_col = cols.get("name") or cols.get("first name")
    int_col = cols.get("interest")
    top_col = cols.get("topics")
    results = []
    for i, row in enumerate(reader):
        if i >= 5000:
            break
        results.append(add_subscriber(row.get(email_col), row.get(name_col) if name_col else "", row.get(int_col) if int_col else "", "Import", "Imported from %s" % os.path.basename(f.filename)[:60], row.get(top_col) if top_col else ""))
    get_db().commit()
    flash("Import finished: " + _tally(results), "ok")
    return redirect(url_for("mailing_list"))


@app.route("/export/mailing-list.csv")
@owner_required
def export_mailing_list():
    rows = get_db().execute("SELECT email, name, interest, topics, source, consent_at FROM subscribers WHERE status='active' ORDER BY email").fetchall()
    return _csv_response("mailing-list-active.csv", ["Email", "First name", "Interest", "Topics", "Source", "Consent date"], [tuple(r) for r in rows])


# ---------------------------------------------------------------- forms
FORMS = [
    ("dropoff-receipt", "Drop-Off Receipt", "Proof that a device was received. Customer copy and shop copy on one page. Use \"customer copy only\" to text or email it.", True),
    ("pickup-receipt", "Pick-Up Receipt", "Signed when a customer collects their items. Lists parts used and how it was paid.", True),
    ("release", "Computer Drop-Off and Donation Release", "For old desktops and laptops that are donated. The customer signs it.", False),
    ("certificate", "Certificate of Data Wipe", "A record of a secure wipe. One page per device.", False),
]
FORM_NAMES = {k: n for k, n, _, _ in FORMS}


def render_form(kind, tid=None, copies="both"):
    if kind not in FORM_NAMES:
        abort(404)
    configure_pdfs()
    if tid is None:
        t, c, devs, parts = pdfs.Blank(), pdfs.Blank(), [], []
    else:
        t, c, devs = ticket_bundle(tid)
        parts = get_db().execute("SELECT * FROM parts WHERE ticket_id=? ORDER BY id", (tid,)).fetchall()
    if kind == "dropoff-receipt":
        data = pdfs.dropoff_receipt(t, c, devs, copies)
    elif kind == "pickup-receipt":
        data = pdfs.pickup_receipt(t, c, devs, parts, copies)
    elif kind == "release":
        data = pdfs.release(t, c, devs)
    else:
        data = pdfs.certificate(t, c, devs)
    if tid is not None:
        log_event(tid, "Paperwork printed", FORM_NAMES[kind]); get_db().commit()
    label = t["number"] if tid is not None else "blank"
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": 'inline; filename="%s-%s.pdf"' % (kind, label)})


@app.route("/forms")
def forms():
    tix = get_db().execute("SELECT t.id, t.number, t.status, c.name cname FROM tickets t JOIN customers c ON c.id=t.customer_id ORDER BY t.id DESC LIMIT 200").fetchall()
    return render_template("forms.html", forms=FORMS, tix=tix)


@app.route("/forms/<kind>.pdf")
def form_pdf(kind):
    tid = request.args.get("ticket", "")
    copies = "customer" if request.args.get("copies") == "customer" else "both"
    if tid.isdigit():
        get_ticket_or_404(int(tid))
        return render_form(kind, int(tid), copies)
    return render_form(kind, None, copies)


@app.route("/tickets/<int:tid>/dropoff-receipt.pdf")
def pdf_dropoff_receipt(tid):
    get_ticket_or_404(tid)
    return render_form("dropoff-receipt", tid, "customer" if request.args.get("copies") == "customer" else "both")


@app.route("/tickets/<int:tid>/pickup-receipt.pdf")
def pdf_pickup_receipt(tid):
    get_ticket_or_404(tid)
    return render_form("pickup-receipt", tid, "customer" if request.args.get("copies") == "customer" else "both")


# ---------------------------------------------------------------- files
MAGIC = {"jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG",), "gif": (b"GIF8",), "pdf": (b"%PDF",),
         "webp": (b"RIFF",), "docx": (b"PK",), "xlsx": (b"PK",)}
INLINE = {"jpg", "jpeg", "png", "gif", "webp"}


def save_upload(file, ticket_id=None, customer_id=None, category="General", description=""):
    if not file or not file.filename:
        return None, "Choose a file first."
    name = os.path.basename(file.filename.replace("\\", "/"))
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in db.ALLOWED_UPLOADS:
        return None, "That file type isn't allowed. Allowed: " + ", ".join(sorted(db.ALLOWED_UPLOADS)) + "."
    head = file.stream.read(8); file.stream.seek(0)
    if ext in MAGIC and not any(head.startswith(m) for m in MAGIC[ext]):
        return None, "That file doesn't look like a real ." + ext + " file."
    stored = uuid.uuid4().hex + "." + ext
    file.save(os.path.join(db.UPLOADS, stored))
    size = os.path.getsize(os.path.join(db.UPLOADS, stored))
    cur = get_db().execute("INSERT INTO attachments(ticket_id,customer_id,category,description,original_name,stored_name,content_type,size,uploaded_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (ticket_id, customer_id, category if category in db.FILE_CATEGORIES else "General", clean(description, 300), name[:200], stored,
                            db.ALLOWED_UPLOADS[ext], size, g.user["id"], db.now()))
    get_db().commit()
    return cur.lastrowid, None


@app.route("/tickets/<int:tid>/upload", methods=["POST"])
def ticket_upload(tid):
    t = get_ticket_or_404(tid)
    fid, err = save_upload(request.files.get("file"), tid, t["customer_id"], request.form.get("category", "Photo"), request.form.get("description", ""))
    if err:
        flash(err, "error")
    else:
        log_event(tid, "File added", request.files["file"].filename[:120]); get_db().commit(); flash("File added.", "ok")
    return redirect(url_for("ticket_view", tid=tid) + "#files")


@app.route("/files", methods=["GET", "POST"])
def files():
    d = get_db()
    if request.method == "POST":
        cid = request.form.get("customer_id", "")
        cid = int(cid) if cid.isdigit() and d.execute("SELECT 1 FROM customers WHERE id=?", (cid,)).fetchone() else None
        fid, err = save_upload(request.files.get("file"), None, cid, request.form.get("category", "General"), request.form.get("description", ""))
        flash(err or "File added.", "error" if err else "ok")
        return redirect(url_for("files"))
    q = clean(request.args.get("q"), 80)
    like = "%" + q.replace("%", "").replace("_", "") + "%"
    rows = d.execute("SELECT a.*, t.number, c.name cname FROM attachments a LEFT JOIN tickets t ON t.id=a.ticket_id LEFT JOIN customers c ON c.id=a.customer_id WHERE (?='' OR a.original_name LIKE ? OR a.description LIKE ? OR a.category LIKE ? OR c.name LIKE ? OR t.number LIKE ?) ORDER BY a.id DESC LIMIT 300", (q, like, like, like, like, like)).fetchall()
    custs = d.execute("SELECT id, name FROM customers ORDER BY name COLLATE NOCASE").fetchall()
    return render_template("files.html", rows=rows, q=q, custs=custs)


@app.route("/files/<int:fid>/download")
def file_download(fid):
    a = get_db().execute("SELECT * FROM attachments WHERE id=?", (fid,)).fetchone() or abort(404)
    path = os.path.join(db.UPLOADS, os.path.basename(a["stored_name"]))
    if not os.path.exists(path):
        abort(404)
    ext = a["stored_name"].rsplit(".", 1)[-1]
    return send_file(path, mimetype=a["content_type"], as_attachment=ext not in INLINE, download_name=a["original_name"])


@app.route("/files/<int:fid>/delete", methods=["POST"])
@owner_required
def file_delete(fid):
    d = get_db()
    a = d.execute("SELECT * FROM attachments WHERE id=?", (fid,)).fetchone() or abort(404)
    try:
        os.remove(os.path.join(db.UPLOADS, os.path.basename(a["stored_name"])))
    except OSError:
        pass
    d.execute("DELETE FROM attachments WHERE id=?", (fid,))
    if a["ticket_id"]:
        log_event(a["ticket_id"], "File removed", a["original_name"][:120])
    d.commit(); flash("File deleted.", "ok")
    return redirect(request.form.get("back") if (request.form.get("back") or "").startswith("/") and not (request.form.get("back") or "").startswith("//") else url_for("files"))


# ---------------------------------------------------------------- wiki
def make_slug(title):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "page"
    slug, n = base, 2
    while get_db().execute("SELECT 1 FROM wiki_pages WHERE slug=?", (slug,)).fetchone():
        slug = "%s-%d" % (base, n); n += 1
    return slug


@app.route("/wiki")
def wiki_index():
    q = clean(request.args.get("q"), 80)
    like = "%" + q.replace("%", "").replace("_", "") + "%"
    rows = get_db().execute("SELECT * FROM wiki_pages WHERE (?='' OR title LIKE ? OR body LIKE ?) ORDER BY title COLLATE NOCASE", (q, like, like)).fetchall()
    return render_template("wiki.html", rows=rows, q=q)


@app.route("/wiki/new", methods=["GET", "POST"])
def wiki_new():
    if request.method == "POST":
        title, body = clean(request.form.get("title"), 120), request.form.get("body", "")[:50000]
        if not title:
            flash("Give the page a title.", "error")
        else:
            slug = make_slug(title)
            get_db().execute("INSERT INTO wiki_pages(slug,title,body,updated_by,updated_at) VALUES (?,?,?,?,?)", (slug, title, body, g.user["id"], db.now()))
            get_db().commit()
            return redirect(url_for("wiki_page", slug=slug))
    return render_template("wiki_edit.html", p={"title": request.form.get("title", ""), "body": request.form.get("body", ""), "slug": None})


@app.route("/wiki/<slug>")
def wiki_page(slug):
    p = get_db().execute("SELECT w.*, u.display_name uname FROM wiki_pages w LEFT JOIN users u ON u.id=w.updated_by WHERE slug=?", (slug,)).fetchone() or abort(404)
    return render_template("wiki_page.html", p=p, html=wikimod.render(p["body"]))


@app.route("/wiki/<slug>/edit", methods=["GET", "POST"])
def wiki_edit(slug):
    d = get_db()
    p = d.execute("SELECT * FROM wiki_pages WHERE slug=?", (slug,)).fetchone() or abort(404)
    if request.method == "POST":
        title, body = clean(request.form.get("title"), 120), request.form.get("body", "")[:50000]
        if not title:
            flash("Give the page a title.", "error")
        else:
            d.execute("UPDATE wiki_pages SET title=?, body=?, updated_by=?, updated_at=? WHERE id=?", (title, body, g.user["id"], db.now(), p["id"]))
            d.commit(); flash("Page saved.", "ok")
            return redirect(url_for("wiki_page", slug=slug))
        p = {"title": title, "body": body, "slug": slug}
    return render_template("wiki_edit.html", p=p)


@app.route("/wiki/<slug>/delete", methods=["POST"])
@owner_required
def wiki_delete(slug):
    get_db().execute("DELETE FROM wiki_pages WHERE slug=?", (slug,)); get_db().commit()
    flash("Page deleted.", "ok")
    return redirect(url_for("wiki_index"))


# ---------------------------------------------------------------- settings, users, backup, export
@app.route("/settings")
def settings():
    return render_template("settings.html", cfg=shop_settings(), svc_text="\n".join(services_list()), loc_text="\n".join(locations_list()))


def _save_settings(pairs):
    d = get_db()
    for k, v in pairs.items():
        d.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
    d.commit()


@app.route("/settings/shop", methods=["POST"])
@owner_required
def settings_shop():
    f = request.form
    name, phone, email = clean(f.get("shop_name"), 80), clean(f.get("shop_phone"), 30), clean(f.get("shop_email"), 120)
    web = re.sub(r"^https?://", "", clean(f.get("shop_web"), 120)).rstrip("/")
    if not name:
        flash("The shop name can't be empty.", "error")
    elif email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash("That email address doesn't look right.", "error")
    else:
        _save_settings({"shop_name": name, "shop_phone": phone, "shop_email": email, "shop_web": web,
                        "shop_area": clean(f.get("shop_area"), 120), "shop_hours": clean(f.get("shop_hours"), 120)})
        flash("Shop details saved. They now appear on every printed form.", "ok")
    return redirect(url_for("settings") + "#shop")


@app.route("/settings/lists", methods=["POST"])
@owner_required
def settings_lists():
    services = _lines(request.form.get("services"))
    if not services:
        flash("Keep at least one service in the list.", "error")
    else:
        _save_settings({"services": "\n".join(services), "storage_locations": "\n".join(_lines(request.form.get("storage_locations"), 80, 100))})
        flash("Lists saved.", "ok")
    return redirect(url_for("settings") + "#lists")


@app.route("/settings/receipt", methods=["POST"])
@owner_required
def settings_receipt():
    note = "\n".join(_lines(request.form.get("dropoff_note"), 130, 3)) or db.DEFAULT_SETTINGS["dropoff_note"]
    _save_settings({"dropoff_note": note})
    flash("Receipt wording saved.", "ok")
    return redirect(url_for("settings") + "#receipt")


@app.route("/team")
@owner_required
def team():
    users = get_db().execute("SELECT * FROM users ORDER BY active DESC, display_name").fetchall()
    return render_template("team.html", users=users)


@app.route("/settings/password", methods=["POST"])
def change_password():
    f = request.form
    u = get_db().execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone()
    if not check_password_hash(u["password_hash"], f.get("current", "")):
        flash("Your current password isn't right.", "error")
    elif len(f.get("new", "")) < 10:
        flash("Use a new password with at least 10 characters.", "error")
    elif f.get("new") != f.get("new2"):
        flash("The two new passwords don't match.", "error")
    else:
        get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(f["new"]), u["id"])); get_db().commit()
        flash("Password changed.", "ok")
    return redirect(url_for("settings"))


@app.route("/settings/users/add", methods=["POST"])
@owner_required
def user_add():
    f = request.form
    name, username, pw = clean(f.get("display_name"), 80), clean(f.get("username"), 40).lower(), f.get("password", "")
    role = "owner" if f.get("role") == "owner" else "staff"
    if not name or not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
        flash("Enter a name and a username of 3 to 40 letters or numbers.", "error")
    elif len(pw) < 10:
        flash("Use a starting password with at least 10 characters.", "error")
    elif get_db().execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        flash("That username is already taken.", "error")
    else:
        get_db().execute("INSERT INTO users(username,password_hash,display_name,role,created_at) VALUES (?,?,?,?,?)",
                         (username, generate_password_hash(pw), name, role, db.now())); get_db().commit()
        flash("Added %s. Give them their username and starting password, and ask them to change it in Settings after they sign in." % name, "ok")
    return redirect(url_for("team"))


@app.route("/settings/users/<int:uid>/toggle", methods=["POST"])
@owner_required
def user_toggle(uid):
    if uid == g.user["id"]:
        flash("You can't turn off your own account.", "error")
    else:
        get_db().execute("UPDATE users SET active = 1 - active WHERE id=?", (uid,)); get_db().commit()
        flash("Person updated.", "ok")
    return redirect(url_for("team"))


@app.route("/settings/users/<int:uid>/reset", methods=["POST"])
@owner_required
def user_reset(uid):
    pw = request.form.get("password", "")
    if len(pw) < 10:
        flash("Use a password with at least 10 characters.", "error")
    else:
        get_db().execute("UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL WHERE id=?", (generate_password_hash(pw), uid)); get_db().commit()
        flash("Password reset. Give them the new password.", "ok")
    return redirect(url_for("team"))


@app.route("/backup.zip")
@owner_required
def backup():
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "hub.db")
        src = sqlite3.connect(db.DB_PATH); dst = sqlite3.connect(snap)
        src.backup(dst); dst.close(); src.close()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "hub.db")
            for fn in sorted(os.listdir(db.UPLOADS)):
                z.write(os.path.join(db.UPLOADS, fn), "uploads/" + fn)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="nighttech-hub-backup-%s.zip" % datetime.now().strftime("%Y%m%d-%H%M"))


def _csv_cell(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _csv_response(name, header, rows):
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(header)
    for r in rows:
        w.writerow([_csv_cell(x) for x in r])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="%s"' % name})


@app.route("/export/customers.csv")
@owner_required
def export_customers():
    rows = get_db().execute("SELECT name, phone, email, ok_to_text, notes, created_at FROM customers ORDER BY name").fetchall()
    return _csv_response("customers.csv", ["Name", "Phone", "Email", "OK to text", "Notes", "Added"], [tuple(r) for r in rows])


@app.route("/export/tickets.csv")
@owner_required
def export_tickets():
    rows = get_db().execute("SELECT t.number, c.name, t.service_type, t.status, t.priority, t.quote_amount, t.storage_location, t.created_at, t.closed_at FROM tickets t JOIN customers c ON c.id=t.customer_id ORDER BY t.id").fetchall()
    return _csv_response("tickets.csv", ["Ticket", "Customer", "Service", "Status", "Priority", "Quote", "Storage", "Created", "Closed"], [tuple(r) for r in rows])


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
def problem(e):
    msgs = {404: "We couldn't find that page.", 413: "That file is too big. The limit is 25 MB."}
    text = msgs.get(e.code) or getattr(e, "description", "Something went wrong.")
    return render_template("error.html", code=e.code, text=text), e.code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
