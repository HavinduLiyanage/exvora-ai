# 0. Executive Snapshot

Exvora AI is a small FastAPI backend that generates day-by-day Sri Lanka travel itineraries from a local POI dataset. It filters and ranks candidate POIs using preferences and constraints, then schedules activities with transfers (Google Maps live verification optional) and returns budget-aware, stateless itineraries. It also supports single-day feedback-based repacking.

- Key capabilities
  - Stateless itinerary generation with candidates → rules → rank → schedule pipeline [app/api/routes.py:99–147][app/engine/candidates.py:84–139][app/engine/rules.py:9–50][app/engine/rank.py:162–209][app/engine/schedule.py:231–252]
  - Transfer estimation with heuristic default, optional Google Distance Matrix live verification with caching and call caps [app/engine/transfers.py:93–151]
  - Structured errors and common HTTP exception handling [app/api/errors.py:6–23][app/main.py:43–61]
  - Feedback endpoint to repack a single day with actions like remove_item and rate bias [app/api/routes.py:241–327]
  - Currency selection and simple conversion stub in responses [app/utils/currency.py:32–55][app/api/routes.py:184–214]

- Key gaps
  - No persistent storage or user sessions; all is stateless and in-memory [README.md:7–11]
  - No authentication/authorization; open endpoints
  - Google Maps verification depends on env vars; no retry/backoff/circuit breaker [app/engine/transfers.py:120–144]
  - Dataset is a sample JSON; no ingestion pipeline, small coverage [app/dataset/loader.py:8–35][app/dataset/pois.sample.json:1–946]
  - Limited validation on many response dicts (use of untyped dicts in DayPlan items) [app/schemas/models.py:155–160]

Repo digest

- Total files: 27 (code + tests + clients; excluding ignored paths)
- Python files: 25 [glob scan]
- Test files: 3 [tests/test_*.py]
- Lines of code (Python only): ~1,400 (estimate across app/, tests/, clients/python, scripts)
- Endpoints detected: 3 (/v1/healthz GET, /v1/itinerary POST, /v1/itinerary/feedback POST) [openapi.json:7–100]
- Pydantic models: 15 [app/schemas/models.py:6–233]

# 1. Directory Map (depth 3)

```
app/
  api/
    errors.py
    routes.py
  dataset/
    loader.py
    pois.sample.json
  engine/
    candidates.py
    rank.py
    rules.py
    schedule.py
    transfers.py
  schemas/
    models.py
  config.py
  logs.py
  main.py
clients/
  node/
    index.ts
  python/
    exvora.py
scripts/
  bench.py
  dump_openapi.py
tests/
  test_engine_core.py
  test_itinerary_api.py
  test_transfers.py
Dockerfile
README.md
requirements.txt
pyproject.toml
openapi.json
```

Important folders

- app: FastAPI app, API routes, engine, schemas, and config [app/main.py:38–41]
- app/api: HTTP endpoints and error helpers [app/api/routes.py:63–71][app/api/errors.py:6–23]
- app/engine: Core planning pipeline (candidates, rules, rank, schedule, transfers) [app/engine/candidates.py:84–139][app/engine/rules.py:9–50][app/engine/rank.py:162–209][app/engine/schedule.py:231–252][app/engine/transfers.py:93–151]
- app/dataset: Loader and sample POIs JSON [app/dataset/loader.py:8–40]
- app/schemas: Pydantic request/response models [app/schemas/models.py:6–233]
- clients: Simple Python and Node clients [clients/python/exvora.py:7–41][clients/node/index.ts:61–116]
- scripts: OpenAPI exporter and latency benchmark [scripts/dump_openapi.py:11–24][scripts/bench.py:44–148]
- tests: API and engine unit tests [tests/test_itinerary_api.py:26–82][tests/test_engine_core.py:9–25][tests/test_transfers.py:7–26]

# 2. How to Run (from README + code)

- Create venv (Windows/macOS/Linux) [README.md:39–48]

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

- Install dependencies [README.md:50–53]

```bash
pip install -r requirements.txt
```

- Run dev server (reload) [README.md:57–59]

```bash
uvicorn app.main:app --reload
```

- Run tests [README.md:118–130]

```bash
pytest
pytest -v
pytest tests/test_itinerary_api.py
pytest --cov=app tests/
```

- Docker build/run [README.md:186–196][Dockerfile:33–34]

```bash
docker build -t exvora-ai .
docker run -p 8080:8080 exvora-ai
```

# 3. Configuration & Environment

Env is handled via Pydantic Settings, automatically reading .env if present [app/config.py:6–11][app/config.py:35–41].

Referenced environment variables and settings:

- USE_GOOGLE_ROUTES (bool): toggles Google verification [app/config.py:7][app/engine/transfers.py:121–146]
- GOOGLE_MAPS_API_KEY (str): Google client key [app/config.py:8][app/engine/transfers.py:58–62]
- TRANSFER_CACHE_TTL_SECONDS (int): per-process transfer cache TTL [app/config.py:9][app/engine/transfers.py:34–37]
- TRANSFER_MAX_CALLS_PER_REQUEST (int): safety cap per request [app/config.py:10]
- RATE_LIMIT_PER_MINUTE (int): in-memory rate limit per IP [app/config.py:11][app/api/routes.py:37–43]
- DEFAULT_CURRENCY (str): default response currency (USD) [app/config.py:14][app/utils/currency.py:43–55]
- RADIUS_KM_LIGHT/MODERATE/INTENSE (float): candidate radius by pace [app/config.py:17–19][app/engine/candidates.py:71–81]
- RANK_W_PREF/TIME/BUDGET/DIV/HEALTH (float): ranking weights [app/config.py:22–26][app/engine/rank.py:150–157]
- BREAK_AFTER_MINUTES (int): insert breaks during scheduling [app/config.py:29][app/engine/schedule.py:85–103]
- GOOGLE_PER_REQUEST_MAX_CALLS (int): hard cap enforced by transfers [app/config.py:32][app/engine/transfers.py:121–129]
- GOOGLE_VERIFY_FAILURE_424 (bool): escalate 424 on failed verification [app/config.py:33–34][app/engine/schedule.py:211–219]
- MAX_ITEMS_PER_DAY (legacy const): day item cap; accessed via settings fallback [app/config.py:51–54][app/api/routes.py:163–173]

# 4. API Surface (FastAPI)

Mounted under /v1 [app/main.py:38–41]. OpenAPI confirms three endpoints [openapi.json:7–100].

| Method | Path | Handler | Request model | Response model | Error codes | Source |
|---|---|---|---|---|---|---|
| GET | /v1/healthz | healthz | - | object {status, pois_loaded} | 200 | [app/api/routes.py:63–67] |
| POST | /v1/itinerary | build_itinerary | ItineraryRequest | ItineraryResponse | 400, 409, 422, 424, 429 | [app/api/routes.py:69–223] |
| POST | /v1/itinerary/feedback | feedback_repack | FeedbackRequest | DayPlan | 409, 422, 424, 429 | [app/api/routes.py:241–327] |

Examples

- POST /v1/itinerary (abridged) [app/schemas/models.py:168–210]

```json
{
  "currency": "LKR",
  "days": [ { "date": "2025-09-10", "summary": {"title": "Day Plan", "est_cost": 85.0}, "items": [ {"start": "09:00", "end": "10:30", "place_id": "gangaramaya_temple"}, {"type": "transfer", "from_place_id": "gangaramaya_temple", "to_place_id": "temple_of_tooth", "mode": "DRIVE", "duration_minutes": 15, "distance_km": 3.0, "source": "heuristic" } ] } ]
}
```

- POST /v1/itinerary/feedback (returns a single DayPlan) [app/api/routes.py:274–319]

```json
{
  "date": "2025-09-10",
  "summary": {"title": "Day Plan", "est_cost": 50.0},
  "items": [ {"start": "12:00", "end": "13:00", "place_id": "ChIJlocked", "title": "Reserved Lunch"} ],
  "notes": ["Removed 1 items based on feedback"]
}
```

# 5. Data Models (Pydantic & Schemas)

Defined in `app/schemas/models.py`.

- TripDateRange: start:str, end:str; validates max 14 days [app/schemas/models.py:6–22]
- DayTemplate: start:str, end:str, pace: Literal[light|moderate|intense] [app/schemas/models.py:31–42]
- TripContext: base_place_id:str, date_range:TripDateRange, day_template:DayTemplate, modes:List[str] [app/schemas/models.py:45–59]
- Preferences: themes:list[str]=[], activity_tags:list[str]=[], avoid_tags:list[str]=[], currency:Optional[str] [app/schemas/models.py:61–75]
- Constraints: daily_budget_cap:Optional[float], max_transfer_minutes:Optional[int], currency:Optional[str] [app/schemas/models.py:77–88]
- Lock: place_id:str, start/end/title optional [app/schemas/models.py:90–105]
- ItineraryRequest: trip_context, preferences, constraints?, locks:list[Lock]=[] [app/schemas/models.py:107–127]
- Activity: start/end/place_id/title?/estimated_cost? [app/schemas/models.py:129–136]
- Transfer: type="transfer", from_place_id, to_place_id, mode, duration_minutes, distance_km, source [app/schemas/models.py:138–146]
- Summary: title?/est_cost?/walking_km?/health_load? [app/schemas/models.py:148–153]
- DayPlan: date:str, summary:dict, items:list[dict], notes?:list[str] [app/schemas/models.py:155–160]
- Totals: total_cost?, total_walking_km?, total_duration_hours? [app/schemas/models.py:162–166]
- ItineraryResponse: currency:str, days:list[DayPlan], totals?, notes? [app/schemas/models.py:168–211]
- FeedbackAction: type one of [rate_item, remove_item, request_alternative, edit_time, daily_signal], plus fields [app/schemas/models.py:213–221]
- FeedbackRequest: date, base_place_id, day_template, modes, preferences?, constraints?, locks, current_day_plan, actions [app/schemas/models.py:223–233]

Usage mapping

- ItineraryRequest → POST /v1/itinerary [openapi.json:24–61]
- ItineraryResponse → POST /v1/itinerary response [openapi.json:38–59]
- FeedbackRequest → POST /v1/itinerary/feedback [openapi.json:62–99]
- DayPlan → POST /v1/itinerary/feedback response [openapi.json:76–86]

# 6. Engine Pipeline (What happens on /v1/itinerary)

Order of stages in handler [app/api/routes.py:99–147]:

1) Candidate generation: `basic_candidates(pois, prefs, date_str, day_window, base_place_id, pace)`
   - Filters by avoid tags, theme overlap, seasonality, opening hours, and radius-by-pace [app/engine/candidates.py:84–131]
   - Inputs: list of POIs, preferences, date, day window, base place, pace
   - Outputs: filtered POIs and reason counts [app/engine/candidates.py:134–139]

2) Rules/hard filters: `apply_hard_rules(cands, constraints, locks)`
   - Drops by budget, transfer-duration constraint, and coarse lock-conflict heuristic for long activities [app/engine/rules.py:23–44]
   - Inputs: candidates, constraints, locks
   - Outputs: filtered candidates, reasons [app/engine/rules.py:46–50]

3) Scoring/ranking: `rank(cands, daily_cap, prefs, day_start, day_end, pace)`
   - Weighted score across preference fit, time fit, budget fit, diversity, health fit using settings weights [app/engine/rank.py:141–159][app/engine/rank.py:150–157]
   - Returns sorted list and metrics [app/engine/rank.py:179–209]

4) Scheduling/packing: `schedule_days(dates, ranked, daily_cap, day_start, day_end, locks, pace)` builds each day via `schedule_day`
   - Locks first, compute gaps, fit activities to open-hour windows, insert transfers, optional Google sequence verification, insert breaks after continuous activity [app/engine/schedule.py:105–128][app/engine/schedule.py:152–176][app/engine/schedule.py:201–219][app/engine/schedule.py:85–103]
   - Returns list of day dicts [app/engine/schedule.py:231–252]

5) Transfer verification: `verify` per edge, `verify_sequence` for Google flow
   - Heuristic ETA default; if Google enabled, call Distance Matrix with caching and 15-min time buckets [app/engine/transfers.py:41–50][app/engine/transfers.py:64–89][app/engine/transfers.py:100–151]

ASCII flow

```
POIs (JSON) → load_pois → basic_candidates → apply_hard_rules → rank → schedule_day(s)
   ↘ transfers.verify (per hop)  ↘ transfers.verify_sequence (Google mode)
→ ItineraryResponse
```

Notes/TODOs: none marked as TODO/FIXME in engine, but see gaps in Section 14.

# 7. Transfers (Google Maps / Fallback)

- API key read via settings; Google client lazily constructed [app/engine/transfers.py:54–62]
- Heuristic fallback function for duration/distance [app/engine/transfers.py:41–50]
- Cache: per-process TTL cache keyed by (from_id, to_id, mode, 15-min bucket) [app/engine/transfers.py:11–16][app/engine/transfers.py:20–37]
- Call caps: per-request counter with `GOOGLE_PER_REQUEST_MAX_CALLS` limit [app/engine/transfers.py:93–99][app/engine/transfers.py:121–129]
- Error handling: on Google failure, fall back to heuristic and mark verify_failed=1 [app/engine/transfers.py:137–143]
- Mapping into transfer items: duration_minutes, distance_km, source, verify_failed [app/engine/transfers.py:100–112][app/engine/schedule.py:166–176]

Example transfer object (heuristic)

```json
{"type":"transfer","from_place_id":"A","to_place_id":"B","mode":"DRIVE","duration_minutes":20,"distance_km":5.0,"source":"heuristic"}
```

# 8. Dataset / Content

- Loader validates uniqueness, numeric duration, and opening_hours presence when duration>0 [app/dataset/loader.py:18–33]
- POIs stored in JSON with fields: poi_id, place_id, name, coords{lat,lng}, tags, themes, price_band, estimated_cost, opening_hours, seasonality, duration_minutes, safety_flags, region [app/dataset/pois.sample.json:1–24][app/dataset/pois.sample.json:25–47]
- Sample count: ~30 POIs (manually counted in file; extend as needed) [app/dataset/pois.sample.json:1–946]
- Missing fields: some consistency differences (coords uses "lng" while engine expects "lon" in distance calc; engine’s radius check gracefully allows when missing coords) [app/engine/candidates.py:60–66][app/engine/candidates.py:63–71]

# 9. Feedback & Re-pack (/v1/itinerary/feedback)

- Supported actions: remove_item, rate_item, request_alternative, edit_time, daily_signal (model) [app/schemas/models.py:213–221]
- Implemented effects: remove_item (filters out place_ids), rate_item<=2 biases avoid_tags for rebuild; request_alternative biases avoid tags if provided [app/api/routes.py:258–268][app/api/routes.py:226–239]
- Repacking: re-run candidates → rules → rank → schedule for a single date [app/api/routes.py:270–279]
- Locks handling: locks converted to fixed items first; preserves locks; returns 409 if locks cannot be preserved [app/engine/schedule.py:120–128][app/api/routes.py:286–299]
- Conflict responses: 409 for overlapping locks and missing locks; 429 for rate limit; 424 optional for Google verification failure [app/api/routes.py:85–87][app/api/routes.py:291–299][app/api/routes.py:245–248][app/api/routes.py:321–326]

# 10. Reranker (Ratings 1–5)

- Dedicated reranker module/endpoint: not present (no separate reranking service found).
- Partial behavior: Ranking function supports weighted features; feedback bias uses ratings to avoid tags but there is no 1–5 reranker model [app/engine/rank.py:141–159][app/api/routes.py:226–239].

# 11. Validation, Errors, and Limits

- Validation rules:
  - Trip max duration ≤ 14 days [app/schemas/models.py:11–21]
  - FeedbackAction type enum [app/schemas/models.py:215–221]
  - DayTemplate pace enum [app/schemas/models.py:31–42]
  - Dataset loader checks: unique poi_id, numeric duration, opening_hours present if duration>0 [app/dataset/loader.py:18–33]
- Error handlers: Pydantic validation to structured 422; generic HTTP errors structured [app/main.py:43–61][app/api/errors.py:6–23]
- Error status usage:
  - 409 lock_conflict, locks_not_preserved [app/api/routes.py:85–87][app/api/routes.py:291–299]
  - 429 rate_limit_exceeded [app/api/routes.py:71–76][app/api/routes.py:243–248]
  - 400 items_per_day_exceeded [app/api/routes.py:163–173]
  - 424 transfer_verification_failed (optional) [app/api/routes.py:141–146][app/api/routes.py:321–326]
- Limits and safeguards:
  - In-memory rate limit per IP [app/api/routes.py:25–43]
  - MAX_ITEMS_PER_DAY cap check [app/api/routes.py:163–173]
  - Google call per-request cap and caching [app/engine/transfers.py:121–129][app/engine/transfers.py:25–37]

# 12. Tests & Coverage

Test files and coverage hints:

- tests/test_itinerary_api.py: healthz, itinerary success, budget constraint, invalid request 422, locks conflict 409, feedback remove/rate bias, items/day limit, feedback preserves locks, notes on heuristic [tests/test_itinerary_api.py:26–82][tests/test_itinerary_api.py:165–176][tests/test_itinerary_api.py:241–265][tests/test_itinerary_api.py:198–239][tests/test_itinerary_api.py:358–382]
- tests/test_engine_core.py: candidate filters (avoid/theme/availability), ranking determinism, schedule respects budget and includes transfers, locks-first packing [tests/test_engine_core.py:9–26][tests/test_engine_core.py:28–45][tests/test_engine_core.py:47–64][tests/test_engine_core.py:66–89][tests/test_engine_core.py:91–107][tests/test_engine_core.py:131–154]
- tests/test_transfers.py: heuristic default/walking, caching, time bucketing, counter reset, Google live (skipped), mode normalization, fallback [tests/test_transfers.py:7–26][tests/test_transfers.py:28–41][tests/test_transfers.py:44–54][tests/test_transfers.py:56–70][tests/test_transfers.py:72–86][tests/test_transfers.py:88–101][tests/test_transfers.py:117–126]

Run tests: `pytest -v` [README.md:118–130]. Overall tests cover endpoints, pipeline core, and transfers (including failure paths and skips for live Google).

# 13. CI/CD & Tooling

- Dockerfile: Python 3.11 slim, installs requirements, runs uvicorn on 8080 with a healthcheck (note: healthcheck uses requests but the base image doesn’t install it system-wide for the healthcheck command) [Dockerfile:1–35]
- pyproject.toml: tooling configs for ruff, black, pytest [pyproject.toml:39–85]
- Requirements and dev tools pinned in requirements.txt [requirements.txt:1–14]
- No GitHub Actions workflow present in repo snapshot despite README mention [README.md:175–181]

# 14. Known Gaps (from code comments)

Scanned for TODO/FIXME/NOTE; explicit tags not found. Implicit notes:

- Currency conversion is a stub with static rates [app/utils/currency.py:8–29]
- DayPlan uses dict for items/summary rather than typed union models [app/schemas/models.py:155–160]
- Google healthcheck in Dockerfile relies on requests in container; consider using curl or uvicorn built-in [Dockerfile:29–34]

# 15. Quick Wins (Next Actions)

- app/schemas/models.py: type `DayPlan.items` as `List[Activity|Transfer]` and `summary` as `Summary`. Update handlers to construct typed models. 1–2 hours.
- app/engine/candidates.py: normalize POI coordinate keys to support `lng` as used in dataset (or adapt loader). 30 mins. [app/engine/candidates.py:63–71][app/dataset/pois.sample.json:6–7]
- app/engine/rules.py: replace simplistic lock duration heuristic with actual overlap check using proposed schedule windows. 1–2 hours.
- app/engine/schedule.py: compute and return walking_km and total walking distance; currently 0.0 placeholder. 45 mins. [app/api/routes.py:204–212]
- app/engine/transfers.py: rename `TRANSFER_MAX_CALLS_PER_REQUEST` usages to match `GOOGLE_PER_REQUEST_MAX_CALLS` consistently and expose both in Settings for clarity. 30 mins. [app/config.py:10][app/engine/transfers.py:121–123]
- app/api/routes.py: make rate limit `RATE_LIMIT_PER_MINUTE` consistent with README (10 vs 50); expose header with remaining quota. 1 hour. [app/api/routes.py:37–43][app/config.py:11]
- Dockerfile: use curl for HEALTHCHECK or install requests explicitly at OS level; verify port matches README (8080). 20 mins. [Dockerfile:29–34]
- scripts/bench.py: add CLI args for iterations and concurrency (async httpx). 1 hour. [scripts/bench.py:15–42]
- clients/node/index.ts: export types for responses; add error detail parsing (structured error). 45 mins.
- tests: add test for MAX_ITEMS_PER_DAY error branch (400) by forcing > cap. 30 mins. [app/api/routes.py:163–173]
- logging: include request_id in error responses headers for correlation. 30 mins. [app/main.py:15–35]
- currency: document and add more currencies; allow decimal rounding control. 30 mins. [app/utils/currency.py:8–41]
- CI: add GitHub Actions workflow to run ruff/black/pytest on pushes/PRs. 45 mins. [pyproject.toml:39–85]
- Security: add simple API key header check middleware. 1 hour.

# 16. Glossary (Beginner-friendly)

- POI (Point of Interest): A place to visit (e.g., temple, beach) with metadata like opening hours and estimated visit duration [app/dataset/pois.sample.json:1–24].
- Locks: Fixed-time activities the user must keep (e.g., lunch 12:00–13:00), placed first in the schedule [app/engine/schedule.py:120–128].
- Candidate generation: Filtering the dataset down to feasible POIs for a day based on preferences, seasons, hours, and radius [app/engine/candidates.py:84–131].
- Rules/Hard filters: Strict constraints like budget caps or transfer duration screens [app/engine/rules.py:23–33].
- Ranking: Scoring remaining POIs using weighted features to pick better matches [app/engine/rank.py:141–159].
- Scheduling/Packing: Placing selected activities into the day timeline around locks and opening hours, inserting transfers and breaks [app/engine/schedule.py:105–128][app/engine/schedule.py:152–176].
- Transfer: Movement between activities with a duration and distance, estimated heuristically or via Google [app/engine/transfers.py:100–151].
- Heuristic: A simple rule-of-thumb method (randomized ranges here) to estimate transfers without external APIs [app/engine/transfers.py:41–50].
- Repack: Rebuild a single day’s plan after feedback, keeping constraints and locks [app/api/routes.py:274–299].

[End of Report]

