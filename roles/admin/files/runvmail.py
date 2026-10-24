"""Send mail through the Mailgun HTTP API.

Settings live in /etc/runv/mail.env:

    MAILGUN_API=https://api.mailgun.net
    MAILGUN_DOMAIN=example.org
    MAILGUN_KEY=...
    MAIL_FROM=runv.club <noreply@example.org>
    ADMIN_EMAIL=you@example.org

If the file is missing, send() logs and returns False, so nothing else breaks.
"""

import base64
import sys
import urllib.parse
import urllib.request

MAIL_ENV = "/etc/runv/mail.env"


def load_env(path=MAIL_ENV):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"')
    except FileNotFoundError:
        return None
    return env


def admin_address():
    env = load_env()
    return env.get("ADMIN_EMAIL") if env else None


def send(to, subject, body):
    env = load_env()
    needed = ("MAILGUN_API", "MAILGUN_DOMAIN", "MAILGUN_KEY", "MAIL_FROM")
    if not env or not all(env.get(k) for k in needed):
        print(f"mail not configured, skipped: {subject!r} to {to}", file=sys.stderr)
        return False

    url = f"{env['MAILGUN_API'].rstrip('/')}/v3/{env['MAILGUN_DOMAIN']}/messages"
    data = urllib.parse.urlencode({
        "from": env["MAIL_FROM"],
        "to": to,
        "subject": subject,
        "text": body,
    }).encode()
    auth = base64.b64encode(f"api:{env['MAILGUN_KEY']}".encode()).decode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"mail to {to} failed: {e}", file=sys.stderr)
        return False
