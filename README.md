# DealerOS

DealerOS is a full-stack automotive inventory reconciliation platform designed to ingest, process, and reconcile vehicle inventory data across disparate management systems (`System A`, `System B`, and canonical `Locations`).

This project is built using a decoupled architecture:
- **Backend:** Django 5 with Django REST Framework (DRF), `django-cors-headers`, SQLite, and `pytest-django`.
- **Frontend:** React 19 single-page application powered by Vite, JavaScript, and custom CSS.
- **Data Layer:** Centralized `data/` directory housing original source CSV data.

---

## Project Structure

```
DealerOS/
├── backend/
│   ├── backend/               # Django root project configuration (settings, urls, wsgi, asgi)
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── settings.py        # SQLite, DRF, and CORS settings
│   │   ├── urls.py            # Root URL routing, mounting /api/
│   │   └── wsgi.py
│   ├── reconcile/             # Django app for reconciliation domain
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── api/               # REST API layer (Phase 5)
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py # DRF serializers for reconciliation outputs
│   │   │   └── views.py       # API views with tenant isolation & query validation
│   │   ├── apps.py
│   │   ├── management/        # Ingestion commands (import_data)
│   │   ├── migrations/        # Database schema migrations
│   │   ├── models.py          # Location, SystemARecord, SystemBEntry models
│   │   ├── services/          # Core business services
│   │   │   └── reconciliation.py  # Domain reconciliation engine (Phase 4)
│   │   ├── test_api.py        # API endpoint and tenant-isolation test suite (Phase 5)
│   │   ├── test_reconciliation.py # Engine test suite (18 test scenarios)
│   │   ├── tests.py           # Model and importer test suite
│   │   ├── urls.py            # API routing for reconcile endpoints
│   │   └── views.py           # Application views
│   ├── manage.py              # Django CLI utility
│   ├── pytest.ini             # Pytest configuration for Django
│   ├── requirements.txt       # Python backend dependencies
│   └── venv/                  # Python virtual environment (ignored in git)
├── frontend/
│   ├── public/                # Static public assets
│   ├── src/                   # React application source
│   │   ├── assets/            # Component assets and images
│   │   ├── App.css            # Main application styling
│   │   ├── App.jsx            # Root React component
│   │   ├── index.css          # Base design tokens and typography
│   │   └── main.jsx           # React DOM bootstrap entry point
│   ├── index.html             # HTML entry point template
│   ├── package.json           # Node.js dependencies and scripts
│   ├── package-lock.json      # Locked npm dependency tree
│   └── vite.config.js         # Vite bundler configuration
├── data/
│   ├── locations.csv          # Dealership location mapping data
│   ├── system_a.csv           # System A vehicle inventory extract
│   └── system_b.csv           # System B vehicle inventory extract
├── README.md                  # Project documentation and developer guide
├── DECISIONS.md               # Technical and architectural decision records
└── .gitignore                 # Root git ignore specification
```

---

## Environment Prerequisites

The following runtimes and tools are verified for this project:

- **Python:** `3.11+` (tested with Python `3.12.10`)
- **Node.js:** `v18+` (tested with Node.js `v24.19.0`)
- **npm:** `v9+` (tested with npm `11.17.0`)
- **Git:** (tested with Git `2.55.0`)

---

## Backend Setup & Execution

### 1. Navigate to backend directory
```bash
cd backend
```

### 2. Create and activate virtual environment
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  python -m venv venv
  .\venv\Scripts\activate.bat
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install backend dependencies
```bash
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
python manage.py migrate
```

### 5. Ingest CSV datasets
```bash
python manage.py import_data
```
*Imports `locations.csv`, `system_a.csv`, and `system_b.csv` idempotently.*

### 6. Start Django development server
```bash
python manage.py runserver
```
The backend API is now running at `http://127.0.0.1:8000/`.

### 7. Run test suite
```bash
pytest
```

---

## Frontend Setup & Execution

### 1. Navigate to frontend directory
```bash
cd frontend
```

### 2. Install frontend dependencies
```bash
npm install
```

### 3. Start Vite development server
```bash
npm run dev
```
The React development server runs by default at `http://localhost:5173/`.

### 4. Build for production (optional)
```bash
npm run build
```

---

## Reconciliation Engine (Phase 4)

DealerOS includes a standalone, independently testable reconciliation service located at `backend/reconcile/services/reconciliation.py`.

### Capabilities:
- **Identifier Matching:** Matches `SystemARecord.record_id` against normalized `SystemBEntry.record_ref`.
- **Valid Split Entries:** Automatically identifies when multiple System B entries sum exactly to a System A `total_value` (using exact `Decimal` arithmetic), distinguishing valid splits from duplicates.
- **VOIDED Record Policy:** Evaluates voided System A records without false missing alerts; flags System B entries referencing voided records as `VOIDED_IN_B`.
- **Independent Discrepancy Classification:**
  - `MISSING_IN_B`: Active System A record has no entry in System B.
  - `ORPHAN_IN_B`: System B entry references a nonexistent System A record.
  - `DUPLICATE_IN_B`: Multiple System B entries referencing a single System A record with an unequal sum.
  - `VALUE_MISMATCH`: Single entry value discrepancy or missing/blank monetary value (never treated as zero).
  - `LOCATION_MISMATCH`: Differing location identifiers between System A and System B.
  - `DATE_MISMATCH`: Differing transaction dates when both dates are populated.
  - `VOIDED_IN_B`: System B entry referencing a voided System A record.

---

## REST API Specification (Phase 5)

DealerOS exposes a REST API powered by Django REST Framework at `/api/disagreements/`.

### Endpoint: `GET /api/disagreements/`

Retrieves the list of reconciliation disagreements scoped strictly to an organization.

#### Query Parameters:
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `org` | String | **Yes** | Authoritative organization identifier (e.g., `ORG-A`, `ORG-B`). Must match registered locations. Missing returns `400 Bad Request`; nonexistent returns `404 Not Found`. |
| `reason` | String | No | Filter by discrepancy reason: `MISSING_IN_B`, `ORPHAN_IN_B`, `DUPLICATE_IN_B`, `VALUE_MISMATCH`, `LOCATION_MISMATCH`, `DATE_MISMATCH`, `VOIDED_IN_B`. Invalid reason returns `400 Bad Request`. |
| `sort` | String | No | Sort discrepancies by: `record_id`, `value_asc`, `value_desc`, `difference_asc`, `difference_desc`. Discrepancies with null values/differences sort last. Invalid sort returns `400 Bad Request`. |

#### Tenant Isolation Guarantees:
1. **Authoritative Location Mapping:** Organization identity is derived exclusively via `Location.location_id -> Location.org_id`.
2. **Database-Level Scoping:** Records are filtered prior to reconciliation execution using SQL `Q` expressions:
   - System A: Filtered by `location__org_id=org`.
   - System B: Includes entries matching the tenant's System A records OR orphan entries whose own location belongs to the tenant.
3. **Cross-Tenant Redaction:** When a System A record in `ORG-A` mismatches against a System B entry located in `ORG-B` (e.g., `REC-1077`), the foreign location identifier is redacted (`"system_b_location": null`) and explanations are sanitized to prevent metadata leakage.

#### Example Request:
```bash
curl -X GET "http://127.0.0.1:8000/api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH&sort=difference_desc"
```

#### Example Response:
```json
{
  "organization": "ORG-A",
  "summary": {
    "total_disagreements": 3,
    "breakdown": {
      "VALUE_MISMATCH": 3
    }
  },
  "count": 3,
  "disagreements": [
    {
      "record_id": "REC-1088",
      "reason": "VALUE_MISMATCH",
      "system_a_value": "89000.00",
      "system_b_value": "87000.00",
      "difference": "2000.00",
      "system_a_date": "2026-03-22",
      "system_b_date": "2026-03-22",
      "system_a_location": "LOC-101",
      "system_b_location": "LOC-101",
      "system_b_entries": [
        {
          "entry_id": "ENT/2026/4088",
          "recorded_on": "2026-03-22",
          "value": "87000.00",
          "location": "LOC-101",
          "label": "MATCH"
        }
      ],
      "explanation": "Value mismatch: System A total 89000.00 != System B total 87000.00 (diff: 2000.00)"
    }
  ]
}
```

---

## Configuration Files Overview

| Configuration File | Location | Purpose |
| :--- | :--- | :--- |
| `settings.py` | `backend/backend/` | Configures Django application settings: SQLite database backend, `INSTALLED_APPS` (including DRF, CORS, and `reconcile`), `MIDDLEWARE` order (`CorsMiddleware`), and CORS origins. |
| `urls.py` | `backend/backend/` | Primary URL routing file routing admin endpoints and mounting `/api/` to `reconcile.urls`. |
| `urls.py` | `backend/reconcile/` | Application-level routing for reconciliation endpoints. |
| `requirements.txt` | `backend/` | Lists locked Python dependencies (`django`, `djangorestframework`, `django-cors-headers`, `pytest`, `pytest-django`). |
| `pytest.ini` | `backend/` | Configures pytest to automatically load Django settings (`backend.settings`) and discover test files. |
| `package.json` | `frontend/` | Defines frontend project metadata, scripts (`dev`, `build`, `preview`), and dependencies (`react`, `react-dom`, `vite`). |
| `vite.config.js` | `frontend/` | Configures Vite build tool and the `@vitejs/plugin-react` plugin for fast HMR. |
| `.gitignore` | Project Root | Specifies patterns to ignore compiled binaries, virtual environments, `node_modules`, SQLite runtime files, and OS artifacts. |
| `DECISIONS.md` | Project Root | Documents architectural, tooling, and design decisions made throughout project development. |

---

## Development Constraints & Principles

1. **No Premature Business Logic:** Domain models and reconciliation logic will be introduced cleanly in dedicated phases.
2. **Immutable Data Source:** Original CSV files in `data/` remain untouched as the raw canonical source.
3. **Decoupled Architecture:** Frontend and backend communicate exclusively through RESTful JSON APIs.
