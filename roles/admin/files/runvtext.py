"""Text from people we don't control, made safe to show.

clean() drops every control character (ESC, the C1 range, bidi overrides,
zero-width tricks), so nothing written by a member or a visitor can move
the cursor, retitle a terminal or reach a clipboard. visitor() turns an
address into what the limits count: the address, or its /64 on IPv6.
"""

import ipaddress
import unicodedata


def clean(text, lines=None, tabs=True):
    out = []
    for line in str(text).replace("\r", "").split("\n")[:lines]:
        out.append("".join(ch for ch in line
                           if (tabs and ch == "\t") or unicodedata.category(ch)[0] != "C").rstrip())
    return "\n".join(out)


def visitor(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return addr
    return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else str(ip)
