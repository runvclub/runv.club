"""Guestbooks for runv.club members, at runv.club/guestbook/NAME.

A book is off until its owner turns it on with `guestbook on`. Notes wait
until the owner approves them. Nothing here knows who the members are:
a book that isn't on is a 404, like one that doesn't exist.
"""

import configparser
import hashlib
import hmac
import ipaddress
import sqlite3
import time
import unicodedata

from flask import Flask, abort, jsonify, redirect, render_template, request

import gbdb
import runvform

CONF = "/etc/runv-guestbook/guestbook.conf"
SECRET = "/etc/runv-guestbook/secret"

app = Flask(__name__)


def conf():
    c = configparser.ConfigParser(interpolation=None)
    c.read(CONF)
    return c["guestbook"]


def secret():
    with open(SECRET, "rb") as f:
        return f.read().strip()


@app.after_request
def headers(resp):
    resp.headers["Content-Security-Policy"] = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                                               "frame-ancestors 'self'; base-uri 'none'")
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


def clean(text, lines):
    """No control characters, no bidi tricks, at most so many lines."""
    out = []
    for line in text.replace("\r", "").split("\n")[:lines]:
        out.append("".join(ch for ch in line if ch == "\t" or unicodedata.category(ch)[0] != "C").rstrip())
    return "\n".join(out).strip()


def visitor():
    """Who's posting, for the limits: the address, or its /64 on IPv6,
    since one person usually has a whole /64 to hop around in."""
    addr = request.headers.get("X-Real-IP", "")
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return addr
    return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else addr


def book(owner):
    if not gbdb.NAME.fullmatch(owner):
        abort(404)
    c = gbdb.connect()
    if not gbdb.is_open(c, owner):
        abort(404)
    return c


def show(owner, embed, errors=(), f=None, status=200):
    c = book(owner)
    notes = c.execute("select author, body, created from notes where owner = ? and status = 'approved' "
                      "order by created desc limit 200", (owner,)).fetchall()
    return render_template("book.html", owner=owner, embed=embed, notes=notes, errors=errors, f=f or {},
                           token=runvform.make(secret(), owner), sent=request.args.get("sent") == "1",
                           day=lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))), status


@app.get("/guestbook/<owner>")
def page(owner):
    return show(owner, False)


@app.get("/guestbook/<owner>/embed")
def embed(owner):
    return show(owner, True)


@app.get("/guestbook/<owner>.json")
def as_json(owner):
    c = book(owner)
    notes = c.execute("select author, body, created from notes where owner = ? and status = 'approved' "
                      "order by created desc limit 200", (owner,)).fetchall()
    return jsonify([dict(n) for n in notes])


@app.post("/guestbook/<owner>")
@app.post("/guestbook/<owner>/embed")
def sign(owner):
    c = book(owner)
    f = request.form
    embedded = request.path.endswith("/embed")
    age, nonce = runvform.check(secret(), f.get("t", ""), owner)
    author = clean(f.get("author", ""), 1)[:40] or "someone"
    body = clean(f.get("body", ""), 10)
    ip = hmac.new(secret(), visitor().encode(), hashlib.sha256).hexdigest()[:16]
    now = int(time.time())

    ok = not f.get("website") and age is not None and conf().getint("min_seconds") <= age <= 7200
    if ok:
        try:
            with c:
                c.execute("insert into nonces values (?, ?)", (nonce, now))
        except sqlite3.IntegrityError:
            ok = False
    if not ok:
        # bots, a form left open for hours, or the same form twice. no detail on purpose
        return show(owner, embedded, ["Something went wrong with the form, please try again."], f, 400)
    if not body or len(f.get("body", "")) > 500:
        return show(owner, embedded, ["Write something, up to 500 characters."], f, 400)

    day = now - 86400
    here = c.execute("select count(*) from notes where owner = ? and ip_hash = ? and created > ?",
                     (owner, ip, day)).fetchone()[0]
    everywhere = c.execute("select count(*) from notes where ip_hash = ? and created > ?", (ip, day)).fetchone()[0]
    waiting = c.execute("select count(*) from notes where owner = ? and status = 'pending'", (owner,)).fetchone()[0]
    banned = c.execute("select 1 from bans where owner = ? and ip_hash = ?", (owner, ip)).fetchone()
    if here >= 3 or everywhere >= 10 or waiting >= 50:
        return show(owner, embedded, ["That's enough notes for today. Come back tomorrow."], f, 429)
    with c:
        if not banned:
            # a banned visitor sees the same thanks, and the note goes nowhere
            c.execute("insert into notes (owner, created, author, body, ip_hash) values (?, ?, ?, ?, ?)",
                      (owner, now, author, body, ip))
        gbdb.tidy(c)
    gbdb.mark_waiting(c, owner)
    return redirect(request.path + "?sent=1", code=303)
