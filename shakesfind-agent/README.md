# ShakesFind Agent

Config‑driven agent that checks theatre pages, extracts events, and upserts to Notion.

## 1) Notion setup (once)
Create 3 databases (or reuse yours) with these props (names matter):

**Companies**
- Name (title)
- Homepage URL (url)
- Productions URL (url)
- City (text) | State (text) | Country (text)
- Timezone (text) e.g. America/New_York
- Scrape Strategy (multi-select) e.g. jsonld, ics, rss, html
- HTML List Selector (text) – for HTML scraping
- HTML Field Map (text) – JSON: {"title": ".card h3", "dates": ".card .dates", "url": "a@href", "venue": ".venue"}
- Status (select: active, paused)
- Last Checked (date)
- Notes (rich text)

**Plays**
- Title (title)
- Aliases (multi-text)
- Canonical ID (text, optional)

**Productions**
- Company (relation → Companies)
- Play (relation → Plays)
- Title (Display) (text)
- Start Date (date)
- End Date (date)
- Venue (text)
- City (rollup from Company or text)
- State (rollup from Company or text)
- Country (rollup from Company or text)
- Show URL (url)
- Ticket URL (url)
- Source Page (url)
- Source Hash (text)
- Match Confidence (number)
- Status (select: new, changed, verified, ignored)
- Last Seen At (date)
- Raw Dates Text (text)

### Productions Inbox (Notion view)
Create a **Board** or **Table** view on **Productions**:
- **Filter**: `Status is new` OR `Status is changed`
- **Sort**: `Last Seen At` descending
- Show columns: Title (Display), Company, Dates, Venue, City/State, Show URL, Raw Dates Text, Match Confidence
- Optional quick actions: when you review and accept a row, set `Status = verified`; if it’s noise, set `Status = ignored`.

## 2) Local setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env` and fill in values.
4. Put a few test companies into Notion with their **Productions URL** and strategy.
5. `python main.py --dry-run` to preview; `python main.py` to write to Notion.

## 3) GitHub Actions (automation)
- Commit the repo to GitHub.
- Add Secrets: `NOTION_TOKEN`, `COMPANIES_DB_ID`, `PLAYS_DB_ID`, `PRODUCTIONS_DB_ID`, `CONTACT_EMAIL`.
- The workflow runs on a cron; change schedule as you like.

## 4) Add a new company in 3 minutes
- Add a row in **Companies** with Productions URL, Strategy, and (if needed) HTML selectors + field map.
- Next run will pick it up automatically.

## Notes
- Extraction order: JSON‑LD → ICS/RSS (future) → HTML (selectors) → Headless (future)
- Timezone is applied per Company when parsing date ranges.
- Dedupe via Source Hash of {company, title, start_date, end_date, venue}.
