# Deploy history

Why `ansible/deploy.yml` is shaped the way it is. Each change here fixed live traffic breaking during a deploy.

🚨 **A migration that adds a NOT NULL column 500s live checkouts until the workers reload, and the deploy used
to leave ten minutes between the two.** `migrate` ran at line 163 and the gunicorn HUP sat down beside the site
restart, on the far side of `npm install` and the Astro build. In between, the database has the new schema and
the workers are still running the old code, which inserts without the column. Measured 2026-09-21 on
`OrderItem.is_addon`: two `POST /api/checkout/<id>/start` from a Facebook in-app browser on Android, both 500,
both a real ad click that did not become a reservation. **Nothing is written on that path, so the DB cannot show
you the loss and neither can an order count**: the only trace is `/var/log/iguana/api.out.log`, and the
traceback in `api.err.log` carries no timestamp of its own, only the nearest gunicorn line.
Two fixes, both in place: the API now reloads **directly after the migration**, before the long site build; and
`0006_orderitem_is_addon_db_default` restores the database default Django drops, so an insert from an old worker
gets `false` rather than an `IntegrityError`. **Give any new NOT NULL column a DB default in a follow-up
migration** (Postgres only; SQLite cannot ALTER it and does not need to).

🚨 **The deploy used to break live traffic twice over, and both were invisible to every log check.** Gunicorn
was hard-restarted, so the checkout iframe served **502 inside the ad landing page** for the ~2s window; it is
now a graceful `supervisorctl signal HUP`, which keeps the listening socket, and only a dependency change
falls back to a restart. Worse, the site was rebuilt **in place**: the Node adapter resolves Astro route
modules lazily, so every route the running process had not yet imported threw `ERR_MODULE_NOT_FOUND` until the
restart (`/en/open-mic/` 500'd for a minute on 2026-09-21 with ads pointed at it). It now builds into
`dist.next`, asserts that build produced a `server/entry.mjs`, and renames; `dist.old` is the rollback. The
play then polls the site and the checkout before finishing.

A third case survived both of those, because it happens to the BROWSER rather than the server. A build hashes
its filenames from their content, so a name that has gone is not a name that changed: it is last build's file,
still exactly what its name says it holds. Somebody with a page already open when a deploy lands asks for it
and gets a 404, the island never hydrates, and the symptom is a button that does nothing. Nothing reports it;
the only trace is an `_astro` 404 in nginx, which reads as crawler noise (13 on 2026-09-24, 11 of them
Facebook's crawler). `location ^~ /_astro/` now `try_files $uri @last_build` into `dist.old`, the previous
build the deploy already keeps for rollback. Verify by putting a file in `dist.old/client/_astro/` only: it
serves 200, and a nonsense hash still 404s.
