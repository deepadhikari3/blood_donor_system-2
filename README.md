# Blood Donor Matching System — Palghar & Boisar Region

A B.Tech IT (Sem 3) capstone project connecting blood donors with people in
need across the **Palghar–Boisar region, Maharashtra** — pure **Python +
SQLite (DBMS) + standard data structures**. No AI/ML/NLP/cloud services
used anywhere.

## How It Works
1. **Donors register once** with their name, blood group, phone, address,
   locality, and city.
2. **Anyone in need searches** by blood group + city (and optionally
   locality/area).
3. The platform instantly shows a **ranked list of matching, available
   donors with phone numbers** — the seeker calls the donor directly. No
   request, no approval step, no waiting.

## Tech Stack
- **Backend:** Python 3 (Flask for the web layer)
- **Database:** SQLite (file-based DBMS, `database/blood_donor.db`), schema in `database/schema.sql`
- **Data Structures:** hashmap (`dict`) for blood-group indexing, Timsort (`sorted()`) for multi-key ranking

## Project Structure
```
blood_donor_system/
├── app.py                     # Flask web app (all routes/pages)
├── requirements.txt
├── progress.md                 # module-by-module progress + test log
├── database/
│   ├── schema.sql              # DDL: tables, PKs, FKs, indexes
│   └── db_setup.py             # creates DB + seeds sample data (Palghar/Boisar)
├── core/
│   ├── compatibility.py        # blood group compatibility hashmap
│   ├── data_structures.py      # BloodGroupIndex hashmap
│   ├── search_engine.py        # search + ranking algorithm (the core feature)
│   └── db_manager.py           # all SQL queries (data access layer)
├── templates/                  # Jinja2 HTML pages
└── static/style.css
```

## How to Run
```bash
cd blood_donor_system
python3 -m venv venv && source venv/bin/activate   # recommended
pip install -r requirements.txt
python3 app.py
```
Then open **http://127.0.0.1:5001** in your browser.

### Admin Login
The Admin Dashboard now requires login. Default credentials (change these
before any real deployment):
- **Username:** `admin`
- **Password:** `changeme123`

To use your own credentials instead of the defaults, set environment
variables before running the app:
```bash
export ADMIN_USERNAME=youradmin
export ADMIN_PASSWORD=yourstrongpassword
python3 app.py
```
The database and sample data (10 donors across Boisar, Palghar, Tarapur,
Dahanu, Virar) are created automatically on first run.

## Algorithms — How Search & Matching Works

### 1. Blood Compatibility (Hashmap, O(1))
`core/compatibility.py` defines `CAN_DONATE_TO` — a dict mapping each donor
blood group to the list of patient groups it can safely donate to (e.g.
`O-` → all 8 groups, `AB+` → only `AB+`). The reverse map
`CAN_RECEIVE_FROM` is derived automatically by inverting it, so when a
seeker searches for "A+ needed", the compatible donor groups
(`O-, O+, A-, A+`) are looked up in O(1).

### 2. Search Optimization (Hashmap Index)
`core/data_structures.py` → `BloodGroupIndex` builds an in-memory
`{blood_group: [donor rows]}` dict from the DB result set once per search,
giving O(1) average-time access per compatible blood group instead of
scanning every donor row in a Python loop. This is on top of SQL-level
B-Tree indexes (`idx_donor_blood_group`, `idx_donor_group_city`,
`idx_donor_group_city_locality`) that keep the initial database read fast.

### 3. Search & Ranking Pipeline
`core/search_engine.search_donors()`:
1. **Hashmap lookup** — get compatible donor blood groups for what's needed (O(1)).
2. **Indexed fetch** — pull only donors of the compatible groups via `BloodGroupIndex` (O(k) for k groups).
3. **Filtering** — remove donors who are `availability = 0` or who donated
   within the last **90 days** (medical safety rest-period rule).
4. **Ranking (multi-key sort, Timsort O(n log n))** — remaining donors are
   sorted by: (1) same locality as the searcher, (2) same city, (3) days
   since last donation (a donor who never donated, or donated longest ago,
   is "most rested" and ranked higher).
5. **Direct contact** — each result carries the donor's phone number and
   address, rendered as a `tel:` link so the seeker can call with one tap.

## Database Schema Summary
| Table | Purpose | Key Relationships |
|---|---|---|
| `donors` | Donor profiles: contact + location + availability | indexed on blood_group, city, locality |
| `search_log` | Every search performed (for admin demand analytics) | — |
| `donation_history` | Records when a donor is marked "donated" | FK → donors |

Full DDL with `PRIMARY KEY`, `FOREIGN KEY`, `CHECK` constraints and indexes
is in `database/schema.sql`.

## Pages
- **Home** — quick search bar (blood group + city + locality) + live stats
- **Become a Donor** — registration form (name, blood group, phone, address, locality, city, availability, etc.)
- **Find a Donor** — search form + ranked results with **Call Now** buttons
- **Admin Dashboard** — donor list (toggle availability / mark donated / delete), recent searches, donation history

## Testing
Every core module (`compatibility.py`, `data_structures.py`,
`search_engine.py`) includes a `__main__` self-test block — run any of
them directly, e.g. `python3 core/search_engine.py`. See `progress.md`
for the full test log, including Flask route smoke tests and an
end-to-end register → search → mark-donated → 90-day-exclusion → delete
test.
