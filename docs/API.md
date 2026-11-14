# Loan Workflow API (v1)

Base address: `https://<server>/api/v1/`. Interactive documentation (OpenAPI / Swagger) for
signed-in staff: `/api/v1/docs`; the schema itself: `/api/v1/openapi.json`.

## Who can call it

| Caller | How | Rights |
|---|---|---|
| Another system (core banking, CIC connector, eKYC, data warehouse) | Header `X-API-Key: <key>` | The scopes given to its key in the admin (**API and integrations → API clients**); optional IP allow-list |
| A staff app (mobile app for Sale) | `POST /auth/token` with username and password, then `Authorization: Bearer <token>` (12 hours) | The person's own rights: only the applications they may see |

Keys are shown once when made and only their hash is stored. Making a new key stops the old one.
Calls are limited (300 a minute per key or token, 30 a minute without one, 10 sign-ins a minute)
and every call is logged (**API calls** in the admin).

### Scopes

| Scope | Allows |
|---|---|
| `applications:read` | List and read applications and their workflow history |
| `applications:personal` | Full ID numbers, dates of birth and addresses (otherwise ID numbers are masked: `079******123`) |
| `reference:read` | Products, status codes |
| `core_banking` | Applications waiting for disbursement; reporting disbursements |
| `cic` | Sending credit bureau reports |
| `ekyc` | Sending eKYC results (staff apps may do this too) |

## Endpoints

| Method and path | Scope | Purpose |
|---|---|---|
| `GET /applications?status=&updated_since=&limit=&offset=` | `applications:read` | Applications, most recently changed first |
| `GET /applications/{number}` | `applications:read` | One application: applicants, collaterals, credit assessment, decision, contract terms, what is missing, policy breaches |
| `GET /applications/{number}/history` | `applications:read` | Workflow steps |
| `POST /customers/loans` with `{"id_number": "..."}` | `applications:read` | Every application of one customer (borrower or co-borrower): status, approved amount, contract terms, disbursements. The ID number goes in the body so it stays out of access logs |
| `GET /reference/products`, `GET /reference/statuses` | `reference:read` | Reference data |
| `POST /auth/token`, `POST /auth/logout`, `GET /auth/me` | – | Staff app sign-in |
| `GET /core-banking/ready` | `core_banking` | Applications at "CRA Disbursement" with the contract terms |
| `POST /core-banking/disbursements` | `core_banking` | Report a disbursement (see below) |
| `POST /cic/reports` | `cic` | Send a credit bureau report for an ID number |
| `POST /ekyc/checks` | `ekyc` | Send a chip ID card and face match result |

### Reporting a disbursement

```http
POST /api/v1/core-banking/disbursements
X-API-Key: lwf_key_...
Content-Type: application/json

{"application": "DS.SS.26.0004", "reference": "CB-20261105-0001", "amount": 1500000000,
 "disbursed_at": "2026-11-05T10:15:00+07:00", "account_number": "1234567890"}
```

`201` recorded; `200` with `"created": false` when the same `reference` was sent before (safe to retry);
`409` when the application is not waiting for disbursement; `422` when the total would exceed the
contract's disbursement amount. The disbursement is written to the application's history and the CRA
officer is notified; CRA confirms the workflow step.

### Sending a CIC report

```json
{"id_number": "079190000123", "report_date": "2026-11-05", "credit_group": "G1",
 "secured_loans": [{"original_amount": 500000000, "interest_rate": 10.5, "tenor_months": 120,
                    "outstanding": 300000000}],
 "unsecured_loans": [{"monthly_payments": [3000000, 3000000, 3000000]}],
 "overdrafts": [{"interest_rate": 12, "outstanding": 50000000}],
 "credit_cards": [{"balances": [12000000, 9000000, 15000000, 8000000, 10000000, 11000000]}]}
```

The report replaces the CIC records of every applicant with that ID number on applications in
progress, and their repayment capacity (DSR, NST) is recalculated. In the demo, the applicant page has
a **Look up CIC (demo)** button that produces a made-up report in the same shape.

### Sending an eKYC result

```json
{"application": "AP1126sale11145", "id_number": "079190000123", "full_name": "PHẠM NGỌC OANH",
 "date_of_birth": "1989-09-14", "issue_date": "2021-07-01", "issue_place": "Cục Cảnh sát QLHC về TTXH",
 "permanent_address": "...", "chip_verified": true, "face_match_score": 93.5}
```

Answer: `{"passed": true, "differences": [], "applicant": "Phạm Ngọc Oanh"}`. It passes when the chip
is verified, the face match score is at least 80 (demo assumption) and the name and date of birth
match the application. Empty ID card details on the application are filled from the chip.

## Demo page

`/api-demo/` (staff only, sidebar **API and integrations → API demo: customer loans**) plays a partner
system (API key) or the staff mobile app (sign-in) calling `POST /customers/loans`, and shows each
request and JSON response. It calls the real API, so scopes, masking, throttling and the call log all
apply. With `LWF_API_DEMO_SAMPLES=true` (default: same as `DJANGO_DEBUG`) it suggests demo customers to
click on; keep it off where the data is real.

## AI document reading

On an application's **Documents** tab, **Read with AI** sends an ID card, payslip or land
certificate (PDF or image) to Claude (`claude-opus-5-5`, Anthropic API) and shows what was read next to
what the application holds; **Fill the empty fields** applies it (differing values are never
overwritten). Off unless `LWF_AI_DOCUMENT_READING=true` and `ANTHROPIC_API_KEY` are set: the document
leaves the bank's systems, so turn it on only with the bank's approval.

## Example

```bash
curl -H "X-API-Key: $LWF_KEY" "https://<server>/api/v1/applications?status=34&limit=20"
```
