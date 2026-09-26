"""
The support form: bug reports, problems and requests for other puzzles.

Messages are emailed to the site owner through Resend (https://resend.com).
Two environment variables turn it on (set them in Vercel, never in code):

    RESEND_API_KEY   the Resend API key
    SUPPORT_EMAIL    where messages go (for the free Resend plan without a
                     verified domain, this must be the Resend account's email)

Optional:
    SUPPORT_FROM      a sender on a domain verified in Resend
                      (default "Cube Solver <onboarding@resend.dev>")
    RESEND_TEMPLATE   the id or alias of a published Resend template made
                      from templates/support_email.html (e.g. support-message).
                      Without it, the server fills that same file itself; if
                      sending with the template fails, it falls back to that.

Every message is also written to the server log, so nothing is lost if email
is not set up yet or Resend is down.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from typing import List

from pydantic import BaseModel, Field

log = logging.getLogger("support")

KINDS = {"bug": "Bug", "problem": "Problem", "request": "Cube request"}
CUBES = ["2x2", "4x4", "5x5", "Mirror cube", "Pyraminx", "Megaminx", "Skewb", "Square-1", "Other"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# a light per-address limit: 5 messages per 10 minutes (per server instance)
_recent = defaultdict(deque)
LIMIT, WINDOW = 5, 600


class SupportIn(BaseModel):
    kind: str = Field("bug", max_length=20)
    cubes: List[str] = Field(default_factory=list, max_length=len(CUBES))
    name: str = Field("", max_length=80)
    email: str = Field("", max_length=160)
    message: str = Field("", max_length=4000)
    website: str = Field("", max_length=200)      # honeypot: people never see or fill it
    page: str = Field("", max_length=200)          # where they came from, if known


class SupportError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def check(body: SupportIn) -> SupportIn:
    body.kind = body.kind if body.kind in KINDS else "bug"
    body.cubes = [c for c in body.cubes if c in CUBES]
    body.name, body.email, body.message = body.name.strip(), body.email.strip(), body.message.strip()
    if not body.name:
        raise SupportError(422, "Please add your name.")
    if not EMAIL_RE.match(body.email):
        raise SupportError(422, "Please check your email address.")
    if body.kind == "request" and not body.cubes and not body.message:
        raise SupportError(422, "Pick a cube or tell us which one.")
    if body.kind != "request" and len(body.message) < 5:
        raise SupportError(422, "Please tell us what happened.")
    return body


def rate_limited(ip: str) -> bool:
    now, q = time.time(), _recent[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return True
    q.append(now)
    return False


TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "support_email.html")
# badge colours per kind: (background, text, icon)
BADGE = {"bug": ("#fdecec", "#c62828", "&#128030;"), "problem": ("#fdf3e3", "#b45309", "&#129300;"),
         "request": ("#e9effd", "#2459e0", "&#129513;")}


def variables(body: SupportIn, received: str) -> dict:
    """
    The template's variables for one message, already HTML-escaped: Resend
    puts them in raw, and so does render(). The optional rows are built here
    because Resend templates have no if/else; an empty row is an HTML
    comment, since Resend refuses a variable with no value and no fallback.
    """
    e = lambda v: html.escape(v, quote=True)
    row = lambda label, value: (
        "<tr><td class='muted rule' style='padding:10px 0;border-bottom:1px solid #e3e6eb;color:#5d6673;"
        f"vertical-align:top;'>{label}</td><td class='ink rule' style='padding:10px 0;border-bottom:1px solid "
        f"#e3e6eb;color:#111418;'>{value}</td></tr>")
    chips = "".join(
        "<span class='chip' style='display:inline-block;margin:0 6px 6px 0;padding:4px 10px;border-radius:999px;"
        f"background:#eceff3;color:#111418;font-size:13px;font-weight:600;'>{e(c)}</span>" for c in body.cubes)
    bg, color, icon = BADGE[body.kind]
    kind = KINDS[body.kind]
    return {
        "SUBJECT": e(subject(body)), "KIND": e(kind), "KIND_BG": bg, "KIND_COLOR": color, "KIND_ICON": icon,
        "SENDER_NAME": e(body.name),
        "SENDER_FIRST": e(body.name.split()[0] if body.name.split() else body.name),
        "SENDER_EMAIL": e(body.email), "RECEIVED": e(received),
        "REPLY_SUBJECT": urllib.parse.quote(f"Re: your Cube Solver {kind.lower()}"),
        "MESSAGE": e(body.message or "(no message)").replace("\n", "<br>"),
        "PREHEADER": e((body.message or ", ".join(body.cubes) or kind)[:120]),
        "CUBES_ROW": row("Cubes", chips) if body.cubes else "<!-- no cubes -->",
        "PAGE_ROW": row("Page", e(body.page)) if body.page else "<!-- no page -->",
    }


def render(body: SupportIn, received: str) -> str:
    """The HTML email for one message: templates/support_email.html, filled in."""
    with open(TEMPLATE, encoding="utf-8") as f:
        out = f.read()
    for k, v in variables(body, received).items():
        out = out.replace("{{{" + k + "}}}", v)
    return out


def subject(body: SupportIn) -> str:
    s = f"[Cube Solver] {KINDS[body.kind]}" + (f": {', '.join(body.cubes)}" if body.cubes else "") + f" from {body.name}"
    return s[:180]


def _email(body: SupportIn, use_template: bool) -> dict:
    """
    The Resend request. With a template: its id and our variables (Resend
    does not allow html/text alongside). Without: the same design, filled in
    here, plus a plain-text copy.
    """
    received = time.strftime("Received %d %b %Y, %H:%M UTC", time.gmtime())
    email = {
        "from": os.environ.get("SUPPORT_FROM", "Cube Solver <onboarding@resend.dev>"),
        "to": [os.environ["SUPPORT_EMAIL"]],
        "reply_to": body.email,
        "subject": subject(body),
    }
    if use_template:
        email["template"] = {"id": os.environ["RESEND_TEMPLATE"], "variables": variables(body, received)}
        return email
    rows = [("Type", KINDS[body.kind]), ("Name", body.name), ("Email", body.email)]
    if body.cubes:
        rows.append(("Cubes", ", ".join(body.cubes)))
    if body.page:
        rows.append(("Page", body.page))
    email["html"] = render(body, received)
    email["text"] = "\n".join(f"{k}: {v}" for k, v in rows) + "\n\n" + (body.message or "(no message)")
    return email


def _send(key: str, email: dict) -> bool:
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=json.dumps(email).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "cube-solver-support/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as exc:          # Resend said no: log why
        log.error("support email refused (%s): %s", exc.code, exc.read()[:500].decode("utf-8", "replace"))
        return False
    except (urllib.error.URLError, TimeoutError) as exc:
        log.error("support email failed: %s", exc)
        return False


def deliver(body: SupportIn) -> bool:
    """Log the message, then email it if Resend is set up. True if emailed."""
    log.warning("support message: %s", json.dumps(body.model_dump(exclude={"website"}), ensure_ascii=False))
    key, to = os.environ.get("RESEND_API_KEY"), os.environ.get("SUPPORT_EMAIL")
    if not key or not to:
        return False
    if os.environ.get("RESEND_TEMPLATE") and _send(key, _email(body, use_template=True)):
        return True
    # no template set, or the template send failed (not published, a variable
    # missing...): send the same design filled in here, so nothing is lost
    return _send(key, _email(body, use_template=False))
