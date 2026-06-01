# HTA Website Design Specification

**Version:** 0.1  
**Date:** 2026-06-01  
**Status:** Design — ready for review before implementation  
**Scope:** Local-first development; cloud-ready architecture

---

## Table of Contents

1. [Decisions and constraints](#1-decisions-and-constraints)
2. [Architecture overview](#2-architecture-overview)
3. [Repository layout](#3-repository-layout)
4. [Session model and data storage](#4-session-model-and-data-storage)
5. [Backend — FastAPI](#5-backend--fastapi)
6. [Frontend — React](#6-frontend--react)
7. [Real-time streaming design](#7-real-time-streaming-design)
8. [Plot strategy](#8-plot-strategy)
9. [Export and report download](#9-export-and-report-download)
10. [Local development setup](#10-local-development-setup)
11. [Cloud readiness](#11-cloud-readiness)
12. [Implementation sequence](#12-implementation-sequence)

---

## 1. Decisions and constraints

| Decision | Choice | Implication |
|---|---|---|
| LLM dialogue | Real-time streaming | SSE from backend → frontend; no polling |
| Authentication | None (v1) | Session identified by UUID only; stored in browser `localStorage` |
| Data storage | Server-side, persistent | Sessions stored as files; 7-day TTL with background cleanup |
| Deployment | Local first, cloud later | Storage and config abstracted behind interfaces from day one |

---

## 2. Architecture overview

```
Browser (React + TypeScript)
    │
    │  REST + SSE  (HTTP/1.1)
    ▼
FastAPI backend  (Python 3.11)
    │                │
    │ imports        │ reads/writes
    ▼                ▼
hta package      Session store
(core library)   (local filesystem  →  S3 in cloud)
    │
    ▼
Azure OpenAI (GPT-5.4)  /  R via rpy2 (BET)
```

The backend is a **thin HTTP wrapper** around the existing `hta` library. It does not contain statistical logic — all of that lives in `src/hta/`. The backend's job is session management, HTTP routing, and streaming.

The frontend never touches data directly. Every action goes through the API. This ensures the cloud migration only requires changing the storage backend, not the frontend or the core library.

---

## 3. Repository layout

New `web/` directory alongside the existing `src/` layout:

```
Better_Testing_Agent/
├── src/hta/                    # Core library (existing — untouched)
├── tests/                      # Library tests (existing — untouched)
│
├── web/
│   ├── backend/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Web-layer config (port, session TTL, storage type)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── sessions.py     # Session CRUD
│   │   │   ├── dialogue.py     # SSE dialogue endpoint
│   │   │   ├── run.py          # SSE analysis execution
│   │   │   └── export.py       # PDF / Markdown download
│   │   ├── storage/
│   │   │   ├── base.py         # Abstract StorageBackend interface
│   │   │   ├── local.py        # LocalStorage (dev)
│   │   │   └── s3.py           # S3Storage (cloud — stub for now)
│   │   ├── plots.py            # PlotSpec → Plotly JSON conversion
│   │   ├── pdf.py              # Report → PDF via WeasyPrint
│   │   └── schemas.py          # Pydantic request/response schemas for the API
│   │
│   ├── frontend/
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       ├── types/
│   │       │   └── api.ts      # TypeScript types mirroring Pydantic schemas
│   │       ├── hooks/
│   │       │   ├── useSession.ts
│   │       │   └── useSSE.ts
│   │       ├── api/
│   │       │   └── client.ts   # Typed fetch wrappers for every API endpoint
│   │       └── components/
│   │           ├── Landing/
│   │           │   ├── Landing.tsx
│   │           │   └── HowItWorks.tsx
│   │           ├── Wizard/
│   │           │   ├── Wizard.tsx          # Step controller + progress bar
│   │           │   ├── StepUpload.tsx      # Drag-drop CSV + preview table
│   │           │   ├── StepVariables.tsx   # Column pickers + hypothesis text
│   │           │   ├── StepDialogue.tsx    # Chat window + design summary card
│   │           │   ├── StepReview.tsx      # Confirm before running
│   │           │   └── StepResults.tsx     # Full results view
│   │           ├── Results/
│   │           │   ├── PrimaryResult.tsx   # Statistic / p-value / significance badge
│   │           │   ├── EffectSizeCard.tsx  # Effect size + CI + interpretation
│   │           │   ├── AssumptionTable.tsx # Colour-coded assumption checks
│   │           │   ├── CaveatList.tsx      # Severity-labelled caveats
│   │           │   ├── PlotViewer.tsx      # Tabbed Plotly charts
│   │           │   ├── PlainSummary.tsx    # Plain-language callout box
│   │           │   ├── MethodsText.tsx     # APA text + copy button
│   │           │   └── ExportBar.tsx       # PDF + Markdown download buttons
│   │           ├── About/
│   │           │   └── About.tsx
│   │           └── shared/
│   │               ├── Badge.tsx           # Status / severity badges
│   │               ├── Spinner.tsx
│   │               └── CopyButton.tsx
│   │
│   ├── docker-compose.yml      # Local dev: backend + frontend together
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── data/                   # Gitignored — session files stored here locally
│       └── sessions/
│
├── pyproject.toml              # Existing — add web deps to [project.optional-dependencies].web
├── TECHNICAL_REPORT.md
├── IMPLEMENTATION_PLAN.md
└── WEBSITE_DESIGN.md           # This document
```

---

## 4. Session model and data storage

### Session lifecycle

```
CREATED → PROFILED → DESIGNED → READY → RUNNING → COMPLETE
                                              └──→ FAILED
```

| State | Reached after |
|---|---|
| `CREATED` | CSV uploaded successfully |
| `PROFILED` | `DataProfile` computed |
| `DESIGNED` | Dialogue complete; `StudyDesign` captured |
| `READY` | User confirms on Step 4 |
| `RUNNING` | `POST /api/sessions/{id}/run` called |
| `COMPLETE` | `Report` stored |
| `FAILED` | Any unhandled error during execution |

### Storage structure

Each session is a directory under `data/sessions/{session_id}/`:

```
data/sessions/
└── {uuid}/
    ├── metadata.json     # { session_id, status, created_at, expires_at }
    ├── data.csv          # original upload
    ├── preview.json      # first 10 rows + column inferences (returned on upload)
    ├── variables.json    # { outcome_variable, group_variable, hypothesis }
    ├── profile.json      # DataProfile (serialised Pydantic model)
    ├── design.json       # StudyDesign
    ├── graph.json        # CausalGraph
    ├── result.json       # TestResult
    └── report.json       # Report
```

Files are written **incrementally** as each pipeline stage completes. This means the frontend can poll for progress or stream events; it also means a server restart doesn't lose work mid-pipeline.

### TTL and cleanup

- Sessions expire after **7 days** from `created_at`.
- A FastAPI background task (`asyncio` periodic task) runs every hour and deletes expired session directories.
- No database required for v1 — metadata is read from `metadata.json`.

### Abstract storage interface

```python
class StorageBackend(Protocol):
    def write(self, session_id: str, filename: str, data: bytes) -> None: ...
    def read(self, session_id: str, filename: str) -> bytes: ...
    def exists(self, session_id: str, filename: str) -> bool: ...
    def list_sessions(self) -> list[str]: ...
    def delete_session(self, session_id: str) -> None: ...
```

`LocalStorage` writes to `web/data/sessions/`. `S3Storage` wraps `boto3` and writes to a configured bucket. The active backend is selected from the environment variable `HTA_STORAGE_BACKEND=local|s3`.

---

## 5. Backend — FastAPI

### Configuration (`web/backend/config.py`)

All values come from environment variables (`.env` at project root):

```
HTA_STORAGE_BACKEND=local          # "local" or "s3"
HTA_SESSION_TTL_DAYS=7
HTA_BACKEND_PORT=8000
HTA_ALLOWED_ORIGINS=http://localhost:5173   # comma-separated for CORS
# (Azure OpenAI keys inherited from existing HTA config)
```

### API routes

#### `POST /api/sessions`
Accepts a multipart CSV upload. Creates a session directory, stores the file, runs `DataProfiler.profile()`, writes `profile.json`, returns session metadata.

**Request:** `multipart/form-data` with field `file` (CSV)

**Response:**
```json
{
  "session_id": "uuid",
  "status": "PROFILED",
  "columns": ["group", "bp", "age"],
  "inferred_types": { "group": "CATEGORICAL", "bp": "CONTINUOUS", "age": "CONTINUOUS" },
  "preview": [ { "group": "A", "bp": 120, "age": 45 }, ... ]
}
```

---

#### `PATCH /api/sessions/{id}/variables`
Records the user's variable selection and hypothesis text. Stores `variables.json`. No computation yet.

**Request:**
```json
{
  "outcome_variable": "bp",
  "group_variable": "group",
  "hypothesis": "Treatment reduces blood pressure vs control"
}
```

**Response:** `{ "status": "ok" }`

---

#### `POST /api/sessions/{id}/dialogue`
One turn of the study-design dialogue. Calls `DesignDialogue` with the user message, streams the assistant response as SSE, and on completion writes `design.json` and `graph.json`.

**Request:** `{ "user_message": "This is a randomised trial" }`

**SSE stream:**
```
data: {"type": "token", "content": "Thank"}
data: {"type": "token", "content": " you"}
...
data: {"type": "done", "is_complete": false}
```

When the LLM calls `capture_study_design`, the final event is:
```
data: {"type": "done", "is_complete": true, "study_design": { ... }}
```

The frontend renders the accumulated tokens in real-time as a chat bubble, then displays the study design summary card when `is_complete=true`.

---

#### `POST /api/sessions/{id}/run`
Runs the full pipeline: selector → executor → reporter. Streams progress events as SSE, then writes `result.json` and `report.json`.

**SSE stream:**
```
data: {"type": "progress", "stage": "selecting_test", "message": "Selecting statistical test..."}
data: {"type": "progress", "stage": "executing_test", "message": "Running Welch's t-test..."}
data: {"type": "progress", "stage": "generating_report", "message": "Generating report..."}
data: {"type": "done", "report": { ... full Report JSON ... }}
```

On `type: done`, the frontend renders the full results view.

---

#### `GET /api/sessions/{id}`
Returns whatever is currently available for a session — used for restoring state if the user refreshes.

**Response:** `{ "status": "COMPLETE", "profile": {...}, "design": {...}, "report": {...} }`

---

#### `GET /api/sessions/{id}/export/pdf`
Renders the report to PDF via WeasyPrint and streams the file.

**Response:** `Content-Type: application/pdf`

---

#### `GET /api/sessions/{id}/export/markdown`
Renders the report to a Markdown string and streams the file.

**Response:** `Content-Type: text/markdown`

---

### Error handling

All endpoints return standard error envelopes:
```json
{ "error": "SESSION_NOT_FOUND", "message": "No session with id abc123" }
```

HTTP status codes: 400 (bad input), 404 (session not found), 422 (validation error), 500 (pipeline failure). Pipeline failures also set `session.status = FAILED` and store an error message in `metadata.json`.

---

## 6. Frontend — React

### Technology choices

| Choice | Reason |
|---|---|
| **Vite** | Fast dev server; instant HMR for React + TypeScript |
| **React + TypeScript** | Component model suits wizard; types match Pydantic schemas |
| **Tailwind CSS** | Utility-first; no design-system overhead; clean academic look |
| **Plotly.js** | Interactive charts from PlotSpec JSON; no server rendering |
| **TanStack Query** | Data fetching, caching, SSE integration |

### State model

Session state lives in a single React context (`SessionContext`) and is persisted to `localStorage` under `hta_session_id`. On page load, if a session ID exists in localStorage and the backend returns status `COMPLETE`, the results view is shown directly (session restore).

```typescript
type SessionState = {
  sessionId: string | null;
  status: SessionStatus;
  step: 1 | 2 | 3 | 4 | 5;
  columns: string[];
  inferredTypes: Record<string, string>;
  preview: Record<string, unknown>[];
  variables: VariablesPayload | null;
  studyDesign: StudyDesign | null;
  report: Report | null;
};
```

### Page routing

Two routes only (React Router):
- `/` — Landing page
- `/analyse` — Wizard (all 5 steps live here; step is internal state, not a URL)
- `/about` — About page

A persistent top nav with: **HTA** logo (links to `/`), **About** link, and the session ID shown as a small chip when a session is active.

---

### Wizard steps in detail

#### Step 1 — Upload

- Full-width drag-and-drop zone. Accepts `.csv` only (enforced client-side and server-side).
- On drop: calls `POST /api/sessions`, shows a spinner, then transitions to the preview state.
- Preview: scrollable table of first 10 rows. Below each column header: an editable type chip (CONTINUOUS / CATEGORICAL / BINARY / ORDINAL) pre-filled from `inferred_types`. Users can correct misdetections.
- "Looks good →" button proceeds to Step 2.

#### Step 2 — Variables & hypothesis

- Two dropdowns: **Outcome variable** (required) and **Group / predictor variable** (optional; has a "No group variable — testing correlation" option).
- Textarea: **Research hypothesis**. Placeholder: *"e.g., Patients in the treatment group have lower blood pressure than controls."*
- Below the textarea: 3 clickable example prompts (chips) for common scenarios:
  - "Two groups, comparing means"
  - "Before and after a single intervention"
  - "Association between two continuous measures"
- "Next →" calls `PATCH /api/sessions/{id}/variables` and proceeds to Step 3.

#### Step 3 — Study design dialogue

- Split view: left is the **chat window**, right is the **study design summary card** (initially empty).
- The chat opens with the first assistant message arriving immediately via SSE.
- User types replies in a text input at the bottom. Each send calls `POST /api/sessions/{id}/dialogue` and streams the response token-by-token into a new chat bubble.
- When `is_complete=true` arrives, the right panel populates with the `StudyDesign` card showing:
  - Design type (Experimental / Observational / Quasi-experimental)
  - Measurement type (Between / Within / Mixed)
  - Randomised: yes/no
  - Confounders identified (list)
  - Relationship form (linear / monotone / nonlinear) — only shown for correlation analyses
- Each field on the summary card is **inline-editable** — a click turns it into a dropdown or text field. This lets users correct any misunderstanding before proceeding.
- "Confirm design →" proceeds to Step 4.

#### Step 4 — Review & run

- Single-screen confirmation showing three cards:
  1. **Data summary**: N observations, variables profiled, any data quality warnings.
  2. **Study design**: the confirmed StudyDesign card from Step 3.
  3. **Planned test**: the test the selector will run (computed live on this step via a lightweight `GET /api/sessions/{id}/preview-test` endpoint), with a one-sentence rationale.
- A large "Run analysis →" button. Clicking calls `POST /api/sessions/{id}/run` and transitions to Step 5 with a progress view.

#### Step 5 — Results

See §6 wireframe below. Replaces the wizard content entirely.

---

### Results view — detailed layout

```
┌─ NAV ─────────────────────────────────────────────────────────────────┐
│ HTA                                          About   Session: a3f2…   │
└───────────────────────────────────────────────────────────────────────┘

┌─ LEFT PANEL (320px fixed) ────┐  ┌─ RIGHT PANEL (flex) ───────────────┐
│                               │  │                                     │
│  DATA PROFILE                 │  │  ┌─ PRIMARY RESULT ──────────────┐  │
│  ─────────────────────        │  │  │  Welch's t-test                │  │
│  N = 100  │  2 variables      │  │  │  t = 3.14   df = 98           │  │
│  2 missing (blood_pressure)   │  │  │  p = 0.002  ● Significant     │  │
│                               │  │  └────────────────────────────────┘  │
│  TEST SELECTED                │  │                                     │
│  ─────────────────────        │  │  EFFECT SIZE                        │
│  Welch's t-test               │  │  Cohen's d = 0.52                   │
│  [Why this test? ▾]           │  │  95% CI  [0.21 – 0.83]             │
│  (expandable rationale)       │  │  ● Medium effect                    │
│                               │  │                                     │
│  ASSUMPTION CHECKS            │  │  SENSITIVITY                        │
│  ─────────────────────        │  │  Min detectable d = 0.28            │
│  ✅ Normality (SW p=0.31)     │  │  at N=100, α=.05, power=.80        │
│  ✅ Sample size (N=50/group)  │  │                                     │
│  ✅ Independence              │  │  ─────────────────────────────────  │
│                               │  │                                     │
│  CAVEATS                      │  │  PLAIN-LANGUAGE SUMMARY             │
│  ─────────────────────        │  │  ┌──────────────────────────────┐  │
│  ⚠ Marginal p-value (0.04)   │  │  │ "The treatment group showed   │  │
│  ℹ Observational design       │  │  │  meaningfully lower blood     │  │
│                               │  │  │  pressure than controls       │  │
│  ← Start new analysis         │  │  │  (p=.002, d=0.52)."          │  │
│                               │  │  └──────────────────────────────┘  │
│                               │  │                                     │
│                               │  │  PLOTS                              │
│                               │  │  [Boxplot] [QQ-plot] [Histogram]   │
│                               │  │  ┌──────────────────────────────┐  │
│                               │  │  │   [Interactive Plotly chart] │  │
│                               │  │  └──────────────────────────────┘  │
│                               │  │                                     │
│                               │  │  METHODS TEXT  [Copy]               │
│                               │  │  ┌──────────────────────────────┐  │
│                               │  │  │ "An independent-samples      │  │
│                               │  │  │  Welch's t-test was used…"   │  │
│                               │  │  └──────────────────────────────┘  │
│                               │  │                                     │
│                               │  │  [⬇ Download PDF] [⬇ Download MD] │
└───────────────────────────────┘  └─────────────────────────────────────┘
```

**Colour coding:**
- `CRITICAL` assumption / caveat → red badge
- `WARNING` → amber badge
- `INFO` → blue badge
- `MET` → green badge
- Significant p-value → green chip; not significant → grey chip

**"Why this test?" expandable:** A collapsible panel showing the full `get_selection_rationale()` text. Aimed at Profile C users who want to audit the decision.

---

### About page

Three sections:
1. **How HTA works** — the 5-step pipeline in plain language; decision tree summary.
2. **Supported tests** — table of all 17 tests with brief descriptions and when each is selected.
3. **References and limitations** — BET paper citation, scipy/pingouin, scope limitations (continuous data for BET, v0.1.0 test coverage, no multiple-outcome correction).

---

## 7. Real-time streaming design

All streaming uses **Server-Sent Events (SSE)** over standard HTTP. No WebSocket needed — the dialogue and execution streams are one-directional (server → client).

### SSE event format

Every SSE message is a JSON object. The `type` field is the discriminator:

| `type` | When | Key fields |
|---|---|---|
| `token` | Each LLM output chunk (dialogue) | `content: string` |
| `done` | End of dialogue turn | `is_complete: bool`, `study_design?: object` |
| `progress` | Pipeline stages (run) | `stage: string`, `message: string` |
| `result` | Pipeline complete | `report: object` |
| `error` | Any failure | `error: string`, `message: string` |

### Client-side SSE hook (`useSSE.ts`)

```typescript
function useSSE(url: string, onEvent: (e: SSEEvent) => void) {
  useEffect(() => {
    const es = new EventSource(url);
    es.onmessage = (e) => onEvent(JSON.parse(e.data));
    es.onerror = () => es.close();
    return () => es.close();
  }, [url]);
}
```

The dialogue component accumulates `token` events into a string and renders them as they arrive, giving the typing-in-real-time effect. The `done` event triggers the study design card.

---

## 8. Plot strategy

The `TestExecutor` already produces `PlotSpec` objects (declarative, data-only). The backend converts these to **Plotly JSON** via `web/backend/plots.py`. No server-side image rendering — Plotly runs entirely in the browser.

### PlotSpec → Plotly mapping

| `plot_type` | Plotly trace type | Notes |
|---|---|---|
| `boxplot` | `Box` | One trace per group |
| `histogram` | `Histogram` | Overlapping, opacity=0.7 |
| `qqplot` | `Scatter` (points) + `Scatter` (line) | Theoretical vs. sample quantiles |
| `scatter` | `Scatter` (markers) | For correlation / BET |

The API returns Plotly JSON in the `Report` object under `report.plots[i].plotly_json`. The `PlotViewer` component renders it with `<Plot data={...} layout={...} />` from `react-plotly.js`.

This means:
- No PNG encoding/decoding
- Interactive charts (zoom, hover, download from Plotly toolbar)
- Smaller payload than rasterised images

---

## 9. Export and report download

### Markdown export

A `render_markdown(report: Report) -> str` function in `web/backend/pdf.py` produces:

```markdown
# HTA Analysis Report
**Date:** 2026-06-01  **Session:** a3f2…

## Data Profile
…

## Study Design
…

## Statistical Test: Welch's t-test
**Statistic:** t = 3.14   **df** = 98   **p = 0.002** ✓ Significant

## Effect Size
Cohen's d = 0.52 (medium), 95% CI [0.21, 0.83]

## Assumption Checks
| Assumption | Status | Note |
|---|---|---|
| Normality | ✅ Met | Shapiro-Wilk p = 0.31 |
…

## Caveats
…

## Plain-Language Summary
…

## Methods
An independent-samples Welch's t-test was used…
```

Streamed as `Content-Disposition: attachment; filename="hta_report_{session_id}.md"`.

### PDF export

`render_pdf(report: Report) -> bytes` in `web/backend/pdf.py`:
1. Calls `render_markdown` and converts to HTML via `markdown` library.
2. Wraps in an HTML template with academic styling (clean serif font, no sidebar).
3. Converts to PDF via **WeasyPrint**.
4. Returns bytes streamed with `Content-Type: application/pdf`.

WeasyPrint system dependencies (Cairo, Pango) are included in `Dockerfile.backend`.

### Copy-to-clipboard (methods text)

The `MethodsText` component has a `[Copy]` button using `navigator.clipboard.writeText()`. No server call — the methods text is already in the report JSON.

---

## 10. Local development setup

### Prerequisites

- Docker Desktop (or docker + docker-compose CLI)
- OR: Python 3.11 + Node 20 (for running services directly without Docker)

### Option A — Docker Compose (recommended)

```yaml
# web/docker-compose.yml
services:
  backend:
    build:
      context: ..
      dockerfile: web/Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ../src:/app/src        # hot-reload HTA library changes
      - ../web/backend:/app/web/backend
      - ../web/data:/app/web/data
    env_file:
      - ../.env
    environment:
      HTA_STORAGE_BACKEND: local
      HTA_SESSION_TTL_DAYS: "7"
      HTA_ALLOWED_ORIGINS: "http://localhost:5173"

  frontend:
    build:
      context: web/frontend
      dockerfile: ../Dockerfile.frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
    environment:
      VITE_API_BASE: "http://localhost:8000"
```

```bash
cd web
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

### Option B — Direct (no Docker)

```bash
# Terminal 1 — backend
cd Better_Testing_Agent
pip install -e ".[web]"          # new optional dep group
uvicorn web.backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd web/frontend
npm install
npm run dev                      # http://localhost:5173
```

### New `pyproject.toml` dependency group

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "python-multipart>=0.0.9",    # file upload
    "aiofiles>=23.0.0",           # async file I/O
    "weasyprint>=61.0",           # PDF export
    "markdown>=3.6",              # Markdown → HTML for PDF
    "boto3>=1.34.0",              # S3 (stub for now, used in cloud)
]
```

---

## 11. Cloud readiness

The following are baked in from day one so the cloud migration is a config change, not a rewrite:

| Concern | Local approach | Cloud swap |
|---|---|---|
| Storage | `LocalStorage` writes to `web/data/` | Set `HTA_STORAGE_BACKEND=s3`, configure bucket name |
| Config | `.env` at project root | Cloud secret manager (AWS Secrets Manager / Azure Key Vault) injects same env vars |
| Sessions | Files on local disk | S3 objects with the same key structure |
| Serving | `uvicorn` direct | Behind a reverse proxy (nginx / ALB); same `uvicorn` process |
| Frontend | Vite dev server | `npm run build` → static files served by nginx or CDN |
| Containerisation | `docker-compose.yml` | Push images to ECR / ACR; deploy with ECS / App Service / Kubernetes |
| Background cleanup | `asyncio` periodic task in FastAPI | Replace with a scheduled Lambda / Cloud Function calling `DELETE /api/sessions/expired` |

**No code changes are required for the cloud migration** — only environment variable updates and infrastructure provisioning.

---

## 12. Implementation sequence

The website is built in three phases, each independently testable.

### Phase W1 — Backend skeleton (no LLM, dry-run only)

**Goal:** All API endpoints working; sessions stored; pipeline runs in dry-run mode.

- [ ] `web/backend/main.py` — FastAPI app with CORS, error handlers, lifespan cleanup task
- [ ] `web/backend/storage/base.py` + `local.py` — `LocalStorage` implementation
- [ ] `web/backend/schemas.py` — request/response Pydantic models
- [ ] `web/backend/api/sessions.py` — upload, PATCH variables, GET session
- [ ] `web/backend/api/run.py` — SSE pipeline execution (dry-run)
- [ ] `web/backend/plots.py` — `PlotSpec → Plotly JSON`
- [ ] `web/backend/pdf.py` — Markdown and PDF rendering
- [ ] `web/backend/api/export.py` — PDF and Markdown download
- [ ] `web/docker-compose.yml` + Dockerfiles
- [ ] Manual test: `curl` through the full upload → run → export flow

**Gate:** Full dry-run pipeline accessible via `curl` with correct JSON responses.

---

### Phase W2 — Frontend wizard

**Goal:** Working UI connected to the Phase W1 backend; real-time SSE not yet wired.

- [ ] Vite + React + TypeScript + Tailwind project setup
- [ ] `types/api.ts` — TypeScript types matching all Pydantic schemas
- [ ] `api/client.ts` — typed fetch wrappers
- [ ] `Landing.tsx` — hero + how-it-works + CTA
- [ ] `Wizard.tsx` — step controller + progress bar
- [ ] `StepUpload.tsx` — drag-drop + preview table + type chips
- [ ] `StepVariables.tsx` — dropdowns + hypothesis textarea + example chips
- [ ] `StepReview.tsx` — confirmation cards + run button
- [ ] `StepResults.tsx` — results layout (static mock data first)
- [ ] All Results sub-components: `PrimaryResult`, `EffectSizeCard`, `AssumptionTable`, `CaveatList`, `PlotViewer`, `PlainSummary`, `MethodsText`, `ExportBar`
- [ ] `About.tsx`
- [ ] `localStorage` session restore

**Gate:** Full wizard flow completes end-to-end with dry-run data; results render correctly.

---

### Phase W3 — Real-time dialogue and live LLM

**Goal:** SSE dialogue working; `StepDialogue.tsx` wired up; live API key required.

- [ ] `web/backend/api/dialogue.py` — SSE dialogue endpoint with streaming GPT-5.4
- [ ] `web/backend/main.py` — register dialogue router
- [ ] `useSSE.ts` hook
- [ ] `StepDialogue.tsx` — chat window + token streaming + study design summary card + inline edit
- [ ] End-to-end test: full analysis with live LLM from browser to report

**Gate:** Full analysis completes live from browser with a real CSV and a real API key.

---

*Last updated: 2026-06-01. Approved decisions in §1; ready for Phase W1 implementation.*
