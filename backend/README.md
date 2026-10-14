# FastAPI backend

## Install and run

From the `backend` directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$secretBytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($secretBytes)
$rng.Dispose()
$env:ECOSORT_AUTH_SECRET = [Convert]::ToBase64String($secretBytes)
$env:ECOSORT_COOKIE_SECURE = "false"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

The application creates `backend/data/` and `backend/uploads/` when needed and
initializes the SQLite database at `backend/data/ecosort.db` on startup. No
database server or database password is required. Keep the generated auth
secret in the same PowerShell session when restarting the backend if existing
sessions should remain valid. The local
database and uploaded image files are excluded from Git.

## Train the waste classifier

The two-category dataset is expected at `../dataset/DATASET`, with image files
under `TRAIN/<class>/` and `TEST/<class>/`. The training script detects these
folders automatically. Install the Python requirements and run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.ml.train
```

The CPU-friendly pipeline extracts 64x64 HOG shape and RGB color features and
fits a class-balanced logistic classifier. It selects regularization against a
stratified validation split and saves a best-validation model to
`backend/app/ml/models/waste_classifier.joblib`, class names to
`backend/app/ml/models/class_labels.json`, and held-out metrics and a confusion
matrix under `backend/app/ml/models/`. Exact-image duplicates are removed;
images shared by official train/test splits are excluded from test evaluation
to avoid leakage. Source datasets and generated model artifacts remain local.
Byte-identical files carrying different class labels are excluded as ambiguous.

The dataset's `O` examples contain organic fruit/vegetable material and map to
`Wet Waste`; `R` examples contain recyclable/dry items (including plastics and
textiles) and map to `Dry Waste`. The classifier keeps the original labels for
model probabilities and evaluation, then maps them to these two API categories.
The inference endpoint and persisted report classifications return only `Wet
Waste` or `Dry Waste`; startup also converts previously saved `O`/`R` report
predictions to the corresponding category.

Classify an image from the command line with:

```powershell
.\.venv\Scripts\python.exe -m app.ml.predict ..\dataset\DATASET\TEST\O\O_12568.jpg
```

Start the API after training so it loads the model once on startup. The
`POST /api/classify` endpoint accepts an image field named `photo`. The existing
`POST /api/reports` endpoint also predicts from the uploaded photo and stores
the predicted category, confidence, model version, and timestamp alongside the
report in SQLite. Authenticated citizens can use `GET /api/reports` to retrieve
their own saved classifications.
`GET /health` includes `model_available`; without a trained model, classification
and report creation return HTTP 503 with instructions to train it.

On first startup the application creates these SQLAlchemy tables and inserts
the initial report statuses:

- `users`
- `locations`
- `complaint_statuses`
- `waste_reports`
- `image_references`
- `report_status_history`
- `waste_classifications`
- `municipal_complaints`
- `complaint_status_history`

Startup adds the nullable report idempotency columns/index when migrating an
existing SQLite database, creates the complaint tables, and creates an initial
complaint for each existing classified report that does not already have one.
Existing reports and uploaded images are retained.
An older report with no saved category is left untouched during backfill rather
than assigning it a fabricated Wet/Dry category; new submissions require a
successful model classification before creating both the report and complaint.

## Authentication and role access

Citizen registration is available at `/user/register`; citizen and municipal
authority login use separate frontend pages. Passwords are stored as salted
PBKDF2-SHA256 hashes. Authentication uses a signed, 12-hour HTTP-only cookie
with same-site protection and origin validation. Set `ECOSORT_AUTH_SECRET` to a
random value of at least 32 bytes to preserve sessions across API restarts. If
it is omitted, a cryptographically random process-local secret is used and
sessions expire when the backend restarts. Set `ECOSORT_COOKIE_SECURE=true`
when serving the frontend over HTTPS.

Only citizen accounts can be created through public registration. Provision
municipal authority accounts from the backend directory using the local
administrator command; it prompts for a password without echoing it:

```powershell
.\.venv\Scripts\python.exe -m app.provision_authority
```

The authority dashboard, complaint listing/detail, assignment, status changes,
resolution, report listing, and uploaded-image route enforce roles/ownership
in the API. Citizens can view only their own reports, complaints, and related
images; authorities can view all complaints and their images. Complaint filters
include status, department, location, waste category, and inclusive creation
date bounds. Assignment and status changes are recorded in complaint history.
Existing reports with no owner remain available to authorities but are not
exposed to citizen accounts.

The `users` table migration adds nullable `password_hash`; existing user rows
remain intact. Passwordless legacy accounts cannot sign in until an
administrator establishes a password using an approved account-management
process. `complaint_status_history` adds event type and optional acting-user
columns. SQLite startup migrations are idempotent.

## Municipal complaint management

Every new `POST /api/reports` request now requires an `Idempotency-Key` header
(8-128 characters). Reuse the same key when retrying the exact same description,
location, filename, content type, and image bytes. A retry returns the original
report and complaint (HTTP 200 with `X-Idempotent-Replay: true`) instead of
creating additional database rows or an extra image. Reusing a key with
different request data returns HTTP 409. The React form generates and retains a
key until a submission succeeds or its input changes.

The initial department-routing configuration is a JSON environment variable
named `ECOSORT_COMPLAINT_ROUTING_JSON`. Match the submitted address/landmark
exactly after trimming whitespace and ignoring letter case. Coordinate
locations use their `latitude, longitude` display string as the key. Example:

```powershell
$env:ECOSORT_COMPLAINT_ROUTING_JSON = '{"locations":{"park entrance":{"Wet Waste":"Configured wet-waste team","Dry Waste":"Configured dry-waste team"}},"fallback_department":"General municipal sanitation (manual review)"}'
```

The example department values are placeholders: replace them with names
configured by your organization; the application does not assert they are real
municipal departments. An unknown location, or a known location/category with
no configured rule, is routed to `fallback_department`, defaulting to the
generic `General municipal sanitation (manual review)`. Invalid JSON or
unsupported category rules fail startup explicitly.

Complaint API:

- `GET /api/complaints` lists complaints visible to the current account. Optional
  filters: `status`, `department` and `location` (substring matches), `category`,
  `created_after`, and `created_before`.
- `GET /api/complaints/{complaint_id}` returns the complaint and complete status
  history.
- `PUT /api/complaints/{complaint_id}/assignment` changes the assigned department
  and records the assignment in complaint history.
- `PUT /api/complaints/{complaint_id}/status` accepts JSON with `status`
  (`New`, `Assigned`, `In Progress`, `Resolved`, or `Closed`) and optional
  `staff_note` for transitions other than resolution. Resolve a complaint with
  `PUT /api/complaints/{complaint_id}/resolve`, multipart fields
  `after_cleaning_photo` (required) and `staff_note` (optional). The photo must
  be a JPEG, PNG, or WebP image of 10 MB or smaller; its bytes are signature
  checked, saved under a unique name in `backend/uploads/`, and its relative
  path and UTC upload timestamp are stored on the linked complaint. The status
  endpoint rejects direct transitions to Resolved unless the photo-required
  resolve endpoint is used. Allowed transitions are New → Assigned → In
  Progress → Resolved → Closed. Invalid transitions return HTTP 409; unknown
  IDs return HTTP 404. Every transition stores previous/new status, timestamp,
  and note.

The complaint detail/list response includes `before_cleaning_photo_path` from
the original report image and the optional `after_cleaning_photo_path` plus
`after_cleaning_photo_uploaded_at`. Both image paths are served by the
authenticated `/uploads/{filename}` route. The dashboard displays separately
labeled Before Cleaning and After Cleaning photos on complaint details and
shows both on resolved complaint cards.

**Deployment note:** Authentication does not replace HTTPS, operational
account-provisioning controls, rate limiting, or a production secret-management
system. Use HTTPS and a securely managed `ECOSORT_AUTH_SECRET` before exposing
the service to an untrusted network.

The complaint rows retain report ID, waste category, description, location,
assigned department, status, and timestamps. No real department contacts or
municipal integrations are assumed or contacted.

## Test the API

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

Install test dependencies and run the role/complaint integration test from
`backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Create a report with either `location` or both `latitude` and `longitude`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/reports `
  -H "Idempotency-Key: replace-with-a-unique-request-key" `
  -F "description=Overflowing garbage near the park" `
  -F "location=Park entrance" `
  -F "photo=@C:\path\to\photo.jpg;type=image/jpeg"
```

List reports:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/reports
Invoke-RestMethod http://127.0.0.1:8000/api/complaints
```

Report metadata and relative image paths persist in SQLite. New uploaded image
files are stored under `backend/uploads/` and served at `/uploads/<filename>`
to authenticated owners and authorities; they remain available after backend
restarts. Existing image BLOB data is left untouched. No municipal department
is notified by this API.
