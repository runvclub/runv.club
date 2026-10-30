"""Form tokens for the signup form and the guestbooks.

A token is a timestamp and a nonce signed with the app's secret. It tells
a bot that posts at once, or a form left open for hours, from a person,
with no cookies. The nonce lets an app refuse a token the second time.
"""

import hashlib
import hmac
import secrets
import time


def make(key, extra=""):
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    sig = hmac.new(key, f"{ts}.{nonce}.{extra}".encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{nonce}.{sig}"


def check(key, token, extra=""):
    """(seconds since it was made, nonce), or (None, None) if it's not ours."""
    try:
        ts, nonce, sig = token.split(".")
        made = int(ts)
    except ValueError:
        return None, None
    good = hmac.new(key, f"{ts}.{nonce}.{extra}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return None, None
    return time.time() - made, nonce
