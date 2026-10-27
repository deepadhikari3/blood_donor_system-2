"""
db_manager.py
--------------
Thin data-access layer between the Flask UI and SQLite.
Keeps all raw SQL in one place (separation of concerns).
"""

import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_setup import get_connection


class DuplicatePhoneError(Exception):
    """Raised when a donor is registered with a phone number already on file."""
    pass


class InvalidBloodGroupError(Exception):
    """Raised when a blood_group value fails the DB's CHECK constraint."""
    pass


# ---------------------- Donors ----------------------
def add_donor(name, blood_group, phone, email, address, locality, city,
              availability, last_donation_date, age, gender):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO donors
               (name, blood_group, phone, email, address, locality, city,
                availability, last_donation_date, age, gender)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (name, blood_group, phone, email, address, locality, city,
             availability, last_donation_date or None, age, gender),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        msg = str(e)
        if "donors.phone" in msg:
            raise DuplicatePhoneError(
                f"A donor with phone number {phone} is already registered."
            ) from e
        if "blood_group" in msg:
            raise InvalidBloodGroupError(
                f"'{blood_group}' is not a valid blood group."
            ) from e
        raise
    finally:
        conn.close()


def get_all_donors():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM donors ORDER BY donor_id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_donors_by_groups(blood_groups):
    """Fetch available donors belonging ONLY to specific blood groups via SQL index.
    O(k) DB lookup instead of full table scan."""
    if not blood_groups:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in blood_groups)
    query = f"SELECT * FROM donors WHERE availability = 1 AND blood_group IN ({placeholders}) ORDER BY donor_id DESC"
    rows = conn.execute(query, tuple(blood_groups)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_donor_by_id(donor_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM donors WHERE donor_id = ?", (donor_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_donor_availability(donor_id, availability):
    """Returns True if a donor row was updated, False if donor_id doesn't exist."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE donors SET availability = ? WHERE donor_id = ?",
        (availability, donor_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def mark_donor_donated(donor_id, notes=None):
    """Record a donation and refresh last_donation_date (used for the
    90-day rest-period rule). Returns True if the donor existed and was
    updated, False if donor_id doesn't exist (instead of the old behaviour
    of raising an unhandled FOREIGN KEY error)."""
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM donors WHERE donor_id = ?", (donor_id,)
        ).fetchone()
        if not exists:
            return False
        conn.execute(
            "INSERT INTO donation_history (donor_id, notes) VALUES (?, ?)",
            (donor_id, notes),
        )
        conn.execute(
            "UPDATE donors SET last_donation_date = date('now') WHERE donor_id = ?",
            (donor_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_donor(donor_id):
    conn = get_connection()
    conn.execute("DELETE FROM donors WHERE donor_id = ?", (donor_id,))
    conn.commit()
    conn.close()


# ---------------------- Search log ----------------------
def log_search(blood_group, city, locality, results_found):
    """Swallow an IntegrityError from a bad blood_group instead of crashing
    the whole request -- search.html should still render its 'invalid
    blood group' message regardless of whether the demand-analytics log
    entry could be written."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO search_log (blood_group, city, locality, results_found)
               VALUES (?,?,?,?)""",
            (blood_group, city, locality, results_found),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def get_recent_searches(limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM search_log ORDER BY searched_on DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------- Donation history ----------------------
def get_donation_history():
    conn = get_connection()
    rows = conn.execute(
        """SELECT dh.*, d.name AS donor_name, d.blood_group
           FROM donation_history dh
           LEFT JOIN donors d ON dh.donor_id = d.donor_id
           ORDER BY dh.donation_date DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------- Dashboard stats ----------------------
def get_dashboard_stats():
    conn = get_connection()
    stats = {}
    stats["total_donors"] = conn.execute("SELECT COUNT(*) c FROM donors").fetchone()["c"]
    stats["available_donors"] = conn.execute(
        "SELECT COUNT(*) c FROM donors WHERE availability = 1"
    ).fetchone()["c"]
    stats["total_searches"] = conn.execute("SELECT COUNT(*) c FROM search_log").fetchone()["c"]
    stats["total_donations"] = conn.execute(
        "SELECT COUNT(*) c FROM donation_history"
    ).fetchone()["c"]

    rows = conn.execute(
        "SELECT blood_group, COUNT(*) c FROM donors GROUP BY blood_group"
    ).fetchall()
    stats["donors_by_group"] = {r["blood_group"]: r["c"] for r in rows}

    rows = conn.execute(
        "SELECT city, COUNT(*) c FROM donors GROUP BY city ORDER BY c DESC"
    ).fetchall()
    stats["donors_by_city"] = {r["city"]: r["c"] for r in rows}
    conn.close()
    return stats
