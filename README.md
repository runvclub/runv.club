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

## Backups

restic to S3. A full backup runs on the 1st and the 16th and the last 6
are kept. The member list, the signup queue and the I2P keys are also
sent right after they change.

    sudo runv-backup status
