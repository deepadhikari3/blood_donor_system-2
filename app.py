"""
app.py
-------
Flask web application - the UI layer of the Blood Donor Matching System.

Model: Donor Directory + Search + Direct Contact
  - Donors register once with full contact + location details.
  - A patient / relative / hospital staff searches by blood group + city
    (optionally locality) and instantly sees a ranked list of matching,
    available donors with phone number & address -- so they can call or
    visit directly. No approval / request queue in between.

Pages:
  /                    Home (quick search bar + live stats)
  /donors/register     Register donor (GET form / POST submit)
  /search              Search donors (GET form / GET results)
  /admin               Admin dashboard (stats, donor list, donation log)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_setup import create_schema, seed_sample_data, DB_PATH
from core import db_manager
from core.db_manager import DuplicatePhoneError, InvalidBloodGroupError
from core.compatibility import ALL_BLOOD_GROUPS, compatible_donor_groups
from core.search_engine import search_donors

app = Flask(__name__)
app.secret_key = "blood-donor-college-project-secret"  # fine for a college demo

CITIES = [
    "Boisar", "Palghar", "Tarapur", "Dahanu", "Vasai", "Virar",
    "Kelva", "Safale", "Umbergaon", "Other",
]

# ------------------------------------------------------------------
# Admin auth
# ------------------------------------------------------------------
# Credentials come from environment variables when set (recommended for
# anything beyond a local demo), and fall back to a default pair so the
# project still runs out of the box. Change these before any real deployment.
#   export ADMIN_USERNAME=youradmin
#   export ADMIN_PASSWORD=yourpassword
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "vortexx"),
    method="pbkdf2:sha256"
)


def login_required(view_func):
    """Redirect to /admin/login if the session isn't marked admin-authenticated.
    Preserves the originally-requested URL so login sends the user back."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def ensure_database():
    if not os.path.exists(DB_PATH):
        create_schema()
        seed_sample_data()
    else:
        create_schema()  # schema.sql uses IF NOT EXISTS, safe to re-run


ensure_database()


# ------------------------------------------------------------------
# Home
# ------------------------------------------------------------------
@app.route("/")
def home():
    stats = db_manager.get_dashboard_stats()
    return render_template("home.html", stats=stats, blood_groups=ALL_BLOOD_GROUPS, cities=CITIES)


# ------------------------------------------------------------------
# Donor registration
# ------------------------------------------------------------------
@app.route("/donors/register", methods=["GET", "POST"])
def register_donor():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        blood_group = request.form.get("blood_group")
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        address = request.form.get("address", "").strip()
        locality = request.form.get("locality", "").strip()
        city = request.form.get("city", "").strip()
        availability = 1 if request.form.get("availability") == "on" else 0
        last_donation_date = request.form.get("last_donation_date") or None
        age = request.form.get("age") or None
        gender = request.form.get("gender") or None

        # QC FIX: re-render the form with whatever the user already typed
        # instead of redirecting, which used to silently discard it all.
        def redisplay(error_message):
            flash(error_message, "error")
            return render_template(
                "register_donor.html",
                blood_groups=ALL_BLOOD_GROUPS,
                cities=CITIES,
                form=request.form,
            )

        if not (name and blood_group and phone and address and locality and city):
            return redisplay(
                "Please fill all required fields (name, blood group, phone, address, locality, city)."
            )

        # QC FIX: server-side validation of blood_group. The <select> in the
        # HTML form already restricts this, but a hand-crafted POST request
        # could previously send any string and crash the whole app with an
        # unhandled sqlite3.IntegrityError (CHECK constraint failure).
        if blood_group not in ALL_BLOOD_GROUPS:
            return redisplay(f"'{blood_group}' is not a valid blood group.")

        try:
            donor_id = db_manager.add_donor(
                name, blood_group, phone, email, address, locality, city,
                availability, last_donation_date, age, gender
            )
        except DuplicatePhoneError:
            # QC FIX: previously an unhandled UNIQUE constraint crash (500).
            return redisplay(
                f"A donor with phone number {phone} is already registered. "
                "If this is you, contact the admin to update your existing record."
            )
        except InvalidBloodGroupError as e:
            return redisplay(str(e))

        flash(f"Thank you {name}! You're registered as a donor and can now be found by people in need.", "success")
        return redirect(url_for("register_donor"))

    return render_template(
        "register_donor.html",
        blood_groups=ALL_BLOOD_GROUPS,
        cities=CITIES,
    )


@app.route("/donors/<int:donor_id>/toggle", methods=["POST"])
@login_required
def toggle_donor_availability(donor_id):
    donor = db_manager.get_donor_by_id(donor_id)
    if donor:
        db_manager.set_donor_availability(donor_id, 0 if donor["availability"] else 1)
    else:
        # QC FIX: previously silently did nothing with no feedback at all.
        flash(f"No donor found with ID {donor_id}.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/donors/<int:donor_id>/mark-donated", methods=["POST"])
@login_required
def mark_donated(donor_id):
    # QC FIX: previously called db_manager unconditionally, which raised an
    # unhandled FOREIGN KEY constraint error (500 crash) for a bad donor_id.
    ok = db_manager.mark_donor_donated(donor_id, notes="Marked via platform")
    if ok:
        flash("Marked as donated. This donor will be hidden from search for the 90-day rest period.", "success")
    else:
        flash(f"No donor found with ID {donor_id}.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/donors/<int:donor_id>/delete", methods=["POST"])
@login_required
def delete_donor(donor_id):
    db_manager.delete_donor(donor_id)
    flash("Donor record removed.", "success")
    return redirect(url_for("admin_dashboard"))


# ------------------------------------------------------------------
# Search donors (the core feature)
# ------------------------------------------------------------------
@app.route("/search", methods=["GET"])
def search():
    blood_group = request.args.get("blood_group", "")
    city = request.args.get("city", "")
    locality = request.args.get("locality", "").strip()

    results = None
    if blood_group and city:
        # QC FIX: a hand-edited URL like ?blood_group=ZZ used to crash the
        # whole request (CHECK constraint failure when logging the search).
        # Now it's validated and shown as a normal flash message instead.
        if blood_group not in ALL_BLOOD_GROUPS:
            flash(f"'{blood_group}' is not a valid blood group.", "error")
            blood_group = ""
        else:
            compatible_groups = compatible_donor_groups(blood_group)
            candidate_donors = db_manager.get_donors_by_groups(compatible_groups)
            results = search_donors(blood_group, city, locality or None, candidate_donors)
            db_manager.log_search(blood_group, city, locality or None, len(results))

    return render_template(
        "search.html",
        blood_groups=ALL_BLOOD_GROUPS,
        cities=CITIES,
        selected_blood_group=blood_group,
        selected_city=city,
        selected_locality=locality,
        results=results,
    )


# ------------------------------------------------------------------
# Admin auth
# ------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    next_url = request.args.get("next") or request.form.get("next") or url_for("admin_dashboard")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["is_admin"] = True
            session["admin_username"] = username
            flash("Logged in as admin.", "success")
            # Only allow redirecting back to an internal path (never an
            # external URL) to avoid an open-redirect via the ?next= param.
            if next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "error")

    return render_template("admin_login.html", next=next_url)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_username", None)
    flash("Logged out.", "success")
    return redirect(url_for("admin_login"))


# ------------------------------------------------------------------
# Admin dashboard
# ------------------------------------------------------------------
@app.route("/admin")
@login_required
def admin_dashboard():
    stats = db_manager.get_dashboard_stats()
    donors = db_manager.get_all_donors()
    history = db_manager.get_donation_history()
    recent_searches = db_manager.get_recent_searches()
    return render_template(
        "admin_dashboard.html",
        stats=stats,
        donors=donors,
        history=history,
        recent_searches=recent_searches,
        admin_username=session.get("admin_username"),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
