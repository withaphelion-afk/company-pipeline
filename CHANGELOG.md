# Changelog

## 0.3.0
- Gmail API sender (local): dry-run preview, one email per person, daily allowance, important flag, stops at first error; `python -m pipeline gmail-auth`.
- Featured projects (Orbit and Dentiq with live links) in every email; opt-out line removed from templates.
- Junk-contact filter (page headings, customer quotes); first.last address preferred; tests isolated from local `.env`.

## 0.2.0
- Search & run page: role keywords, remote-only switch, goals (hire / invest / advise), one-click pipeline.
- Remote jobs page: every job matching the saved search, with apply link and best contact.
- New free sources: Hacker News "Who is hiring", RemoteOK, Remotive, We Work Remotely; job boards found automatically from careers pages.
- Relevance scoring, intents and a `rank` stage; investor firms discovered from funding news; three draft templates.
- Free hosting: in-process job runner (no Redis), Dockerfile, Render + Neon + Vercel with auto-deploy via GitHub Action.
- Import LinkedIn: upload your own Connections.csv export (no scraping); connections get a score bonus.
- Send today page, daily allowance, published-first ordering, automatic follow-up (day 4) and last note (day 10), reply/decline tracking.
- Gmail workflow: "Open in Gmail" (pre-filled compose), Copy and "I sent it" on approved drafts; PITCH.md guide.
- Auth is now optional (`AUTH_ENABLED`).

## 0.1.0
- Initial pipeline (7 stages), review UI, control panel, fixtures-based test suite.
