"""Guestbook moderation, run as runvgb.

    gbctl.py NAME list|all|on|off          what's waiting, everything, open, close
    gbctl.py NAME ok|rm|ban ID             approve, delete, delete and block the sender
    gbctl.py NAME block|unblock|purge      for runv-user: suspend, unsuspend, purge

Members get here through `sudo runv-priv guestbook`, which passes their own
name. Every change is limited to notes of NAME.
"""

import sys
import time

import gbdb


def die(msg):
    print(f"guestbook: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 3 or not gbdb.NAME.fullmatch(sys.argv[1]):
        die("usage: gbctl.py NAME ACTION [ID]")
    owner, action = sys.argv[1], sys.argv[2]
    nid = None
    if action in ("ok", "rm", "ban"):
        if len(sys.argv) != 4 or not sys.argv[3].isdigit():
            die(f"{action} which note? guestbook {action} NUMBER")
        nid = int(sys.argv[3])
    c = gbdb.connect()
    with c:
        if action in ("list", "all"):
            where = "" if action == "all" else "and status = 'pending'"
            rows = c.execute(f"select id, created, author, body, status from notes where owner = ? {where} "
                             "order by created", (owner,)).fetchall()
            r = c.execute("select enabled, blocked from books where owner = ?", (owner,)).fetchone()
            state = "blocked" if r and r["blocked"] else "on" if r and r["enabled"] else "off"
            print(f"your guestbook is {state}: https://runv.club/guestbook/{owner}")
            if not rows:
                print("nothing waiting" if action == "list" else "no notes")
            for n in rows:
                when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(n["created"]))
                mark = "" if action == "list" else f" [{n['status']}]"
                print(f"\n#{n['id']} from {n['author']}, {when}{mark}")
                print("  " + n["body"].replace("\n", "\n  "))
            return
        if action in ("on", "off", "block", "unblock"):
            c.execute("insert or ignore into books (owner) values (?)", (owner,))
            col, val = {"on": ("enabled", 1), "off": ("enabled", 0),
                        "block": ("blocked", 1), "unblock": ("blocked", 0)}[action]
            c.execute(f"update books set {col} = ? where owner = ?", (val, owner))
            if action in ("on", "off"):
                print(f"your guestbook is {action}: https://runv.club/guestbook/{owner}")
        elif action == "purge":
            for t in ("notes", "bans", "books"):
                c.execute(f"delete from {t} where owner = ?", (owner,))
        elif action in ("ok", "rm", "ban"):
            n = c.execute("select ip_hash from notes where id = ? and owner = ?", (nid, owner)).fetchone()
            if not n:
                die("no such note")
            if action == "ok":
                c.execute("update notes set status = 'approved' where id = ? and owner = ?", (nid, owner))
            else:
                c.execute("delete from notes where id = ? and owner = ?", (nid, owner))
            if action == "ban" and n["ip_hash"]:
                c.execute("insert or ignore into bans values (?, ?)", (owner, n["ip_hash"]))
            print({"ok": "approved", "rm": "deleted", "ban": "deleted, and that sender can't post here again"}[action])
        else:
            die(f"unknown action {action}")
    gbdb.mark_waiting(c, owner)


if __name__ == "__main__":
    main()
