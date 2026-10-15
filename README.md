# Company & Contact Discovery Pipeline

**Version 0.3.0.** A free, public-data pipeline that finds companies and the people at them, scores each person against *your* profile and goals (get hired, find investors, find advisors), and drafts short outreach emails for you to review. A React app has a **Review UI** (jobs, companies, contacts, review queue, suppression) and a **Control Panel** (search & run, dashboard, live runs, schedules, sources, safety, history, cache).

**Nothing is sent without you.** Approving a draft only sets `status = approved`; sending happens only when you click Send in the app (Gmail API, local) or in a Gmail window yourself.

## How it works

`discover → resolve_domains → find_contacts → verify_email → enrich → rank → draft`

1. **discover**: pulls companies (and, for job sources, the matching job and any published contact email) from the enabled sources. A discover `limit` counts *new* companies, so each run adds the next batch.
2. **resolve_domains**: guesses `name.{com,io,ai,in}` and keeps a domain only if it answers HTTP and has MX records.
3. **find_contacts**: reads `/about /team /contact /company` for founders, execs and recruiters (robots.txt respected).
4. **verify_email**: an address printed on a page scores 90; otherwise name-pattern guesses score 30 (unverified). SMTP probing is off by default.
5. **enrich**: finds the company's own job board from its careers page (Greenhouse / Lever / Ashby), reads its jobs, adds news and blog signals.
6. **rank**: scores every person 0-100 with an intent (`hire`, `invest`, `advise`) and a one-line reason.
7. **draft**: writes a short email per person from one of three templates (or Ollama), using only `profile.yaml` facts and stored signals.

### Two apps, one sidebar layout

The UI has a sidebar with five modules (Run, Opportunities, Outreach, Automation, Settings & Safety), tabs inside each, and an **Apps** switcher at the top right. The second app, **Maps Leads**, finds local businesses with no website: the Chrome extension in `tools/page-to-csv` reads a Google Maps results list you have open and posts it straight to the app (**Find** live feed, **Leads** with score, **Pitch** with WhatsApp links, **Tracker**). Use it only where you have the right to collect that data (Google's terms restrict scraping Maps). The theme is Aphelion's design system (`web/src/index.css` and `design.ts` are copied verbatim).

### Maps Leads: automatic crawler and the strict website check

- **Search queue** (Maps Leads → Find): keyword × area rows (for example `skin clinic in Saket, Delhi`), with a Delhi high-ticket starter pack. One Maps search stops at roughly 100 results, so split a city by neighbourhood.
- **Crawler** (`tools/maps_crawler/crawl.py`, Playwright + headless Chromium): takes the next pending search, scrolls the list, opens every business, reads website/phone/listing links (only a panel whose title matches the business is accepted, otherwise the lead stays "not checked"), posts leads to the app, then asks it to run the strict check. Local smoke test: `python tools/maps_crawler/crawl.py --query "skin clinic in Saket, Delhi" --max-businesses 5 --dry-run`.
- **GitHub Actions** (`.github/workflows/maps-crawler.yml`): every 6 hours plus a manual run, max 120 businesses per run. Repo secrets: `APP_URL` and `INGEST_TOKEN` (also set `INGEST_TOKEN` on the server so only the crawler can add leads). It stops, and the run fails, if Google shows a CAPTCHA; it never tries to get around one. Google's terms restrict automated collection of Maps data, so use it only where you have the right to; cloud IPs are often challenged.
- **Strict website check** (`verify_websites` stage): a lead is "no website" only if details were read, Maps lists no site, the listing has no site link, and no matching domain exists. A listed website counts as has-site; Instagram/Facebook/Justdial/Practo are not websites; a listing link or a guessed domain (`name.com`, `.in`, `.co.in`) must match the business name or phone number. Statuses: *has site, probable site, no website, not checked*. Only *no website* appears as a lead by default, and the evidence is shown.

### Search & run (the main page)

Set role keywords (default `frontend, react, ui engineer`), *Remote jobs only*, and your goals. Only jobs whose title matches a keyword (and is remote, if ticked) become hiring signals; a matching job adds +30 to a contact's score. **Enable all recommended free sources** turns on every no-config source; **Run everything** queues all stages in order. Repeat it to keep growing the list. The **Remote jobs** page lists every matched job with its apply link and best contact.

## Sources (all free, no keys)

| Source | What | Notes |
|---|---|---|
| `hn_hiring` | latest "Ask HN: Who is hiring?" posts matching your search | many posts include a contact email (confidence 90) |
| `remoteok`, `remotive`, `weworkremotely` | remote job feeds | RemoteOK and Remotive ask for a link back if data is shown publicly and for modest request rates; this app is private and low-volume |
| `greenhouse`, `lever`, `ashby` | public job-board JSON for the slugs you configure (starter list built in); more boards are found automatically from company careers pages | public posting APIs |
| `ycombinator` | company list | uses the community mirror `yc-oss.github.io/api` (a third-party static JSON dataset), because the directory itself needs an embedded Algolia key. Batch accepts `W24` or `Winter 2024` |
| `sec_edgar` | tickers + submissions filtered by SIC code | identify yourself via `CONTACT_EMAIL`; stay under 10 req/s |
| `press_rss` | TechCrunch, Entrackr, Inc42, ET Startups, Crunchbase News | funding and launch signals; investor firms named in funding news ("led by X") become `investor` companies, whose team pages yield investor contacts. Verify the ET feed URL in `app/sources/press_rss.py` |
| `company_site` | `/about /team /contact /company /careers /blog` | robots.txt and each site's terms apply |
| `mca21` | **stub** | no public API; cannot be enabled |

**LinkedIn is not accessed.** It is excluded on purpose: its terms prohibit scraping, and its `robots.txt` disallows it, which this app's HTTP client honours. Instead, **Review → Import LinkedIn** takes your own `Connections.csv` from LinkedIn's "Get a copy of your data" export: each connection becomes a contact (a shared email counts as published, confidence 90) and gets a +25 score bonus after the next `rank`.

## Run it locally

```bash
docker compose up -d                       # Postgres + Redis
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
make install
cp .env.example .env                       # set CONTACT_EMAIL (used in the User-Agent)
cp profile.yaml.example profile.yaml       # your facts; drafts use only this + stored signals
make migrate
make run-api       # http://127.0.0.1:8000  (docs at /docs)
make run-worker    # RQ worker + scheduler
make run-web       # http://localhost:5173
```

CLI (in-process, no Redis): `python -m pipeline run --stage all`, `python -m pipeline run --stage discover --source hn_hiring --no-dry-run`, `python -m pipeline purge --person 42`. Without `--no-dry-run` the CLI follows the stored dry-run default (on), so the first run changes nothing.

### Drafting with Ollama (optional)

Install from <https://ollama.com>, `ollama pull llama3.1:8b`, and keep `LLM_PROVIDER=ollama`. If it is unreachable or fails validation (80-120 words, opt-out line, JSON) the Jinja2 templates in `templates/outreach_{hire,invest,advise}.j2` are used. `LLM_PROVIDER=template` needs no model.

## Free hosting (what the live deployment uses)

| Part | Where |
|---|---|
| Web app | Vercel, project root `web/`, deploys on every push; `web/vercel.json` rewrites `/api/*` to the backend |
| API + job runner + scheduler | Render free web service from the `Dockerfile` (`QUEUE_MODE=thread`: one process, no Redis) |
| Database | Neon free Postgres |

Render needs `DATABASE_URL` (Neon string; `postgres://` is converted automatically), `CONTACT_EMAIL`, `PROFILE_YAML` (the contents of your profile), `AUTH_ENABLED`, and optionally `DRAFT_MIN_CONFIDENCE` / `DRAFT_MIN_SCORE`. A GitHub Action (`.github/workflows/deploy.yml`) triggers a Render deploy on each push, using the `RENDER_API_KEY` and `RENDER_SERVICE_ID` repo secrets. The free instance sleeps when idle and its disk is wiped on restart, so only the database persists.

## Configuration

`DATABASE_URL`, `REDIS_URL`, `CONTACT_EMAIL`, `LLM_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL`, `SMTP_PROBE_ENABLED` (default false), `SMTP_PROBE_DOMAINS`, `DAILY_SEND_CAP`, `DRY_RUN_DEFAULT`, `QUEUE_MODE` (`rq` | `thread` | `none`), `PROFILE_PATH` / `PROFILE_YAML`, `DATA_DIR`, `DRAFT_MIN_CONFIDENCE` (80; the hosted app uses 30 so guessed addresses can be drafted, labelled "guess"), `DRAFT_MIN_SCORE`, `AUTH_ENABLED` and `CONTROL_API_TOKEN`.

**Auth:** with `AUTH_ENABLED=true` (default) the control API accepts only loopback unless `CONTROL_API_TOKEN` is set, and when it is set every route needs `Authorization: Bearer <token>`. The hosted deployment runs with `AUTH_ENABLED=false`, **so its URL is open to anyone who finds it**; turn auth back on if that matters.

## Sending (from your own Gmail)

Approved drafts go to **Send today**: published addresses first, up to your daily allowance (`DAILY_SEND_CAP`, default 15, rolling 24 h), each one a separate email to one person (no CC or BCC).

- **Gmail API (fast, free, local only):** one-time setup: create a Google Cloud project, enable the Gmail API, set the OAuth consent screen to *External / Testing* and add your Gmail as a test user, create a *Desktop app* OAuth client and save it as `credentials.json` in the repo root; then run `python -m pipeline gmail-auth` and click Allow. Scope is `gmail.send` only. `credentials.json` and `token.json` are git-ignored. On **Send today**, *Preview (dry run)* lists what would go out, *Send N now* sends them with a short pause between each, marks them sent, and stops at the first error. Messages are flagged important (`Importance: high`).
- **Or by hand:** *Open in Gmail* opens a pre-filled compose window per person (set "Send from" to choose the account) and *I sent it* logs it.

Marking a first email sent schedules a day-4 follow-up and a day-10 last note for your review; replied/declined/done cancels them. Sending is local only: the hosted app never has your Gmail token.

## Safety and compliance

Kill switch (423 on new jobs, workers skip queued jobs, running jobs stop at the next item), per-item cancel, dry run (rolls back; no SMTP), robots.txt per host with crawl-delay, per-source rate limit (minimum 1 s), every external request appended to `data/requests.log`, suppression list enforced in verify_email, draft and approval, catch-all addresses never `verified`, SMTP RCPT probing only for allowlisted domains, never sends mail. Guessed addresses (confidence 30) may bounce; the UI labels them.

## Quality

```bash
make test      # 80+ tests, no network (HTTP, DNS, SMTP mocked), SQLite
make lint      # ruff check . && mypy app
cd web && npm run build
```

## Roadmap

- More boards: grow the Greenhouse/Lever/Ashby coverage from careers pages and the YC list.
- Optional free pinger so scheduled runs fire while the free server is asleep.

## Known limitations

- Port 25 is often blocked, so SMTP checks may return `unknown`.
- Tests use SQLite; production is Postgres. With SQLite, job logs are written when a stage ends.
- RQ's forking worker is unix-only; `make run-worker` uses `SimpleWorker` so it also runs on Windows.
- Company-site people extraction is heuristic and misses unusual layouts. `resolve_domains` guesses can pick the wrong company with a common name.
- Free hosting is slow (about 15 s per company when finding contacts) and a deploy restarts the server, which fails any job running at that moment.
- The first Alembic revision creates tables from the models; later ones are explicit migrations.
