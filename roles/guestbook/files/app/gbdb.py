"""The guestbook database, shared by the web app and gbctl.

Everything here runs as runvgb, so the files never end up owned by root.
"""

import os
import re
import sqlite3
import time

DIR = "/var/lib/runv-guestbook"
DB = os.path.join(DIR, "db", "gb.db")
WAITING = os.path.join(DIR, "waiting")
NAME = re.compile(r"[a-z][a-z0-9_]{1,15}")
KEEP = 30 * 86400


def connect():
    c = sqlite3.connect(DB, timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("pragma journal_mode = wal")
    c.executescript("""
        create table if not exists books (owner text primary key, enabled int default 0, blocked int default 0);
        create table if not exists notes (id integer primary key, owner text, created int,
            author text, body text, status text default 'pending', ip_hash text);
        create table if not exists bans (owner text, ip_hash text, primary key (owner, ip_hash));
        create table if not exists nonces (nonce text primary key, created int);
        create index if not exists notes_owner on notes (owner, status);
    """)
    return c


def is_open(c, owner):
    r = c.execute("select 1 from books where owner = ? and enabled = 1 and blocked = 0", (owner,)).fetchone()
    return r is not None


def tidy(c):
    """Old pending notes and old address hashes go after 30 days."""
    old = int(time.time()) - KEEP
    c.execute("delete from notes where status = 'pending' and created < ?", (old,))
    c.execute("update notes set ip_hash = null where created < ?", (old,))
    c.execute("delete from nonces where created < ?", (int(time.time()) - 7200,))


def mark_waiting(c, owner):
    """How many notes wait for the owner, where `runv` and the motd can read it."""
    n = c.execute("select count(*) from notes where owner = ? and status = 'pending'", (owner,)).fetchone()[0]
    path = os.path.join(WAITING, owner)
    if n:
        with open(path + ".new", "w") as f:
            f.write(f"{n}\n")
        os.chmod(path + ".new", 0o644)
        os.replace(path + ".new", path)
    elif os.path.exists(path):
        os.remove(path)
