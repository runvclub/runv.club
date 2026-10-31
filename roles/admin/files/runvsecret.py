"""Leave a secret in a member's ~/.config/runv.

The writing happens as the member, so whatever they put in the way (a
symlink, say) can only point at their own files.
"""

import pwd
import subprocess

SCRIPT = 'umask 077; d="$HOME/.config/runv"; mkdir -p "$d"; cat > "$d/$1.new" && mv -f "$d/$1.new" "$d/$1"'
HOME_SCRIPT = 'umask 077; cat > "$HOME/$1.new" && chmod "$2" "$HOME/$1.new" && mv -f "$HOME/$1.new" "$HOME/$1"'


def _as_member(name, script, args, text):
    home = pwd.getpwnam(name).pw_dir
    subprocess.run(["runuser", "-u", name, "--", "env", "HOME=" + home,
                    "sh", "-c", script, "sh", *args],
                   input=text + "\n", text=True, check=True, capture_output=True)


def save(name, fname, text):
    _as_member(name, SCRIPT, [fname], text)
    return "~/.config/runv/" + fname


def save_home(name, fname, text, mode="600"):
    """Same, but straight in the home, for the files the welcome mail names."""
    _as_member(name, HOME_SCRIPT, [fname, mode], text)
    return "~/" + fname
