# Technical Decisions & Architecture Log: DealerOS

This document records the foundational architectural, technological, and design decisions made for the DealerOS full-stack application.

---

## 1. Monorepo Repository Structure

### Context
DealerOS requires a cohesive full-stack codebase composed of a Django backend, a React frontend, raw inventory data files, and unified project documentation.

### Decision
A clean, two-tier root workspace was selected:
```
DealerOS/
├── backend/
├── frontend/
├── data/
├── README.md
├── DECISIONS.md
└── .gitignore
```
- `backend/` contains all Python services, Django configuration, and virtual environment isolations.
- `frontend/` houses the React + Vite single-page application and its dependency tree.
- `data/` serves as the centralized repository for raw input data (`locations.csv`, `system_a.csv`, `system_b.csv`).
- Root configuration (`.gitignore`, `README.md`, `DECISIONS.md`) governs repository-wide conventions.

### Consequences
- Prevents cross-contamination between Python virtual environments and Node dependency graphs.
- Simplifies CI/CD pipelines, containerization, and local development orchestration.

---

## 2. Backend Architecture: Django 5 + Django REST Framework

### Context
The backend requires a robust web framework capable of handling data models, validations, REST APIs, and automated test suites.

### Decision
- **Django 5.2+** was chosen as the web application foundation for its mature ORM, built-in migration engine, and security features.
- **Django REST Framework (DRF 3.18+)** was selected for crafting standardized RESTful APIs, serialization, and status code handling.
- The Django project configuration package is named `backend` (configured inside `backend/backend/`), keeping `manage.py` at the root of `backend/`.
- Domain features are encapsulated in a dedicated Django app named `reconcile`.

### Consequences
- Provides modular separation between project-wide configuration (`backend/backend/settings.py`) and business capabilities (`backend/reconcile/`).
- Standardizes future API development with DRF serializers, viewsets, and JSON responses.

---

## 3. Database Selection: SQLite

### Context
DealerOS is evaluated as a full-stack assessment project requiring portability, reproducible setups, and zero external infrastructure hurdles.

### Decision
- **SQLite 3** (`django.db.backends.sqlite3`) is configured in `backend/backend/settings.py` via `BASE_DIR / 'db.sqlite3'`.
- SQLite is file-backed, self-contained within Python standard library, and requires no external database server daemon.

### Consequences
- Evaluators can clone, run `python manage.py migrate`, and test immediately without provisioning PostgreSQL/MySQL instances.
- Database file `db.sqlite3` is explicitly excluded from version control via `.gitignore`.

---

## 4. Cross-Origin Resource Sharing (CORS) Strategy

### Context
During development, the React frontend runs on `http://localhost:5173` (Vite's default port) while the Django backend operates on `http://127.0.0.1:8000`. Cross-origin browser requests must be safely allowed.

### Decision
- Installed and configured `django-cors-headers`.
- Positioned `corsheaders.middleware.CorsMiddleware` as the first middleware in `MIDDLEWARE` to guarantee proper CORS headers on all incoming requests before downstream handlers.
- Explicitly whitelisted frontend development origins:
  ```python
  CORS_ALLOWED_ORIGINS = [
      'http://localhost:5173',
      'http://127.0.0.1:5173',
  ]
  CORS_ALLOW_CREDENTIALS = True
  ```

### Consequences
- Eliminates CORS preflight failures during local development while adhering to secure origin whitelisting rather than unrestricted wildcards.

---

## 5. Testing Framework: Pytest and Pytest-Django

### Context
Testing is a core requirement of the assessment. Django provides standard `unittest`-based runners, but modern Python teams prioritize pytest for readability and fixture flexibility.

### Decision
- Installed `pytest` (9.2+) and `pytest-django` (4.14+).
- Added `backend/pytest.ini` with:
  ```ini
  [pytest]
  DJANGO_SETTINGS_MODULE = backend.settings
  python_files = tests.py test_*.py *_tests.py
  ```
- Created an initial smoke/sanity test in `backend/reconcile/tests.py` verifying settings and installed apps.

### Consequences
- Developers can run either `pytest` or `python manage.py test`.
- Pytest features such as parametrized tests, database fixtures (`@pytest.mark.django_db`), and assertions are immediately available.

---

## 6. Frontend Tooling: React + Vite with JavaScript and CSS

### Context
The assessment requires a modern, responsive frontend using React, Vite, JavaScript, and CSS.

### Decision
- Scaffolded frontend via Vite using the standard React template (`template: react`).
- Kept the stack strictly to JavaScript (ES modules) and clean CSS per requirements.
- Configured clean page title in `index.html` ("DealerOS") and established a baseline layout and status card in `App.jsx`.

### Consequences
- Fast cold starts and sub-millisecond Hot Module Replacement (HMR).
- Lightweight footprint with zero unnecessary UI library overhead before requirements dictate.

---

## 7. Data Layer Integrity & Non-Destructive Principles

### Context
Reconciliation requires comparing records across `system_a.csv`, `system_b.csv`, and `locations.csv`.

### Decision
- Raw CSV files are housed in a top-level `data/` directory.
- A strict rule of **data immutability** is established: original CSV files are treated as read-only canonical sources of truth.
- CSV parsing, sanitization, and database ingestion will operate non-destructively.

---

## 8. Git and Environment Isolation

### Context
The project must remain clean, reproducible, and free of binary cache, compiled bytecode, node dependencies, or local virtual environment files.

### Decision
- Defined comprehensive root `.gitignore` covering:
  - Python: `venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.
  - Django: `db.sqlite3`, `*.log`.
  - Node: `node_modules/`, `dist/`.
  - OS / Editors: `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`.

---

## 9. Reconciliation Domain Data Modeling (Phase 2)

### Context
Phase 2 requires modeling `Location`, `SystemARecord`, and `SystemBEntry` to support reconciliation while preserving dirty CSV rows and keeping raw sources intact.

### Decisions
1. **Decoupled System B & System A Architecture (No ForeignKey between SystemBEntry and SystemARecord):**
   - System B and System A represent independent external ledgers.
   - A relational ForeignKey constraint would reject orphan System B entries, prevent independent ingestion orders, and make discovering discrepancies impossible at the database level.
   - `record_ref` is therefore modeled as a nullable `CharField` (not unique, as multiple System B entries may reference or split a single System A record).
2. **Raw Value Preservation for Dirty CSV Survival:**
   - Raw string values (`record_ref_raw`, `value_raw`, `location_raw`, `event_date_raw`, `recorded_on_raw`, `base_value_raw`, `adjustment_raw`, `total_value_raw`) are captured alongside normalized/cleaned fields across both System A and System B models.
   - Unresolved foreign keys or unparseable dates/numbers are stored as `null=True, blank=True` while retaining original strings, guaranteeing 100% row survival during ingestion.
   - Raw monetary fields (`base_value_raw`, `adjustment_raw`, `total_value_raw` in SystemARecord, and `value_raw` in SystemBEntry) prevent data loss when records contain unparseable formatting (e.g. currency symbols, commas, or corrupted characters), allowing audits and post-ingestion remediation.
3. **Monetary Precision with DecimalField:**
   - All financial quantities (`base_value`, `adjustment`, `total_value`, `value`) use `DecimalField(max_digits=14, decimal_places=2)` to prevent floating-point inaccuracies.
4. **Location Ownership Principle:**
   - Ownership (`org_id`) is strictly managed by `Location`. Records link to `Location` via `on_delete=models.PROTECT` and resolve organizational hierarchy through the relationship.

---

## 10. CSV Data Ingestion & Importer Architecture (Phase 3)

### Context
Phase 3 requires an idempotent, resilient CSV data importer implemented via a Django management command (`python manage.py import_data`) to ingest `locations.csv` (5 rows), `system_a.csv` (120 rows), and `system_b.csv` (121 rows).

### Decisions
1. **Execution Ordering:**
   - `locations.csv` is imported first, preloading an in-memory resolution cache (`locations_cache = {loc.location_id: loc for loc in Location.objects.all()}`) to optimize foreign key assignments for System A and System B transactions without redundant database round-trips.
2. **String-First Ingestion & Non-Destructive Parsing:**
   - Python `csv.DictReader` reads every cell as raw text.
   - Raw values are immediately preserved into dedicated raw fields (`location_raw`, `event_date_raw`, `base_value_raw`, `adjustment_raw`, `total_value_raw`, `record_ref_raw`, `recorded_on_raw`, `value_raw`).
   - If location lookups fail, `location` is set to `None` while retaining `location_raw`.
   - If date parsing fails, `event_date`/`recorded_on` is set to `None` while retaining raw strings.
3. **Strict Monetary Parsing Rules:**
   - `Decimal` is used exclusively for all monetary values (never `float`).
   - Handles multi-comma and Indian-style numbering formats (`1,25,400.00` $\to$ `125400.00`).
   - Empty or blank monetary strings are parsed to `None`, never to `0`.
4. **Reference Normalization Strategy:**
   - System B references are normalized to canonical `REC-XXXX` format using regex matching (`rec1034` $\to$ `REC-1034`, `REC - 1070` $\to$ `REC-1070`, `1112` $\to$ `REC-1112`).
   - The uncleaned original reference is retained in `record_ref_raw`.
5. **Idempotent Ingestion via `update_or_create()`:**
   - Keys: `location_id` for Location, `record_id` for System A, and `entry_id` for System B.
   - Repeated runs produce 0 duplicate records, updating existing records without changing total counts.
6. **Per-Row Transactional Isolation:**
   - Each record is encapsulated in `transaction.atomic()` savepoints. If an unexpected integrity or database error occurs on a single row, only that row is rolled back, the error is logged with filename, row number, and reason, and processing proceeds to subsequent rows.
7. **Complete Dataset Ingestion (Including Orphans):**
   - Decoupled System B modeling ensures all 121 System B entries are persisted regardless of whether a matching System A record exists.

---

## 11. Reconciliation Engine Architecture & Business Rules (Phase 4)

### Context
Phase 4 implements the core reconciliation domain service (`backend/reconcile/services/reconciliation.py`) comparing System A records against System B entries independently of HTTP/view layers.

### Decisions & Policies
1. **VOIDED Record Policy:**
   - Inactive/voided transactions in System A (`state = 'VOIDED'`) are part of reconciliation audit.
   - If a VOIDED System A record has no entries in System B, it is **not** reported as `MISSING_IN_B`.
   - If one or more System B entries reference a VOIDED record, it is flagged with dedicated reason `VOIDED_IN_B` (rather than ordinary `VALUE_MISMATCH` or `DUPLICATE_IN_B`). This isolates erroneous billings/entries against cancelled orders for investigation while preserving both systems' records.
2. **Valid Split-Entry Policy:**
   - Multiple System B entries referencing a single System A record are grouped by `record_ref`.
   - If all monetary amounts are present and their sum equals System A's `total_value` using Decimal arithmetic, the group is classified as a **valid split entry** (e.g. `REC-1055` split into `71950.93 + 107926.39 == 179877.32`) and produces **no** duplicate disagreement.
   - If the sum differs, the record is flagged as `DUPLICATE_IN_B` with the exact difference computed.
3. **Blank / Missing Monetary Value Policy:**
   - Incomplete monetary values (`None`) are **never** treated as zero.
   - Group sums are never computed with missing values.
   - Any single or grouped entry with a `None` value is flagged as `VALUE_MISMATCH` with `difference = None`, preventing false calculations while flagging the missing data.
4. **Multiple Disagreement Handling Strategy:**
   - Independent discrepancies on a single record are never silently suppressed or merged into an ambiguous state.
   - A single transaction can independently report:
     - Monetary discrepancy (`VALUE_MISMATCH` or `DUPLICATE_IN_B`)
     - Facility discrepancy (`LOCATION_MISMATCH`)
     - Temporal discrepancy (`DATE_MISMATCH`)
   - For location and date comparisons, evaluations are only made when both data points are populated, avoiding false mismatches when dates/locations are missing.
   - Entry IDs and specific field discrepancies are retained per disagreement for surgical remediation.
5. **Decoupled Service Layer with Deterministic Structured Output:**
   - Logic is isolated in `ReconciliationEngine` returning `Disagreement` dataclass instances.
   - Disagreements are deterministically sorted by `(record_id, reason, system_b_entry_ids[0])`.
   - Strict `Decimal` arithmetic is used throughout with no floating-point conversions.

---

## 12. Backend REST API, Multi-Tenancy & Redaction Policies (Phase 5)

### Context
Phase 5 exposes reconciliation discrepancies through a secure RESTful API endpoint (`GET /api/disagreements/`) enforcing multi-tenant isolation, cross-tenant data redaction, and strict parameter validation.

### Decisions & Policies
1. **Authoritative Organization Ownership Mapping:**
   - The canonical organization mapping is strictly derived via the relational schema:
     `Location.location_id -> Location.org_id`.
   - Client-provided identifiers and unverified CSV fields are never trusted as proof of organization ownership.
2. **Matched-Record Ownership Policy:**
   - A matched record (where System A exists) belongs solely to the organization that owns its System A facility (`record.location.org_id`).
   - For example, `REC-1077` has System A facility `LOC-102` (belonging to `ORG-A`), while its System B entry has facility `LOC-201` (belonging to `ORG-B`). Ownership of `REC-1077` and its reconciliation discrepancy belongs exclusively to `ORG-A`.
3. **Orphan Entry Ownership Policy:**
   - A genuine orphan System B entry (where `record_ref` does not exist anywhere in System A) belongs to the organization that owns its System B facility (`entry.location.org_id`).
   - Example: `ENT/2026/4901` references non-existent `REC-1999` and has location `LOC-102` (`ORG-A`). It is visible exclusively to `ORG-A` and hidden from `ORG-B`.
4. **Cross-Tenant System B Entry Isolation & Redaction Policy:**
   - If a System B entry references a System A record owned by another organization (such as `ENT/2026/4077` referencing `REC-1077` owned by `ORG-A`), it is **strictly forbidden** from being exposed to the organization owning the B location (`ORG-B`).
   - When requested by the owning organization (`ORG-A`), the discrepancy is returned, the owning organization's location (`LOC-102`) is preserved, but the foreign System B location (`LOC-201`) is **redacted to `null`**. Explanations and responses never leak foreign facility codes or foreign organization names.
5. **Database-Level Tenant Filtering Strategy:**
   - Tenant isolation is enforced in the initial SQL queries before reconciliation, never by loading all records into application memory:
     ```python
     # 1. Scope System A records by tenant
     scoped_a = SystemARecord.objects.filter(location__org_id=org)
     scoped_a_ids = list(scoped_a.values_list('record_id', flat=True))

     # 2. Scope System B entries:
     # - references this org's System A records; OR
     # - genuine orphan belonging to this org's location
     all_a_ids = SystemARecord.objects.values_list('record_id', flat=True)
     scoped_b = SystemBEntry.objects.filter(
         Q(record_ref__in=scoped_a_ids) |
         ((Q(record_ref__isnull=True) | ~Q(record_ref__in=all_a_ids)) & Q(location__org_id=org))
     )
     ```
   - Only these scoped records are passed to `ReconciliationEngine(scoped_a, scoped_b)`.
6. **Strict Decimal Serialization:**
   - Discrepancy values and monetary differences are serialized via DRF as decimal strings (e.g. `"1000.00"`), never floating-point numbers.
   - Missing or uncalculable values remain `null`.




