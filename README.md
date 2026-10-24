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

## Signups

The form at `/join` only drops requests into `/var/lib/runv-join/queue`.
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
sent right after they change.

    sudo runv-backup status
