# Loan Application Workflow

Loan application workflow (Django 6.1 admin with the Unfold theme, Python 3.12, PostgreSQL 15+; Docker uses 17).

A demo project: every name, ID number, partner, rate and limit in the demo data is invented, and the CRR
score matrix in `lwf/fixtures/demo_reference.json` uses illustrative weights, not a real lender's model.

## Local development with Docker

1. Create the configuration file and fill in real values:

   ```bash
   cp .env.example .env
   ```

2. Start PostgreSQL, create the tables and load the demo data: reference data (products,
   workflow steps, score matrix, panels, locations), users for every role and 36 synthetic
   applications at every workflow step. No real customer data is involved.

   ```bash
   docker compose up -d db web
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_demo
   ```

   The demo users (`sale1`, `sale2`, `salelead`, `salesupport`, `saledirector`, `headpfs`, `ced1`,
   `ced2`, `cedadmin`, `approver1`, `approver2`, `cra1`, `craadmin`) share the password in
   `DEMO_USER_PASSWORD`; `DEMO_ADMIN_USERNAME` / `DEMO_ADMIN_PASSWORD` is a superuser.
   `seed_demo --reset` replaces all applications with a fresh set.

3. Open the app at http://localhost:8000.

   Tests: `docker compose exec web python manage.py test lwf`.

Moving real data from the old system is a deployment task: see DEPLOY.md (`docker/restore-db.sh`
restores a `pg_dump -Fc` file placed in `./dumps/`).

## Configuration

All settings that differ between environments come from environment variables (see `.env.example`):
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_HTTPS`,
`POSTGRES_*`, `LENDER_*` and the `EMAIL_*` SMTP settings.

The application is the Django admin at `/admin/`. Old addresses (`/`, `/tickets/<id>/`, `/login/`)
redirect there. Uploaded documents are served at `/media/...` only to users who may see the
application they belong to (`lwf/documents.py`). `/healthz` answers `ok` when the app reaches the database.

Production: see [DEPLOY.md](DEPLOY.md). API for other systems and apps: see [docs/API.md](docs/API.md).

## Admin (main UI)

Loan applications are managed in the Django admin at `/admin/` (Unfold theme):

- **Loan applications**: list with filters and search; each application has tabs for the loan,
  applicants, collaterals, conditions, documents, contract data and history. New applications are
  created from the list (Sale team).
- **Applicants**: one page per applicant with salary, business, household, rental and CIC records.
  Averages, net incomes and installments are calculated on save (`lwf/calculations.py`), and the
  application's income, DSR and NST are recalculated (`lwf/services.py`).
- Who sees an application and who may edit which part at which status is defined in `lwf/access.py`
  (`accessible_tickets`, `editable_sections`).
- **Change status** (button on each application): the steps the Action table offers the user's group
  at the current status, with the next handler (round-robin suggestion for CED and CRA), rejection and
  QC codes. `lwf/workflow.py` checks every step on the locked row, fills the role fields, numbers the
  application `DS.<product>.<yy>.<nnnn>` when it reaches CED, writes the history and emails the new
  handler (`lwf/tasks.py`, django.tasks).
- **CRR scoring**: CED enters the bureau inputs; the page shows the score, band and points per criterion.
- **Credit memo (PDF)**: `lwf/memo.py` renders `lwf/memo/credit_memo.html` with xhtml2pdf and the DejaVu
  font (installed in the image) for Vietnamese text.
- The admin home page is a dashboard: my work queue, overdue items, open applications by status and,
  for team admins, the workload of each officer.
- Reference data, workflow actions, the score matrix and credit settings are for superusers.

## License

MIT, see [LICENSE](LICENSE). The project started from a fork of
[django-helpdesk](https://github.com/django-helpdesk/django-helpdesk) (BSD 3-Clause); its notice is kept in LICENSE.
