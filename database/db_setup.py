"""
db_setup.py
------------
Creates the SQLite database from schema.sql and seeds it with sample
donors (with realistic address/locality/city) so the search + direct
contact flow can be demoed immediately.

Run:  python3 database/db_setup.py
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB_PATH = os.path.join(BASE_DIR, "blood_donor.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# On Vercel or read-only serverless environment, use writable /tmp directory
if os.environ.get("VERCEL") or not os.access(BASE_DIR, os.W_OK):
    DB_PATH = "/tmp/blood_donor.db"
    if not os.path.exists(DB_PATH) and os.path.exists(LOCAL_DB_PATH):
        try:
            shutil.copyfile(LOCAL_DB_PATH, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = LOCAL_DB_PATH


def get_connection():
    """Return a sqlite3 connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn



def create_schema():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[OK] Schema created at {DB_PATH}")


def seed_sample_data():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM donors")
    if cur.fetchone()["c"] > 0:
        print("[SKIP] Sample data already present.")
        conn.close()
        return

    today = datetime.now()
    # (name, blood_group, phone, email, address, locality, city,
    #  availability, last_donation_date, age, gender)
    # Sample donors localized to the Palghar - Boisar region (Maharashtra)
    donors = [
        ("Rahul Sharma", "O+", "9800000001", "rahul@example.com",
         "12 Sai Nagar, Near Boisar Railway Station", "Boisar East", "Boisar",
         1, (today - timedelta(days=120)).strftime("%Y-%m-%d"), 28, "M"),
        ("Anita Verma", "O-", "9800000002", "anita@example.com",
         "45 Tarapur MIDC Road, 3rd Floor", "Tarapur MIDC", "Boisar",
         1, None, 25, "F"),
        ("Vikram Singh", "A+", "9800000003", "vikram@example.com",
         "7 Station Road, Opp. Palghar Court", "Palghar East", "Palghar",
         1, (today - timedelta(days=10)).strftime("%Y-%m-%d"), 32, "M"),
        ("Priya Nair", "A-", "9800000004", "priya@example.com",
         "22 Kaman Road", "Kaman", "Palghar",
         1, None, 27, "F"),
        ("Suresh Iyer", "B+", "9800000005", None,
         "9 Chinchani Road", "Chinchani", "Boisar",
         0, None, 40, "M"),
        ("Meena Joshi", "B-", "9800000006", "meena@example.com",
         "3 Dahanu Road, Near Bus Depot", "Dahanu Road", "Dahanu",
         1, (today - timedelta(days=200)).strftime("%Y-%m-%d"), 30, "F"),
        ("Arjun Rao", "AB+", "9800000007", None,
         "18 Boisar West, Near IIT-Boisar Gate", "Boisar West", "Boisar",
         1, None, 24, "M"),
        ("Kavita Menon", "AB-", "9800000008", "kavita@example.com",
         "5 Virar West, Agashi Road", "Agashi Road", "Virar",
         1, (today - timedelta(days=45)).strftime("%Y-%m-%d"), 29, "F"),
        ("Deepak Kulkarni", "O+", "9800000009", None,
         "31 Palghar West, Manor Road", "Palghar West", "Palghar",
         1, None, 35, "M"),
        ("Sneha Patil", "O+", "9800000010", "sneha@example.com",
         "14 Boisar East, Navapur Naka", "Navapur Naka", "Boisar",
         1, (today - timedelta(days=95)).strftime("%Y-%m-%d"), 26, "F"),
    ]
    cur.executemany(
        """INSERT INTO donors
           (name, blood_group, phone, email, address, locality, city,
            availability, last_donation_date, age, gender)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        donors,
    )

    conn.commit()
    conn.close()
    print("[OK] Sample data seeded (10 donors across Palghar-Boisar region).")


if __name__ == "__main__":
    create_schema()
    seed_sample_data()
