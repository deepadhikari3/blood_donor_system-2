-- ============================================================
-- Blood Donor Matching System - Database Schema (v2)
-- Model: Donor Directory + Search + Direct Contact
-- Engine : SQLite (easily portable to MySQL / PostgreSQL)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Table: donors
-- The core table. Anyone willing to donate registers here with
-- full contact + location details so a searcher can reach them
-- directly (call / WhatsApp) during an emergency.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donors (
    donor_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    blood_group         TEXT NOT NULL CHECK (blood_group IN
                          ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    phone               TEXT NOT NULL UNIQUE,
    email               TEXT,
    address             TEXT NOT NULL,       -- full street address / landmark
    locality            TEXT NOT NULL,       -- area / neighbourhood (e.g. "Andheri East")
    city                TEXT NOT NULL,
    availability        INTEGER NOT NULL DEFAULT 1,   -- 1 = available, 0 = not available
    last_donation_date  TEXT,                          -- NULL if never donated
    age                 INTEGER,
    gender              TEXT,
    registered_on       TEXT DEFAULT (datetime('now'))
);

-- Index for fast lookup by blood group (heavily used in search)
CREATE INDEX IF NOT EXISTS idx_donor_blood_group ON donors(blood_group);
-- Composite index: blood group + city, used for city-filtered search
CREATE INDEX IF NOT EXISTS idx_donor_group_city ON donors(blood_group, city);
-- Composite index: blood group + city + locality, used for locality-ranked search
CREATE INDEX IF NOT EXISTS idx_donor_group_city_locality ON donors(blood_group, city, locality);
-- Index for availability filter
CREATE INDEX IF NOT EXISTS idx_donor_availability ON donors(availability);

-- ------------------------------------------------------------
-- Table: search_log
-- Every search a patient/hospital performs is logged (blood group
-- needed, city, timestamp). Used for the Admin Dashboard to show
-- real demand patterns. No personal identity of the searcher is
-- required to use the platform (contact is direct, donor to
-- seeker), so this table stores only the search parameters.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_log (
    search_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_group     TEXT NOT NULL CHECK (blood_group IN
                      ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    city            TEXT NOT NULL,
    locality        TEXT,
    results_found   INTEGER NOT NULL DEFAULT 0,
    searched_on     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_search_log_group ON search_log(blood_group);

-- ------------------------------------------------------------
-- Table: donation_history
-- Optional record kept when a donor is marked as "donated" (e.g.
-- by the donor themselves, or an admin), so the 90-day
-- rest-period rule can be enforced and last_donation_date stays
-- accurate.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donation_history (
    donation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id        INTEGER NOT NULL,
    donation_date   TEXT DEFAULT (datetime('now')),
    notes           TEXT,
    FOREIGN KEY (donor_id) REFERENCES donors(donor_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_donor ON donation_history(donor_id);
