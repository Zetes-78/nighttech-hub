"""Printable paperwork: Certificate of Data Wipe, Drop-Off Release and ticket labels."""
import io
import os
from reportlab.graphics.barcode import code128
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(BASE, "static", "logo-full.png")
ICON = os.path.join(BASE, "static", "logo-icon.png")
NAVY = HexColor("#1a365d"); ORANGE = HexColor("#ff6b35"); GRAY = HexColor("#6b7a90")
LINE = HexColor("#9fb0c6"); PALE = HexColor("#eef4fb")
W, H = letter
M = 54
CW = W - 2 * M
F, FB = "Helvetica", "Helvetica-Bold"

SHOP = {"name": "Night Tech Solutions", "phone": "(864) 381-8510", "email": "nighttechsolutions1@gmail.com",
        "web": "nighttech.solutions", "area": "Serving all of the Upstate, SC",
        "dropoff_note": "Please keep this receipt. Call or text {phone} with your ticket number to check on your repair.\nPhone, tablet and game console repair is drop-off only. Please back up anything important."}


def configure(d):
    """Use the shop details saved in Settings on every printed form."""
    SHOP.update({k: v for k, v in d.items() if v})


def _contact_line():
    return "%s   |   %s   |   %s" % (SHOP["name"], SHOP["phone"], SHOP["web"])


def _date(s):
    return (s or "")[:10]


def _label(c, x, y, t):
    c.setFillColor(GRAY); c.setFont(FB, 8.5); c.drawString(x, y, t.upper())


def _line(c, x, y, w):
    c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(x, y, x + w, y)


def _value(c, x, y, text, w, size=10.5):
    """Print prefilled text on top of a field line, shrinking to fit."""
    if not text:
        return
    text = str(text).replace("\n", " ")
    while size > 6 and c.stringWidth(text, F, size) > w - 2:
        size -= 0.5
    c.setFillColor(NAVY); c.setFont(F, size); c.drawString(x + 1, y + 3, text)


def _field(c, x, y, w, label, value=""):
    _label(c, x, y + 13, label); _line(c, x, y, w); _value(c, x, y, value, w)


def _box(c, x, y, text="", checked=False, size=10.5):
    c.setStrokeColor(NAVY); c.setLineWidth(1); c.rect(x, y - 2, 10, 10, stroke=1, fill=0)
    if checked:
        c.setLineWidth(1.8); c.line(x + 2, y + 3, x + 4.5, y); c.line(x + 4.5, y, x + 9, y + 8)
    if text:
        c.setFillColor(NAVY); c.setFont(F, size); c.drawString(x + 16, y, text)


def _heading(c, y, t):
    c.setFillColor(NAVY); c.setFont(FB, 13); c.drawString(M, y, t)
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.line(M, y - 5, M + c.stringWidth(t, FB, 13), y - 5)


def _header(c, title, sub2):
    HB = 92
    c.setFillColor(NAVY); c.rect(0, H - HB, W, HB, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(0, H - HB - 4, W, 4, stroke=0, fill=1)
    c.setFillColor(white); c.roundRect(M, H - HB + 10, 72, 72, 10, stroke=0, fill=1)
    c.drawImage(LOGO, M + 4, H - HB + 14, width=64, height=64, preserveAspectRatio=True, mask="auto")
    c.setFillColor(white); c.setFont(FB, 22); c.drawString(M + 88, H - 44, title)
    c.setFont(F, 11); c.setFillColor(HexColor("#dbe7f5"))
    c.drawString(M + 88, H - 62, _contact_line())
    c.drawString(M + 88, H - 79, sub2)
    return H - HB - 44


def _footer(c):
    c.setFillColor(GRAY); c.setFont(F, 8.5)
    c.drawString(M, 26, "%s   |   %s   |   %s   |   %s" % (SHOP["name"], SHOP["phone"], SHOP["email"], SHOP["web"]))


def _wrap(c, text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def certificate(ticket, customer, devices):
    """One Certificate of Data Wipe page per device."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Certificate of Data Wipe - %s" % ticket["number"]); c.setAuthor(SHOP["name"])
    devices = devices or [None]
    for d in devices:
        y = _header(c, "Certificate of Data Wipe", "After-hours IT support and repair   |   " + SHOP["area"])
        contact = " / ".join([x for x in [customer["phone"], customer["email"]] if x])
        _field(c, M, y, 190, "Record number", ticket["number"]); _field(c, M + 216, y, 150, "Date received", _date(ticket["created_at"]))
        _field(c, M + 392, y, CW - 392, "Date completed", _date(ticket["wipe_finished"]))
        y -= 38; _field(c, M, y, 250, "Customer name", customer["name"]); _field(c, M + 276, y, CW - 276, "Phone or email", contact)
        y -= 34; _heading(c, y, "Device")
        y -= 32
        _field(c, M, y, 150, "Device type", d["device_type"] if d else ""); _field(c, M + 176, y, 190, "Make and model", d["make_model"] if d else "")
        _field(c, M + 392, y, CW - 392, "Serial number or IMEI", d["serial"] if d else "")
        y -= 34; _label(c, M, y + 13, "Storage type")
        bx = M
        st = (d["storage_type"] if d else "") or ""
        for t, w in [("Hard drive", 70), ("SSD", 34), ("Phone or tablet memory", 130), ("Other", 40)]:
            _box(c, bx, y, t, checked=(st == t)); bx += w + 36
        y -= 34; _heading(c, y, "Before the wipe")
        y -= 24; _box(c, M, y, "Customer confirmed they backed up anything they want to keep")
        y -= 21; _box(c, M, y, "Customer signed out of their accounts and turned off Find My, Activation Lock or similar")
        y -= 34; _heading(c, y, "The wipe")
        y -= 30; _field(c, M, y, CW, "Wipe method used", ticket["wipe_method"] or "")
        y -= 36; _field(c, M, y, 230, "Wipe started (date and time)", ticket["wipe_started"] or "")
        _field(c, M + 256, y, CW - 256, "Wipe finished (date and time)", ticket["wipe_finished"] or "")
        y -= 26; _box(c, M, y, "Wipe finished and checked", checked=bool(ticket["wipe_checked"]))
        y -= 34; _heading(c, y, "What happened to the device")
        disp = (d["disposition"] if d else "") or ""
        y -= 24; _box(c, M, y, "Returned to customer", checked=(disp == "Returned to customer"))
        y -= 22; _box(c, M, y, "Handed off for reuse or recycling",
                      checked=(disp in ("Handed off for reuse or recycling", "Recycled", "Refurbish", "Parts", "Drive removed")))
        _label(c, M + 262, y, "Handed off to"); _line(c, M + 330, y - 2, CW - 330); _value(c, M + 330, y - 2, ticket["handoff_to"] or "", CW - 330)
        y -= 34; _field(c, M, y, CW, "Notes", (d["notes"] if d else "") or "")
        y -= 26
        c.setFillColor(PALE); c.roundRect(M, y - 52, CW, 62, 8, stroke=0, fill=1)
        c.setFillColor(NAVY); c.setFont(F, 9.5)
        stmt = ("This record shows that %s securely wiped the device listed above on the dates shown, using the method noted. "
                "It documents the work performed. It is not a guarantee that data cannot be recovered by any method.") % SHOP["name"]
        for i, t in enumerate(_wrap(c, stmt, F, 9.5, CW - 24)[:3]):
            c.drawString(M + 12, y - 8 - i * 13, t)
        c.setFont(FB, 9.5); c.drawString(M + 12, y - 8 - 3 * 13 - 1, "Keep this record for your files.")
        y -= 88
        _field(c, M, y, 230, "Technician signature"); _field(c, M + 256, y, 100, "Date"); _field(c, M + 380, y, CW - 380, "Customer signature")
        _footer(c); c.showPage()
    c.save()
    return buf.getvalue()


def release(ticket, customer, devices):
    """Computer Drop-Off and Donation Release, prefilled from the ticket."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Drop-Off and Donation Release - %s" % ticket["number"]); c.setAuthor(SHOP["name"])
    y = _header(c, "Computer Drop-Off and Donation Release", "Desktops and laptops, by appointment   |   " + SHOP["area"])
    contact = " / ".join([x for x in [customer["phone"], customer["email"]] if x])
    _field(c, M, y, 170, "Record number", ticket["number"]); _field(c, M + 196, y, 140, "Date", _date(ticket["created_at"]))
    _field(c, M + 362, y, CW - 362, "Appointment arranged with")
    y -= 36; _field(c, M, y, 250, "Your name", customer["name"]); _field(c, M + 276, y, CW - 276, "Phone or email", contact)
    y -= 32; _heading(c, y, "What you're dropping off")
    desk = sum(1 for d in devices if (d["device_type"] or "") == "Desktop")
    lap = sum(1 for d in devices if (d["device_type"] or "") == "Laptop")
    y -= 30
    _field(c, M, y, 90, "Desktops (how many)", str(desk) if desk else ""); _field(c, M + 116, y, 90, "Laptops (how many)", str(lap) if lap else "")
    ids = "; ".join([("%s %s" % (d["make_model"] or d["device_type"] or "", ("SN " + d["serial"]) if d["serial"] else "")).strip() for d in devices])
    _field(c, M + 232, y, CW - 232, "Makes, models or serial numbers", ids)
    y -= 28; _line(c, M, y, CW)
    y -= 26; _heading(c, y, "Please read and check each box")
    acks = ["I own these computers, or I have permission to donate them.",
            "I understand they are donated and will not be returned to me.",
            "I backed up anything I want to keep. I understand Night Tech Solutions will not recover files from these computers.",
            "I signed out of my accounts, turned off Find My or similar locks, and told Night Tech Solutions about any password that is needed.",
            "I understand computers may be refurbished and reused, or the storage drive removed and the rest recycled, at Night Tech Solutions' discretion.",
            "I am not dropping off swollen or damaged batteries or other hazardous items."]
    acks = [a.replace("Night Tech Solutions", SHOP["name"]) for a in acks]
    y -= 24
    for a in acks:
        ls = _wrap(c, a, F, 10, CW - 22)
        _box(c, M, y); c.setFillColor(NAVY); c.setFont(F, 10)
        for i, t in enumerate(ls):
            c.drawString(M + 18, y - i * 12.5, t)
        y -= 12.5 * len(ls) + 9
    y -= 22
    _field(c, M, y, 230, "Your signature"); _field(c, M + 256, y, 150, "Printed name", customer["name"]); _field(c, M + 432, y, CW - 432, "Date")
    y -= 36
    _field(c, M, y, 230, "Received by (%s)" % SHOP["name"]); _field(c, M + 256, y, 150, "Date received", _date(ticket["created_at"]))
    _field(c, M + 432, y, CW - 432, "Locked in shop (date)")

    def shop_table(top, rows):
        c.setFillColor(PALE); c.roundRect(M, top - 24 - 26 * max(len(rows), 1) - 8, CW, 24 + 26 * max(len(rows), 1) + 30, 8, stroke=0, fill=1)
        c.setFillColor(NAVY); c.setFont(FB, 10.5); c.drawString(M + 12, top, "SHOP USE ONLY")
        cols = [("Serial number", 0), ("Refurbish", 170), ("Parts", 240), ("Drive removed", 290), ("Recycled", 380), ("Date done", 445)]
        c.setFillColor(GRAY); c.setFont(FB, 8)
        for t, x in cols:
            c.drawString(M + 12 + x, top - 16, t.upper())
        ry = top - 34
        for d in rows:
            c.setStrokeColor(LINE); c.setLineWidth(0.7); c.line(M + 12, ry - 6, M + CW - 12, ry - 6)
            if d is not None:
                _value(c, M + 12, ry - 6, d["serial"] or d["make_model"] or "", 150, 9)
                disp = d["disposition"] or ""
                for (t, x), key in zip(cols[1:5], ["Refurbish", "Parts", "Drive removed", "Recycled"]):
                    _box(c, M + 12 + x + 10, ry, checked=(disp == key))
                _value(c, M + 12 + 445, ry - 6, _date(d["disposition_date"]), 70, 9)
            else:
                for t, x in cols[1:5]:
                    _box(c, M + 12 + x + 10, ry)
            ry -= 26

    first = devices[:3] if devices else []
    while len(first) < 3:
        first.append(None)
    shop_table(y - 30, first)
    _footer(c)
    rest = devices[3:] if devices else []
    while rest:
        c.showPage()
        yy = _header(c, "Shop Use (continued)", "Record %s" % ticket["number"])
        chunk, rest = rest[:14], rest[14:]
        shop_table(yy, chunk)
        _footer(c)
    c.showPage(); c.save()
    return buf.getvalue()


def label(ticket, customer, devices):
    """4 x 2.25 inch ticket label with barcode."""
    buf = io.BytesIO()
    w, h = 288, 162
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle("Label - %s" % ticket["number"])
    c.setFillColor(NAVY); c.rect(0, h - 30, w, 30, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(0, h - 33, w, 3, stroke=0, fill=1)
    c.setFillColor(white); c.roundRect(8, h - 27, 24, 24, 4, stroke=0, fill=1)
    c.drawImage(ICON, 10, h - 25, width=20, height=20, preserveAspectRatio=True, mask="auto")
    c.setFont(FB, 11); c.drawString(40, h - 20, SHOP["name"].upper()[:26])
    c.setFont(F, 8); c.drawRightString(w - 8, h - 20, SHOP["phone"])
    c.setFillColor(NAVY); c.setFont(FB, 24); c.drawString(10, h - 62, ticket["number"])
    c.setFont(FB, 10.5); c.drawString(10, h - 78, (customer["name"] or "")[:34])
    d0 = devices[0] if devices else None
    desc = ""
    if d0:
        desc = " ".join([x for x in [d0["device_type"], d0["make_model"]] if x])
        if len(devices) > 1:
            desc += " (+%d more)" % (len(devices) - 1)
    c.setFont(F, 9); c.drawString(10, h - 91, desc[:46])
    c.setFillColor(GRAY); c.setFont(F, 8)
    c.drawString(10, h - 103, "%s   |   In: %s" % ((ticket["service_type"] or "")[:30], _date(ticket["created_at"])))
    bc = code128.Code128(ticket["number"], barHeight=30, barWidth=1.15, quiet=False)
    c.setFillColor(HexColor("#000000"))
    bc.drawOn(c, 10, 12)
    c.setFillColor(NAVY); c.setFont(F, 8); c.drawString(10 + bc.width + 8, 20, ticket["number"])
    c.showPage(); c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ receipts and blank forms
class Blank(dict):
    """A ticket or customer with every field empty, so any form can be printed blank."""
    def __missing__(self, key):
        return ""


def _receipt_half(c, top, title, copy_label, ticket, customer, devices, mode, parts=None, signature=None):
    """Draw one receipt in a 396pt-high region whose top edge is at y=top."""
    x0, w = M, CW
    # header band
    c.setFillColor(NAVY); c.rect(0, top - 56, W, 56, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(0, top - 59, W, 3, stroke=0, fill=1)
    c.setFillColor(white); c.roundRect(x0, top - 50, 44, 44, 7, stroke=0, fill=1)
    c.drawImage(ICON, x0 + 3, top - 47, width=38, height=38, preserveAspectRatio=True, mask="auto")
    c.setFillColor(white); c.setFont(FB, 19); c.drawString(x0 + 58, top - 28, title)
    c.setFont(F, 9.5); c.setFillColor(HexColor("#dbe7f5"))
    c.drawString(x0 + 58, top - 44, _contact_line())
    c.setFillColor(ORANGE); c.roundRect(x0 + w - 104, top - 40, 104, 24, 12, stroke=0, fill=1)
    c.setFillColor(white); c.setFont(FB, 10.5); c.drawCentredString(x0 + w - 52, top - 32, copy_label.upper())
    y = top - 102
    # ticket number + barcode
    _label(c, x0, y + 24, "Ticket number")
    c.setFillColor(NAVY); c.setFont(FB, 26); c.drawString(x0, y, ticket["number"] or "")
    if ticket["number"]:
        bc = code128.Code128(ticket["number"], barHeight=26, barWidth=1.0, quiet=False)
        c.setFillColor(HexColor("#000000")); bc.drawOn(c, x0 + w - bc.width, y - 4)
    y -= 34
    contact = customer["phone"] or customer["email"] or ""
    _field(c, x0, y, 170, "Date and time received" if mode == "dropoff" else "Date and time picked up",
           (ticket["created_at"] or "")[:16] if mode == "dropoff" else "")
    _field(c, x0 + 196, y, 190, "Customer", customer["name"]); _field(c, x0 + 412, y, w - 412, "Phone", contact)
    y -= 26
    c.setFillColor(NAVY); c.setFont(FB, 10.5)
    c.drawString(x0, y, "Items left with us" if mode == "dropoff" else "Items returned")
    c.setStrokeColor(ORANGE); c.setLineWidth(1.6); c.line(x0, y - 3, x0 + 90, y - 3)
    y -= 15
    c.setFont(F, 9.5)
    rows = list(devices or [])
    shown = rows[:4]
    for d in shown:
        label = " ".join([p for p in [d["device_type"], d["make_model"]] if p]) or "Device"
        if d["serial"]:
            label += "   (SN/IMEI " + d["serial"] + ")"
        if mode == "pickup" and d["disposition"]:
            label += "   - " + d["disposition"]
        c.setFillColor(NAVY); c.drawString(x0 + 6, y, "\u2022 " + label[:105]); y -= 13
    if len(rows) > 4:
        c.setFillColor(GRAY); c.drawString(x0 + 6, y, "+ %d more, listed on the ticket" % (len(rows) - 4)); y -= 13
    if not rows:
        for _ in range(3):
            _line(c, x0 + 6, y - 2, w - 6); y -= 14
    y -= 8
    if mode == "dropoff":
        c.setFillColor(NAVY); c.setFont(FB, 9.5); c.drawString(x0, y, "Service:")
        c.setFont(F, 9.5); c.drawString(x0 + 44, y, ticket["service_type"] or "")
        y -= 13
        prob = (ticket["problem"] or "")
        for ln in _wrap(c, prob, F, 9.5, w - 6)[:2] if prob else []:
            c.setFillColor(GRAY); c.drawString(x0, y, ln); y -= 12
        y -= 22
        _field(c, x0, y, w, "Accessories left with the device (chargers, cases, cables)", _get(ticket, "intake_accessories"))
        y -= 26
        _field(c, x0, y, w, "Condition when received (scratches, cracks, missing parts)", _get(ticket, "intake_condition"))
        y -= 20
        c.setFillColor(GRAY); c.setFont(F, 8.8)
        for ln in [l.strip().replace("{phone}", SHOP["phone"]) for l in SHOP["dropoff_note"].split("\n") if l.strip()][:3]:
            c.drawString(x0, y, ln); y -= 11
        y -= 16
    else:
        y -= 16
        _field(c, x0, y, w, "Work performed")
        y -= 26
        plist = ", ".join(["%d x %s" % (p["qty"], p["name"]) for p in (parts or [])])
        _field(c, x0, y, w, "Parts used", plist)
        y -= 26
        q = ticket["quote_amount"]
        _field(c, x0, y, 150, "Quote or total", ("$%.2f" % q) if q not in (None, "") else "")
        _label(c, x0 + 176, y + 13, "Payment")
        bx = x0 + 176
        for t, wd in [("Paid in Square", 90), ("Paid another way", 100), ("Balance due", 80)]:
            _box(c, bx, y + 1, t, size=9.5); bx += wd + 26
        y -= 20
    # signatures
    y -= 10
    signed_at = _get(ticket, "intake_signed_at") if mode == "dropoff" and signature else ""
    _field(c, x0, y, 210, "Customer signature" if mode == "pickup" else "Customer signature (if present)")
    if signed_at:
        try:
            c.drawImage(signature, x0 + 2, y + 1, width=200, height=34, preserveAspectRatio=True, anchor="sw", mask="auto")
        except Exception:
            pass
        c.setFillColor(GRAY); c.setFont(F, 7.5)
        c.drawString(x0, y - 9, "Signed on screen by %s" % (_get(ticket, "intake_signed_name") or "the customer"))
    _field(c, x0 + 236, y, 110, "Date", signed_at[:10] if signed_at else "")
    _field(c, x0 + 372, y, w - 372, "Received by" if mode == "dropoff" else "Released by")
    if mode == "pickup":
        c.setFillColor(GRAY); c.setFont(F, 8.8); c.drawString(x0, y - 14, "By signing, the customer confirms they received the items listed above.")


def _cut_line(c, y):
    c.setStrokeColor(LINE); c.setDash(4, 4); c.setLineWidth(0.8); c.line(24, y, W - 24, y); c.setDash()
    c.setFillColor(GRAY); c.setFont(F, 8); c.drawCentredString(W / 2, y + 3, "cut or fold here")


def _get(row, key):
    """Read a column that may not exist (blank forms, older rows)."""
    try:
        v = row[key]
    except (KeyError, IndexError, TypeError):
        return ""
    return v or ""


def dropoff_receipt(ticket, customer, devices, copies="both", signature=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Drop-Off Receipt - %s" % (ticket["number"] or "blank")); c.setAuthor(SHOP["name"])
    _receipt_half(c, H, "Drop-Off Receipt", "Customer copy", ticket, customer, devices, "dropoff", signature=signature)
    if copies == "both":
        _cut_line(c, H / 2 + 2)
        _receipt_half(c, H / 2, "Drop-Off Receipt", "Shop copy", ticket, customer, devices, "dropoff", signature=signature)
    c.showPage(); c.save()
    return buf.getvalue()


def pickup_receipt(ticket, customer, devices, parts=None, copies="both"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Pick-Up Receipt - %s" % (ticket["number"] or "blank")); c.setAuthor(SHOP["name"])
    _receipt_half(c, H, "Pick-Up Receipt", "Customer copy", ticket, customer, devices, "pickup", parts)
    if copies == "both":
        _cut_line(c, H / 2 + 2)
        _receipt_half(c, H / 2, "Pick-Up Receipt", "Shop copy", ticket, customer, devices, "pickup", parts)
    c.showPage(); c.save()
    return buf.getvalue()


def estimate(ticket, customer, devices, lines, totals, note=""):
    """One-page estimate from the ticket's quote lines."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Estimate - %s" % (ticket["number"] or "")); c.setAuthor(SHOP["name"])
    y = _header(c, "Estimate", SHOP["area"])
    _field(c, M, y, 150, "Ticket", ticket["number"])
    _field(c, M + 170, y, 200, "Customer", customer["name"])
    _field(c, M + 390, y, CW - 390, "Phone", customer["phone"] or customer["email"] or "")
    y -= 30
    devs = ", ".join(" ".join(p for p in [d["device_type"], d["make_model"]] if p) for d in (devices or [])[:3])
    _field(c, M, y, CW * 0.62, "Device", devs)
    from datetime import date
    _field(c, M + CW * 0.62 + 20, y, CW * 0.38 - 20, "Date", date.today().strftime("%b %d, %Y"))
    y -= 40
    _heading(c, y, "Work and parts")
    y -= 24
    cols = [M, M + CW - 250, M + CW - 175, M + CW - 85]
    c.setFillColor(PALE); c.rect(M, y - 6, CW, 20, stroke=0, fill=1)
    c.setFillColor(NAVY); c.setFont(FB, 9.5)
    c.drawString(cols[0] + 6, y, "Description"); c.drawRightString(cols[1] + 50, y, "Qty")
    c.drawRightString(cols[2] + 70, y, "Price"); c.drawRightString(M + CW - 6, y, "Amount")
    y -= 22
    c.setFont(F, 10)
    for ln in lines[:22]:
        amt = ln["qty"] * ln["unit_price"]
        desc = ln["description"] + ("" if ln["taxable"] else "  (not taxed)")
        while c.stringWidth(desc, F, 10) > cols[1] - cols[0] - 20 and len(desc) > 4:
            desc = desc[:-2]
        c.setFillColor(NAVY)
        c.drawString(cols[0] + 6, y, desc)
        q = ("%g" % ln["qty"])
        c.drawRightString(cols[1] + 50, y, q)
        c.drawRightString(cols[2] + 70, y, "$%.2f" % ln["unit_price"])
        c.drawRightString(M + CW - 6, y, "$%.2f" % amt)
        _line(c, M, y - 6, CW)
        y -= 20
    if len(lines) > 22:
        c.setFillColor(GRAY); c.drawString(M + 6, y, "+ %d more line(s), listed on the ticket" % (len(lines) - 22)); y -= 18
    y -= 6
    def total_row(label, value, bold=False):
        nonlocal y
        c.setFillColor(NAVY); c.setFont(FB if bold else F, 12 if bold else 10.5)
        c.drawRightString(M + CW - 110, y, label); c.drawRightString(M + CW - 6, y, value)
        y -= 18 if not bold else 22
    total_row("Subtotal", "$%.2f" % totals["subtotal"])
    rate = ("%g" % totals["rate"])
    total_row("Sales tax (%s%% on $%.2f)" % (rate, totals["taxable"]), "$%.2f" % totals["tax"])
    c.setStrokeColor(ORANGE); c.setLineWidth(1.6); c.line(M + CW - 260, y + 12, M + CW, y + 12)
    total_row("Estimated total", "$%.2f" % totals["total"], bold=True)
    y -= 10
    if note:
        c.setFillColor(GRAY); c.setFont(F, 9.5)
        for ln in _wrap(c, note, F, 9.5, CW)[:4]:
            c.drawString(M, y, ln); y -= 13
    y -= 18
    _field(c, M, y, 250, "Approved by (customer)")
    _field(c, M + 280, y, 120, "Date")
    _footer(c)
    c.showPage(); c.save()
    return buf.getvalue()
