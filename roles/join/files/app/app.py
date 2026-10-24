"""Signup form for runv.club.

It only writes requests into the queue directory. Accounts are made by
`runv-queue approve`, run by hand as root. Mail is sent by root too, this
process never sees the mail credentials.
"""

import configparser
import datetime as dt
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

CONF = "/etc/runv-join/join.conf"
SECRET = "/etc/runv-join/secret"
QUEUE = "/var/lib/runv-join/queue"

app = Flask(__name__)


def conf():
    c = configparser.ConfigParser(interpolation=None)
    c.read(CONF)
    return c["signup"]


def secret():
    with open(SECRET, "rb") as f:
        return f.read().strip()


def form_token():
    ts = str(int(time.time()))
    sig = hmac.new(secret(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def token_age(token):
    try:
        ts, sig = token.split(".", 1)
    except ValueError:
        return None
    good = hmac.new(secret(), ts.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return None
    return time.time() - int(ts)


def pending():
    reqs = []
    for name in os.listdir(QUEUE):
        if name.endswith(".json"):
            with open(os.path.join(QUEUE, name)) as f:
                reqs.append(json.load(f))
    return sorted(reqs, key=lambda r: r["created_at"])


def by_token(token):
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

    f = request.form
    errors = []
    age = token_age(f.get("t", ""))
    if f.get("website") or age is None or age < conf().getint("min_seconds") or age > 7200:
        # bots, or a form left open for hours. no detail on purpose
        errors.append("Something went wrong with the form, please try again.")

    name = f.get("username", "").strip().lower()
    about = f.get("about", "").strip()
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

    queue = pending()
    if any(r["username"] == name for r in queue):
        errors.append(f"Someone already asked for {name}.")
    if mail and any(r["email"].lower() == mail.lower() for r in queue):
        errors.append("There is already a request with that email in line.")

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
    return render_template("rules.html")
