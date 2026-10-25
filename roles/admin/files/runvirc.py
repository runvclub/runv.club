"""The irc bouncer side of an account. soju is driven through sojuctl."""

import os
import secrets
import subprocess

SOJUCTL = ["sojuctl", "-config", "/etc/soju/config"]
# every new account starts on tilde.chat, in #runv
NETWORK, ADDR, CHANNEL = "tilde", "irc.tilde.chat", "#runv"


def available():
    return os.path.exists("/usr/bin/sojuctl") and os.path.exists("/run/soju/admin")


def ctl(*args):
    out = subprocess.run(SOJUCTL + list(args), capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError("soju: " + (out.stderr or out.stdout).strip()[:200])
    return out.stdout


def exists(name):
    return any(l.split()[:1] in ([name], [name + ":"]) for l in ctl("user", "status").splitlines())


def create(name):
    """New bouncer account with the default network. Returns its password."""
    password = secrets.token_urlsafe(24)
    ctl("user", "create", "-username", name, "-password", password,
        "-nick", name, "-realname", f"{name}@runv.club")
    ctl("user", "run", name, "network", "create", "-addr", ADDR, "-name", NETWORK, "-nick", name)
    ctl("user", "run", name, "channel", "create", f"{CHANNEL}/{NETWORK}")
    return password


def new_password(name):
    password = secrets.token_urlsafe(24)
    ctl("user", "update", name, "-password", password, "-enabled", "true")
    return password


def lock(name):
    """Disconnect everything and refuse logins until new_password."""
    if exists(name):
        ctl("user", "update", name, "-enabled", "false", "-disable-password")


def delete(name):
    if not exists(name):
        return
    confirm = ctl("user", "delete", name).split()[-1].strip('"')
    ctl("user", "delete", name, confirm)
