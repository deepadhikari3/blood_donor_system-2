# Project Progress Log — Blood Donor Matching System (v2)

**Model:** Donor Directory + Search + Direct Contact
Donors register once with contact & location details. A person in need
searches by blood group + city and instantly sees a ranked list of
compatible, available donors with phone numbers to call directly —
no request/approval step in between.

| # | Module | Status | Notes |
|---|--------|--------|-------|
| 1 | Database Design | ✅ Done | `donors` (with address/locality/city), `search_log`, `donation_history`. PKs, FKs, and indexes on blood_group, (blood_group, city), (blood_group, city, locality), availability. |
| 2 | Donor Registration | ✅ Done | Web form + `db_manager.add_donor()`. Captures name, blood_group, phone, email, address, locality, city, availability, age, gender, last_donation_date. |
| 3 | Blood Compatibility Logic | ✅ Done | `core/compatibility.py` — dict-based O(1) lookup, self-tested. |
| 4 | Search Engine (replaces request/queue model) | ✅ Done | `core/search_engine.py` — hashmap compatibility lookup → BloodGroupIndex filter → 90-day/availability filter → multi-key sort (locality, city, recency). |
| 5 | Search Optimization | ✅ Done | SQL indexes (`idx_donor_blood_group`, `idx_donor_group_city`, `idx_donor_group_city_locality`) + in-memory `BloodGroupIndex` hashmap (`core/data_structures.py`). |
| 6 | Direct Contact | ✅ Done | Search results render `tel:` and `mailto:` links so the seeker can call/email the donor immediately — no in-app messaging/approval layer. |
| 7 | User Interface | ✅ Done | Flask + Jinja2 templates: Home (quick search bar), Become a Donor, Find a Donor (search + results), Admin Dashboard. |
| 8 | Testing | ✅ Done | Unit self-tests in each core module (`__main__` blocks) + Flask test-client smoke tests for all routes and a full register → search → mark-donated → re-search (90-day exclusion) → delete flow. |

## Test Log

- `core/compatibility.py` — self-test run, all 8 blood groups verified against standard donor/recipient compatibility chart. PASS.
- `core/data_structures.py` — `BloodGroupIndex` self-test, O(1) group lookup and multi-group O(k) lookup verified. PASS.
- `core/search_engine.py` — self-test with synthetic donors: same-locality donor ranked above same-city donor, which ranked above different-city donor. PASS.
- Flask routes (`/`, `/donors/register`, `/search`, `/admin`) — all return HTTP 200. PASS.
- End-to-end flow (register donor → appears in search with Call button → admin toggles/marks donated → donor correctly disappears from search under the 90-day rest rule → admin deletes donor) — verified via Flask test client, all assertions passed. PASS.

## Design Decision: Why No Request/Queue Layer

The original design routed emergency requests through a priority queue and
a "confirm match" step. Based on how the platform is actually meant to be
used — patients/relatives need to reach a donor **immediately** — this was
replaced with a direct **search → call** flow:
- Removes a point of delay (no waiting for someone to process a request).
- Still uses standard data structures (hashmap indexing, multi-key sorting)
  for the "search optimization + ranking" requirement.
- `search_log` table still records every search for admin analytics, so
  demand patterns (which blood group / city is searched most) remain
  visible without slowing down the seeker.

## Known Limitations / Future Work

- SQLite used for simplicity/portability; schema is close to ANSI SQL and
  can be migrated to MySQL/PostgreSQL with minor syntax tweaks
  (AUTOINCREMENT → AUTO_INCREMENT/SERIAL).
- No authentication/login system (out of scope for this project scope; a
  donor's own record can currently be edited only via the Admin Dashboard).
- Phone numbers are shown in plain text for direct calling — in a
  production system you'd typically add rate-limiting or masked-calling to
  prevent misuse; noted here as a possible extension, not implemented.
- Single-process demo server (`app.run(debug=True)`) — fine for a project
  demo/viva, not meant for production deployment.
