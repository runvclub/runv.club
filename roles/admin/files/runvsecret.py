"""Leave a secret in a member's ~/.config/runv.

The writing happens as the member, so whatever they put in the way (a
symlink, say) can only point at their own files.
"""

import pwd
import subprocess

SCRIPT = 'umask 077; d="$HOME/.config/runv"; mkdir -p "$d"; cat > "$d/$1.new" && mv -f "$d/$1.new" "$d/$1"'


def save(name, fname, text):
    home = pwd.getpwnam(name).pw_dir
    subprocess.run(["runuser", "-u", name, "--", "env", "HOME=" + home,
                    "sh", "-c", SCRIPT, "sh", fname],
                   input=text + "\n", text=True, check=True, capture_output=True)
    return "~/.config/runv/" + fname
