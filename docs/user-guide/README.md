# User guide (Vietnamese and English)

`guide.html` (Vietnamese) and `guide_en.html` (English) are the guide's text. The screenshots (`img/`)
and the PDFs are not in the repository: build them from the demo data (`python manage.py seed_demo`)
with the steps below.

To rebuild after a UI change (needs Microsoft Edge and `pip install playwright pymupdf` on the host):

```bash
docker compose exec -T web python manage.py seed_demo --reset
docker compose exec -T web python manage.py shell < docs/user-guide/tools/mksess.py | grep SESSIONS= | sed 's/SESSIONS=//' > docs/user-guide/tools/sessions.json
python docs/user-guide/tools/shoot.py docs/user-guide/tools/png docs/user-guide/tools/screens.json
python docs/user-guide/tools/topdf.py docs/user-guide/guide.html docs/user-guide/HuongDanSuDung_LoanWorkflow.pdf
python docs/user-guide/tools/topdf.py docs/user-guide/guide_en.html docs/user-guide/UserGuide_LoanWorkflow_EN.pdf "Loan Workflow · User Guide"
```

`screens.json` refers to applications by id; after a reseed check that the ids still point at
applications in the right status. Convert the PNGs in `tools/png/` to the JPEGs in `img/`
(half size, quality 82) before building the PDF. `sessions.json` holds login sessions: never commit it.
