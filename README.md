# Company & Contact Discovery Pipeline

Local, free pipeline that discovers companies from public sources, finds founders/execs/recruiters, derives candidate business emails with confidence scores, attaches recent public signals, and drafts short outreach emails for human review. A React app provides a **Review UI** (`/review`) and a **Control Panel** (`/control`).

**Nothing is ever sent.** `app/sender/` is a stub (`send()` raises `NotImplementedError`); approving a draft only sets `status = approved`.

## Setup

```bash
docker compose up -d                    # Postgres + Redis (skip if you run them yourself)
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
make install                            # pip install -r requirements-dev.txt && npm install in web/
cp .env.example .env                    # set CONTACT_EMAIL (goes in every User-Agent)
cp profile.yaml.example profile.yaml    # your facts; the draft stage reads only this + stored signals
make migrate                            # alembic upgrade head
make run-api                            # http://127.0.0.1:8000  (docs at /docs)
make run-worker                         # RQ worker + APScheduler (schedules reload every 30s)
make run-web                            # http://localhost:5173  (proxies /api -> FastAPI)
```

CLI (runs in-process, no Redis needed):

```bash
python -m pipeline run --stage all
python -m pipeline run --stage discover --source greenhouse --dry-run
python -m pipeline run --stage enrich --from-cache      # replay raw responses from data/raw
python -m pipeline purge --person 42                    # delete a person + emails + drafts
```

Without `--dry-run/--no-dry-run` the CLI uses the stored default (`DRY_RUN_DEFAULT=true`), so **the first run changes nothing**; pass `--no-dry-run` to write.

Stages in order: `discover → resolve_domains → find_contacts → verify_email → enrich → draft`. Enable sources and set their filters on the Sources page (or `PUT /control/sources/{name}`) first; a source with missing required config cannot be enabled.

### Drafting with Ollama (optional)

1. Install from <https://ollama.com>, then `ollama pull llama3.1:8b` (low RAM: `llama3.2:3b` and set `OLLAMA_MODEL`).
2. Keep `LLM_PROVIDER=ollama`. If Ollama is unreachable, or a draft fails JSON/80-120-word/opt-out validation twice, the Jinja2 `TemplateProvider` is used and a warning lands in the job log. `LLM_PROVIDER=template` needs no model at all.

## Configuration

All via environment (`.env`), validated by `app/core/config.py`: `DATABASE_URL`, `REDIS_URL`, `CONTACT_EMAIL`, `LLM_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL`, `SMTP_PROBE_ENABLED` (default `false`), `SMTP_PROBE_DOMAINS`, `DAILY_SEND_CAP`, `DRY_RUN_DEFAULT`, `CONTROL_API_TOKEN`, `DATA_DIR`, `PROFILE_PATH`. Runtime toggles (kill switch, dry-run default, send cap) live in the `app_settings` table.

Control API auth: loopback only unless `CONTROL_API_TOKEN` is set, then `Authorization: Bearer <token>` is required (set it in the web app via "API token").

## Behaviour

- **Kill switch**: new jobs get HTTP 423, workers skip queued jobs, running jobs stop at the next item.
- **Cancel**: stages call `ctx.check()` between items, so they stop within one item.
- **Dry run**: full logic, rollback at the end, no SMTP probing; the "what would change" counts are in `job_runs.stats.dry_run_report`.
- **Progress**: every stage logs `{processed,total,errors}`; `GET /control/jobs/{id}/logs/stream` is SSE (`log`, `progress`, `end` events).
- **Schedules**: cron (UTC), anything faster than every 15 minutes is rejected.
- Endpoints are served at the root (`/companies`, `/control/...`); the web app reaches them through the `/api` dev proxy.

## Sources and terms

Review each site's terms before enabling it. The pipeline only fetches public pages/APIs, checks `robots.txt` before HTML, rate-limits per domain, and sends `CompanyPipeline/0.1 (+contact: <CONTACT_EMAIL>)`.

| Source | What | Terms / notes |
|---|---|---|
| `ycombinator` | company list | The YC directory is rendered from an Algolia index that needs an embedded app key, so it is not called. Default is the community static mirror `yc-oss.github.io/api` (free, no key); override with `query_filters.endpoint`. That is a third-party dataset: confirm you are comfortable with it. |
| `greenhouse` / `lever` / `ashby` | public job-board JSON for slugs you configure | Public posting APIs intended for job boards; keep the rate limit conservative. |
| `sec_edgar` | tickers + submissions JSON filtered by SIC | SEC fair-access policy: identify yourself (done via User-Agent), stay under 10 req/s. |
| `company_site` | `/about /team /contact /company /blog` | Per-site terms and robots.txt apply; disallowed pages are skipped. |
| `press_rss` | TechCrunch, Entrackr, Inc42, ET Startups, Crunchbase News feeds | Headlines + links only. Verify the ET feed URL in `app/sources/press_rss.py`. |
| `mca21` | **stub** | MCA21 has no public API; needs a licensed/bulk source. Cannot be enabled. |

## Adding a source

Subclass `Source` in `app/sources/`, set `name`, `requires_config`, `seed`, implement `fetch_companies` / `fetch_people` / `fetch_signals` using `self.client` (never raw httpx), register it in `app/sources/__init__.py`, and add a fixture test.

## Compliance

robots.txt (cached per host, crawl-delay honoured); no logins, CAPTCHA, paywall or rate-limit bypass; no LinkedIn access (only profile links a company page itself publishes); suppression list enforced in verify_email, draft, approval and `can_send`; every external request is appended to `data/requests.log`; SMTP RCPT probing is **off by default**, only for domains in `SMTP_PROBE_DOMAINS`, never sends mail, tests a random address first for catch-all, and is never run in dry runs. Confidence: published on page 90 · SMTP accepted 80 · catch-all 40 · MX only 30 · unknown 10; catch-all is never `verified`.

## Quality

```bash
make test    # pytest, no network, SMTP/DNS mocked, SQLite
make lint    # ruff check . && mypy app
cd web && npm run build   # tsc + vite
```

## Known limitations

- Port 25 is often blocked by ISPs/cloud hosts, so probes may return `unknown`.
- Tests use SQLite; production targets Postgres (JSON columns become JSONB). With SQLite, job logs are written when the stage ends instead of live.
- RQ's forking `Worker` is unix-only; `make run-worker` uses `SimpleWorker` so it also works on Windows (no per-job timeout enforcement there).
- Company-site people extraction is heuristic (name/title line patterns) and will miss unusual layouts.
- `resolve_domains` guesses `name.{com,io,ai,in}` and needs live HEAD + MX; skipped with `--from-cache`.
- The initial Alembic revision creates tables from the models; later changes should be autogenerated diffs.
- Postgres/Redis were not exercised here (Docker was unavailable on the build machine); the full flow is covered against SQLite and fixtures.
