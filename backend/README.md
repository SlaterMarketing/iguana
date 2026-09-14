# Iguana Comedy backend

Django replacement for the Kintana workspace that iguanacomedy.com was built on. It serves the same HTTP
API paths `@kintana/sdk` calls, so the Astro site runs unchanged: point `PUBLIC_KINTANA_BASE_URL` at this
backend and set `PUBLIC_KINTANA_API_KEY` to one of `PUBLIC_API_KEYS`.

## What it covers

| Kintana feature | Here |
| --- | --- |
| Events, venues, comedians, store listings (`/api/public/v1/...`) | `api/public_views.py`, managed in `/admin/` |
| Contact / perform / hotels forms (`endpoints/<slug>/submit`) | `FormSubmission` rows, emailed to `NOTIFY_EMAILS` |
| Fan sign-in (magic link + 6-digit code) | `api/fan_views.py`, signed session tokens |
| Memberships: plans, status, codes, credit transfers, Stripe subscribe / one-off / billing portal | `api/fan_views.py`, `sales/` |
| Ticket checkout widget (`/_t/k.js` + `/embed/event/<id>` iframe) | `api/embed_views.py`, `templates/embed/` |
| Order page with QR codes, door check-in for staff | `/orders/<token>/`, `/checkin/<token>/` |
| Stripe webhooks | `/api/stripe/webhook` (`payment_intent.succeeded`, `customer.subscription.*`) |
| Pageview / event ingest | `crm.TrackedEvent` |
| CRM: contacts, lists, campaign history, inbox history | imported from the export, read-only history in admin |

Members get `free_tickets_per_order` free tickets (priciest first) on events with `members_eligible`,
then `guest_discount_percent` off the rest. Member pricing only applies when the checkout email matches
the signed-in member.

## Local development

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config_example.py config.py        # set DEBUG=True, SITE_URLS, keys; EMAIL_BACKEND console for local
.venv/bin/python manage.py migrate
.venv/bin/python manage.py import_kintana_export ~/iguana-migration/export
.venv/bin/python manage.py seed_site_defaults
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Then in the repo root `.env` and `.dev.vars`:

```
PUBLIC_SITE_URL=http://127.0.0.1:4321
PUBLIC_KINTANA_API_KEY=<a key from config.PUBLIC_API_KEYS>
PUBLIC_KINTANA_BASE_URL=http://127.0.0.1:8000
```

and `npm run dev`. With `DEBUG=True` and no Stripe keys the checkout shows a "simulate payment" button, and
sign-in emails print to the runserver console.

Tests: `.venv/bin/python manage.py test api`

## Data sources

- `import_kintana_export <folder>`: the CSV export Kintana handed over (contacts, orders, tickets, memberships,
  lists, campaign recipients, inbox, events). Contains customer personal data: keep the CSVs out of git.
- Comedians, venue details, event posters and merch were not in the export and are recovered from Wayback
  Machine captures of the old Framer site and the Kintana-era site.

## Production (iguanacomedy.mx, interim)

Single VPS on the VPS.org `free` account: `38.86.78.36` / `2001:550:2:dd::f9:68`, Ubuntu 24.04, user `iguana`
(credentials in `~/.credentials/vpsorg/iguanacomedy/`). nginx fronts Astro (Node adapter, supervisor
`iguana:iguana-web` on :3000) at `iguanacomedy.mx` and Django (gunicorn, `iguana:iguana-api` on :8001) at
`api.iguanacomedy.mx`. Postgres `iguana`, Postfix send-only with OpenDKIM selector `mail`. DNS zone exists on
VPS.org; the registrar (GoDaddy) currently delegates to Cloudflare.

DNS is on VPS.org (ns1-3.vps.org, zone in the `free` account) and live since 2026-09-14.

```bash
cd ansible
ansible-playbook deploy.yml                    # sync code from this checkout, build, restart, apply mail.yml
ansible-playbook deploy.yml --tags all,certs   # also issue any missing certificates (site, api, mail)
ansible-playbook mail.yml                      # Postfix + OpenDKIM only
ansible-playbook email_check.yml               # end-to-end mail test (see below)
```

### Email

`mail.yml` follows the fleet golden standard: direct delivery, DKIM selector `mail`, MX `mail.iguanacomedy.mx`
with a Let's Encrypt cert for STARTTLS, SPF `-all`, DMARC `p=reject` with `rua` to the local `dmarc` mailbox.
`hello@`, `noreply@`, `no-reply@`, `postmaster@`, `abuse@` and `mailer-daemon` deliver to the local `inbox`
user (`sudo mail -f /var/mail/inbox`); nothing forwards offsite and there is no catch-all.

`email_check.yml` asserts on content: public DNS values and forward-confirmed PTR (v4 + v6), the published
DKIM key against the key on disk, the STARTTLS certificate name, open-relay refusal, inbound delivery to
`hello@`, per-message `status=sent` tracked by Message-ID, and SPF/DKIM `pass` from
`check-auth@verifier.port25.com` (its report is read back from the local inbox). Send a one-off test with
`venv/bin/python manage.py send_test_email you@example.com`.

**IPv4 is on the Spamhaus PBL.** 38.86.78.0/24 returns `127.0.0.11` (ISP-maintained PBL), so Gmail answers
`550-5.7.1 ... not authorized to send email directly`. Postfix therefore sets `smtp_address_preference = ipv6`;
Gmail and most large providers accept over IPv6. Receivers without AAAA MX still see the v4 address, so the
real fix is the network owner (VPS.org / Cogent) removing the PBL listing for the range.
`ASTRO_ADAPTER=node` (`npm run build:node`) builds the Node server; the default build stays Cloudflare Pages.
