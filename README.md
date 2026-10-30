# runv.club

Server config for the runv.club pubnix. The box is set up from this repo
with Ansible, run on the server itself:

    cp host_vars/srv1.yml.example host_vars/srv1.yml   # and edit it
    sudo ansible-playbook site.yml

Two secrets live outside the repo and must exist before the first run:

- `/etc/runv/s3.env`, S3 credentials for the backups
- `/etc/runv/restic.pass`, the restic repository password

Mail (welcome messages, the weekly report and failure alerts) stays off
until `/etc/runv/mail.env` exists. There is an example next to it.

## Members

    sudo runv-user add NAME --email ADDR --key-file key.pub
    sudo runv-user suspend NAME --reason '...'
    sudo runv-user unsuspend NAME
    sudo runv-user delete NAME
    sudo runv-user list

Each member gets 1G of RAM, 200 processes, one CPU and 2G of disk.
Deleted homes sit in `/var/lib/runv/deleted` for 14 days before they
are gone for good.

## Web, Gemini and Gopher

nginx serves `https://runv.club/~NAME/` from `~/public_html`, molly-brown
serves `gemini://runv.club/~NAME/` and gophernicus serves
`gopher://runv.club/1/~NAME`. Links to files a member doesn't own are not
followed, and a suspended member's pages go dark on all three.

molly-brown only reads under `/var/gemini`, so each active member's
`public_gemini` is bind mounted read-only into `/var/gemini/users`.
`runv-user` keeps those mounts in sync, don't touch them by hand.

The Gemini certificate is self-signed and made once. Clients pin it, so
don't regenerate it.

## I2P

Every member gets an eepsite with an address of their own, served from
`~/public_i2p`. `runv-user` writes one i2pd tunnel per member in
`/etc/i2pd/tunnels.d` and leaves the address in `~/.i2p-address`. The key
in `/var/lib/i2pd/runv` is the address, so it's backed up as soon as it
exists and only goes away with the account. i2pd runs with no console and
no proxies.

## On the box

Members get `help` (topics live in `/usr/local/share/runv/help`), a
login banner that's different every time (`motd`), and the usual tools:
editors, git, python, gcc, tmux, irssi, weechat, senpai.

`runv` is the member dashboard, in the terminal: keys, tokens, pages,
blog, pastes, access logs, stats and the state of every service. Every
screen also prints as plain text (`runv keys`, `runv analytics`). The few
things that need root go through `runv-priv`, which members can run with
sudo. It only ever acts on whoever called it and takes no free arguments.

- `blog`: markdown in `~/blog` becomes a blog with an Atom feed on the
  web, Gemini and Gopher. A timer rebuilds it as the member, every 3
  minutes, when something changed. `runv-planet` collects everyone's
  posts at `/planet` and on the home page, and writes `/tilde.json`.
- `pb`: text from stdin to `~/public_html/p`, with an expiry.
- `tw`: twtxt in `~/public_html/twtxt.txt`, with a timeline of all members.
- `board`: a forum in the terminal. Posts are written by `runv-priv`
  into `/var/lib/runv-board`, so nobody can touch other people's posts.
- finger on port 79 shows `~/.plan` and who is on.

## IRC bouncer

soju at `irc.runv.club:6697`, gamja at `https://chat.runv.club`. Every
member gets a bouncer account on tilde.chat in #runv, with the password
in `~/.config/runv/irc-token`. `chat` opens senpai on it. Members can add
up to 3 networks. Accounts idle for 30 days get disconnected until they
log in again, and suspending a member locks theirs.

## Tunnels and apps

Whatever listens on `/run/runv-apps/NAME/app.sock` is served at
`https://NAME.tun.runv.club`: a tunnel from the member's machine
(`ssh -R /run/runv-apps/NAME/app.sock:localhost:8000 NAME@runv.club -N`)
or an app under `systemd --user` (lingering is on for members). Members
may only forward to sockets: no `-L`, `-D` or TCP `-R`, so the box can't
be used as a proxy. `runv-tun-cert` keeps one certificate with every
active member's name on it.

## Stats

nginx logs `~member` requests to their own file. `runv-stats` runs every
hour and gives each member an access log with addresses cut down, kept
14 days, and, if they turned analytics on, counts of unique visitors
(hashed with a salt that's thrown away every day), pages and referrers,
kept a year. No address is stored.

## ntfy and feeds

`ntfy.runv.club` is closed by default. `runv token ntfy` gives a member
a user whose only topics start with their name. `feeds.runv.club` is
miniflux on postgres, with login through Forgejo only.

## Mail in

The box only forwards. `admin@`, `postmaster@`, `abuse@` and `dmarc@`
go to `mail_forward_to` in `host_vars`, with SRS so SPF still passes on
the other end. Anything else is refused at RCPT and nothing is relayed.
There are no mailboxes here.

## git.runv.club and links.runv.club

Forgejo, closed to the outside: no signups, nothing visible without
logging in. Git over SSH is on port 2222 with the same key as the shell,
and each member has 1GiB. The binary comes from Codeberg and is checked
against its GPG signature, so updating means changing `forgejo_version`
and the checksum in the role defaults.

linkding runs from a venv and has no login form of its own. People log
in through Forgejo (OIDC), so only members get in.

`runv-user` creates the Forgejo account along with the shell account and
leaves the first password in `~/.forgejo-password`. Suspending a member
locks them out of both, and the purge 14 days after a delete removes the
accounts and the repos.

## Signups

The form at `/join`, and `ssh join@runv.club` (a user with no password
whose only command asks the same questions and posts to the same form),
only drop requests into `/var/lib/runv-join/queue`.
Nothing gets created until someone runs:

    sudo runv-queue list
    sudo runv-queue approve ID
    sudo runv-queue reject ID --reason '...'

At most 5 approvals a week and 100 people in line. Every 60 days in line
people are asked if they still want in, and they're dropped if they don't
answer within a week. Set `signup_state: open` in `host_vars` to open the
form.

## Backups

restic to S3. A full backup runs on the 1st and the 16th and the last 6
are kept. The member list, the signup queue and the I2P keys are also
sent right after they change. The Forgejo and linkding databases are
copied with SQLite's backup API into `/var/backups/runv-db` before each
full run, along with the soju and ntfy databases and a `pg_dump` of
miniflux, and those copies are what gets backed up.

    sudo runv-backup status
