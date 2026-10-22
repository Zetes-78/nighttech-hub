"""Tiny, safe Markdown-style renderer for the wiki. Everything is HTML-escaped first."""
import html
import re
from markupsafe import Markup

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text):
    text = html.escape(text, quote=True)

    def link(m):
        label, url = m.group(1), m.group(2)
        if not re.match(r"^(https?://|mailto:|/)", url):
            return m.group(0)
        external = ' target="_blank" rel="noopener noreferrer"' if url.startswith("http") else ""
        return '<a href="%s"%s>%s</a>' % (url, external, label)

    text = _LINK.sub(link, text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    text = _CODE.sub(r"<code>\1</code>", text)
    return text


def render(md):
    out, para, list_kind = [], [], None

    def flush_para():
        if para:
            out.append("<p>%s</p>" % _inline(" ".join(para)))
            para.clear()

    def close_list():
        nonlocal list_kind
        if list_kind:
            out.append("</%s>" % list_kind)
            list_kind = None

    for raw in (md or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush_para(); close_list(); continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            flush_para(); close_list()
            level = len(m.group(1)) + 1
            out.append("<h%d>%s</h%d>" % (level, _inline(m.group(2)), level))
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            flush_para()
            if list_kind != "ul":
                close_list(); out.append("<ul>"); list_kind = "ul"
            out.append("<li>%s</li>" % _inline(m.group(1)))
            continue
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if m:
            flush_para()
            if list_kind != "ol":
                close_list(); out.append("<ol>"); list_kind = "ol"
            out.append("<li>%s</li>" % _inline(m.group(1)))
            continue
        close_list()
        para.append(line.strip())
    flush_para(); close_list()
    return Markup("\n".join(out))
