"""
The support form: bug reports, problems and requests for other puzzles.

Messages are emailed to the site owner through Resend (https://resend.com).
Two environment variables turn it on (set them in Vercel, never in code):

    RESEND_API_KEY   the Resend API key
    SUPPORT_EMAIL    where messages go (for the free Resend plan without a
                     verified domain, this must be the Resend account's email)

Optional: SUPPORT_FROM, a sender on a domain verified in Resend
(default "Cube Solver <onboarding@resend.dev>").

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


def _email(body: SupportIn) -> dict:
    kind = KINDS[body.kind]
    subject = f"[Cube Solver] {kind}" + (f": {', '.join(body.cubes)}" if body.cubes else "") + f" from {body.name}"
    rows = [("Type", kind), ("Name", body.name), ("Email", body.email)]
    if body.cubes:
        rows.append(("Cubes", ", ".join(body.cubes)))
    if body.page:
        rows.append(("Page", body.page))
    table = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#667'>{k}</td><td>{html.escape(v)}</td></tr>"
                    for k, v in rows)
    msg = html.escape(body.message or "(no message)").replace("\n", "<br>")
    text = "\n".join(f"{k}: {v}" for k, v in rows) + "\n\n" + (body.message or "(no message)")
    return {
        "from": os.environ.get("SUPPORT_FROM", "Cube Solver <onboarding@resend.dev>"),
        "to": [os.environ["SUPPORT_EMAIL"]],
        "reply_to": body.email,
        "subject": subject[:180],
        "html": f"<table style='font:14px sans-serif'>{table}</table><p style='font:14px sans-serif'>{msg}</p>",
        "text": text,
    }


def deliver(body: SupportIn) -> bool:
    """Log the message, then email it if Resend is set up. True if emailed."""
    log.warning("support message: %s", json.dumps(body.model_dump(exclude={"website"}), ensure_ascii=False))
    key, to = os.environ.get("RESEND_API_KEY"), os.environ.get("SUPPORT_EMAIL")
    if not key or not to:
        return False
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=json.dumps(_email(body)).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "cube-solver-support/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, TimeoutError) as exc:
        log.error("support email failed: %s", exc)
        return False
