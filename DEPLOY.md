# Deployment and go-live

How to put the loan workflow in production and move the data of the old system into it.

## 1. Server prerequisites

- Docker Engine with the Compose plugin, or Python 3.12 if you run without containers.
- **PostgreSQL 15 or later.** Django 6.1 refuses older versions; the old server runs PostgreSQL 12.
  The `docker-compose.prod.yml` database runs PostgreSQL 17.
- An HTTPS reverse proxy (nginx, a load balancer) in front of the app, forwarding
  `X-Forwarded-Proto` and the `Host` header.
- An SMTP relay for notification emails.

## 2. Configuration

Copy `.env.example` to `.env` on the server and set at least:

| Variable | Production value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A new random value. Never reuse the key from the old code (it is in the git history). |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | The site host name, e.g. `loans.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://loans.example.com` |
| `DJANGO_HTTPS` | `true` (HTTPS redirect, secure cookies, HSTS) |
| `POSTGRES_*` | Database name, user, a new strong password, host, port |
| `LENDER_NAME`, `LENDER_ADDRESS`, `LENDER_REGISTRATION` | Printed on loan contracts |
| `EMAIL_*`, `DJANGO_EMAIL_BACKEND` | SMTP relay |
| `WEB_CONCURRENCY` | gunicorn workers, about 2 x CPU cores + 1 |

`.env` holds secrets: keep it out of git and readable only by the deploy user.

## 3. Build and start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
curl http://127.0.0.1:8000/healthz      # -> ok
```

The image collects static files at build time and serves them with WhiteNoise; uploaded documents
live in the `media` volume and are served by the app after an access check, so the proxy only needs
to forward all paths to port 8000.

## 4. Moving the data from the old system

Do this on a staging server first, then repeat on production during a short freeze.

1. **Freeze** the old system (read-only or announced stop) and take a dump:
   `pg_dump -Fc -U postgres lws157 > lws.dump`.
2. **Restore** into the new PostgreSQL. With the compose stack: copy the dump to `./dumps/lws0910.sql`
   and run `docker compose exec db sh /docker/restore-db.sh` (it skips the `adminpack` extension,
   which PostgreSQL 17 no longer has).
3. **Migrate:** `python manage.py migrate`. Keep the output: migration `0046` converts the text
   dates and prints every value it had to interpret (month/day order, year only) or could not read.
   Check those records with the business.
4. **Copy uploaded files** from the old server's `media/` folder into the `media` volume
   (`docker compose -f docker-compose.prod.yml cp ./media/. web:/app/media/`).
5. **Check the figures:** open a sample of applications and compare income, DSR and NST with the
   old screens. Scores of re-scored applications change (see "Behaviour changes" below).
6. **Accounts and roles:** users and groups come with the dump. Make sure each user is
   `is_staff` (needed to log in to the admin) and in the right group:

   | Group | Role |
   | --- | --- |
   | SaleTeam, SaleManager, SaleSupport, SaleDirector, HeadPFS, SaleAdmin | Sales and its approvals |
   | CEDOfficer, CEDAdmin | Credit evaluation; panel projects and car dealers |
   | Approver, ConcurApprover, ExceptionApprover, JDAApprover | Credit approvals |
   | CRAOfficer, CRAAdmin | Contract preparation and disbursement |
   | PFSAdmin | Products and pricing schemes |

   Superusers manage the workflow actions, score matrix, credit settings, users and groups.
7. Set **Credit settings** (living costs, salary segment thresholds, CRR bands) in the admin.

## 5. Go-live checklist

- [ ] PostgreSQL 15+ in place, backups scheduled (daily `pg_dump`, plus the `media` volume).
- [ ] `.env` filled; `python manage.py check --deploy` shows no warnings except HSTS preload.
- [ ] HTTPS works and `http://` redirects to `https://`.
- [ ] Data restored, migrated, figures spot-checked, uploaded files copied.
- [ ] Each role tested on staging with real (anonymised) applications: create, edit, change status,
      score, print memo and contract.
- [ ] Notification email received by a test user.
- [ ] Old system kept read-only for 1-2 weeks of parallel run, then archived.

## 6. Rollback

The old system's database is not changed by the migration (the new system uses its own
PostgreSQL). To roll back, point users to the old system again; work entered in the new system
during the parallel run must then be re-entered there.

## Behaviour changes users will notice

- The application is the admin at `/admin/`; old links redirect there.
- CRR scoring no longer carries a criterion's points into the next one, and a value of 0 is scored:
  most re-scored applications get a lower score (20 of 28 bands changed on the 2020 data).
- The lowest monthly installment is the last month's payment (principal part plus its interest),
  for the loan and for secured CIC loans.
- Salary, business, household, rental and CIC figures are calculated by the server when saved.
- Rejection reasons and QC codes are stored with the status change.
- Applications cannot be deleted; they are cancelled through the workflow.
