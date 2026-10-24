"""Checks shared by runv-user and the signup form.

Every function raises ValueError with a message that can be shown to the
person who sent the data.
"""

import re
import subprocess
import tempfile

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
KEY_TYPES = {
    "ssh-ed25519", "sk-ssh-ed25519@openssh.com",
    "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
    "sk-ecdsa-sha2-nistp256@openssh.com", "ssh-rsa",
}
RESERVED = {
    "root", "admin", "administrator", "sysadmin", "sudo", "staff", "support",
    "help", "info", "abuse", "postmaster", "hostmaster", "webmaster", "www",
    "mail", "ftp", "ssh", "git", "irc", "news", "noreply", "nobody", "operator",
    "security", "system", "daemon", "members", "runv", "runvclub", "join",
    "signup", "register", "public", "test", "guest", "anonymous", "user",
    "farewell", "status", "links", "about",
}


def username(name):
    if not NAME_RE.match(name):
        raise ValueError("Usernames are 2 to 16 characters: lowercase letters, digits "
                         "and _, starting with a letter.")
    if name in RESERVED or name.startswith("runv"):
        raise ValueError(f"{name} is reserved.")
    return name


def email(addr):
    addr = addr.strip()
    if len(addr) > 254 or not EMAIL_RE.match(addr):
        raise ValueError("That email address doesn't look right.")
    return addr


def ssh_key(line):
    """Return (key, fingerprint) for a single public key line."""
    line = line.strip()
    if "\n" in line or "\r" in line:
        raise ValueError("Paste one key only, on a single line.")
    parts = line.split()
    if len(parts) < 2 or parts[0] not in KEY_TYPES:
        raise ValueError("That doesn't look like an SSH public key. It should start "
                         "with ssh-ed25519 (options before the key are not allowed).")
    with tempfile.NamedTemporaryFile("w", suffix=".pub") as f:
        f.write(line + "\n")
        f.flush()
        out = subprocess.run(["ssh-keygen", "-l", "-f", f.name],
                             text=True, capture_output=True)
    if out.returncode != 0:
        raise ValueError("ssh-keygen couldn't read that key.")
    bits, fingerprint = out.stdout.split()[:2]
    if parts[0] == "ssh-rsa" and int(bits) < 3072:
        raise ValueError("RSA keys need at least 3072 bits. An ed25519 key is better.")
    return line, fingerprint
