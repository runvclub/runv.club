"""Signup form for runv.club.

It only writes requests into the queue directory. Accounts are made by
`runv-queue approve`, run by hand as root. Mail is sent by root too, this
process never sees the mail credentials.
"""

import configparser
import datetime as dt
import fcntl
import hashlib
import hmac
import json
import math
import os
import pwd
import secrets
import time

from flask import Flask, abort, redirect, render_template, request

import runvcheck
import runvform
import runvtext

CONF = "/etc/runv-join/join.conf"
SECRET = "/etc/runv-join/secret"
QUEUE = "/var/lib/runv-join/queue"
NONCES = "/var/lib/runv-join/nonces"
LOCK = "/var/lib/runv-join/.lock"
# requests waiting from one address (a /64 on IPv6)
PER_VISITOR = 3

app = Flask(__name__)


def conf():
    c = configparser.ConfigParser(interpolation=None)
    c.read(CONF)
    return c["signup"]


def secret():
    with open(SECRET, "rb") as f:
        return f.read().strip()


def form_token():
    return runvform.make(secret())


def token_age(token):
    """Seconds since the form was made, or None if it's not ours or was
    already sent once."""
    age, nonce = runvform.check(secret(), token)
    if age is None:
        return None
    os.makedirs(NONCES, mode=0o700, exist_ok=True)
    cutoff = time.time() - 7200
    for old in os.listdir(NONCES):
        try:
            if os.stat(os.path.join(NONCES, old)).st_mtime < cutoff:
                os.remove(os.path.join(NONCES, old))
        except FileNotFoundError:
            pass
    try:
        os.close(os.open(os.path.join(NONCES, nonce), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        return None
    return age


def visitor():
    """A keyed hash of who's asking, so the limits can count requests per
    address without keeping the address."""
    who = runvtext.visitor(request.headers.get("X-Real-IP", ""))
    return hmac.new(secret(), who.encode(), hashlib.sha256).hexdigest()[:16]


def pending():
    reqs = []
    for name in os.listdir(QUEUE):
        if name.endswith(".json"):
            with open(os.path.join(QUEUE, name)) as f:
                reqs.append(json.load(f))
    return sorted(reqs, key=lambda r: r["created_at"])


def by_token(token):
    if not token.isascii():
        return None, None
    for pos, r in enumerate(pending(), 1):
        if hmac.compare_digest(r["token"], token):
            return pos, r
    return None, None


def save(r):
    path = os.path.join(QUEUE, f"{r['id']}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(r, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def weeks_for(pos):
    return max(1, math.ceil(pos / conf().getint("weekly_cap")))


def state():
    c = conf()
    if c.get("state") != "open":
        return "closed"
    if len(pending()) >= c.getint("queue_max"):
        return "full"
    return "open"


@app.get("/join")
def form():
    return render_template("join.html", state=state(), token=form_token(), errors=[], f={})


@app.post("/join")
def submit():
    st = state()
    if st != "open":
        return render_template("join.html", state=st, token="", errors=[], f={}), 503

    # a page somewhere else (a member's page included, which is sandboxed
    # and says "null") can't send this form from a visitor's browser
    origin = request.headers.get("Origin")
    if origin is not None and origin != conf()["base_url"]:
        abort(403)

    f = request.form
    errors = []
    age = token_age(f.get("t", ""))
    if f.get("website") or age is None or age < conf().getint("min_seconds") or age > 7200:
        # bots, a form left open for hours, or the same form twice. no detail on purpose
        errors.append("Something went wrong with the form, please try again.")

    name = f.get("username", "").strip().lower()
    about = runvtext.clean(f.get("about", "")).strip()
    key = fingerprint = mail = None
    try:
        name = runvcheck.username(name)
        try:
            pwd.getpwnam(name)
            errors.append(f"{name} is taken.")
        except KeyError:
            pass
    except ValueError as e:
        errors.append(str(e))
    try:
        mail = runvcheck.email(f.get("email", ""))
    except ValueError as e:
        errors.append(str(e))
    try:
        key, fingerprint = runvcheck.ssh_key(f.get("key", ""))
    except ValueError as e:
        errors.append(str(e))
    if not about:
        errors.append("Tell us a bit about what you want to do here.")
    elif len(about) > 2000:
        errors.append("That's a lot. Keep it under 2000 characters.")
    if not f.get("rules"):
        errors.append("You need to accept the rules.")

    who = visitor()
    # two requests at once can't both pass the checks below
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        queue = pending()
        if any(r["username"] == name for r in queue):
            errors.append(f"Someone already asked for {name}.")
        if mail and any(r["email"].lower() == mail.lower() for r in queue):
            errors.append("There is already a request with that email in line.")
        if sum(r.get("visitor") == who for r in queue) >= PER_VISITOR:
            errors.append("There are already enough requests in line from where you are.")

        if errors:
            return render_template("join.html", state=st, token=form_token(),
                                   errors=errors, f=f), 400

        r = {
            "id": secrets.token_hex(4),
            "token": secrets.token_urlsafe(24),
            "username": name,
            "email": mail,
            "key": key,
            "key_fingerprint": fingerprint,
            "about": about,
            "former_member": bool(f.get("former")),
            "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "receipt_sent": False,
            "visitor": who,
        }
        save(r)
    return redirect(f"/join/status/{r['token']}", code=303)


@app.get("/join/status/<token>")
def status(token):
    pos, r = by_token(token)
    if not r:
        abort(404)
    return render_template("status.html", r=r, pos=pos, weeks=weeks_for(pos))


@app.route("/join/confirm/<token>", methods=["GET", "POST"])
def confirm(token):
    pos, r = by_token(token)
    if not r:
        abort(404)
    origin = request.headers.get("Origin")
    if request.method == "POST" and origin is not None and origin != conf()["base_url"]:
        abort(403)
    done = False
    # a GET only shows the button, so link scanners in mail clients
    # don't confirm on the person's behalf
    if request.method == "POST" and r.get("reconfirm_sent_at"):
        r["confirmed_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        r.pop("reconfirm_sent_at", None)
        r.pop("reminder_sent_at", None)
        save(r)
        done = True
    return render_template("confirm.html", r=r, pos=pos, done=done,
                           asked=bool(r.get("reconfirm_sent_at")))


@app.get("/join/rules")
def rules():
    return redirect("/rules", code=301)
