"""
search_engine.py
------------------
Core search algorithm for the "Donor Directory + Search + Direct Contact"
model. A patient/hospital/relative searches for a blood group in a city
(and optionally a locality) and gets back a ranked list of donors WITH
their phone number / address so they can be contacted directly and
immediately -- there is no in-between request/approval step.

Pipeline:
  1. HASHMAP LOOKUP   : compatibility.compatible_donor_groups() gives the
                         list of donor blood groups compatible with what
                         the searcher needs, in O(1).
  2. INDEXED FETCH    : donors are pulled from SQLite using the indexed
                         (blood_group, city, locality) columns, then grouped
                         in memory with BloodGroupIndex (hashmap) for O(1)
                         average-case access per compatible group.
  3. FILTERING        : remove donors who are
                            - unavailable (availability = 0)
                            - donated within the last 90 days (medical
                              safety / rest-period rule)
  4. RANKING (SORT)   : multi-key sort (Python Timsort, O(n log n)):
                            1. exact blood-group match with what's needed
                               (highest)
                            2. same locality as searcher
                            3. same city as searcher
                            4. most rested (longest since last donation)
     This puts the donor most likely to be an exact type match, nearby,
     and eligible at the top of the results the searcher will call first.

QC NOTE (2026-09-23): the compatibility hashmap in compatibility.py was
already correct -- every donor this pipeline returns IS medically
compatible (verified against the standard donor/recipient chart). The bug
was in ranking: it previously sorted only by locality/city/recency, so a
donor who is merely *compatible* (e.g. O-) could rank above a donor whose
type is an *exact* match for the patient, even when both are equally
reachable. That's not medically unsafe, but it's poor practice -- real
blood banks conserve O- ("universal donor") for cases where the patient's
type is unknown or no exact match is available, and use an exact match
whenever one exists. Exact-match is now sort key #1: it wins ties between
otherwise-equal candidates, but never overrides the eligibility filters.
"""

from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compatibility import compatible_donor_groups
from core.data_structures import BloodGroupIndex

DONOR_REST_PERIOD_DAYS = 90


def is_donor_eligible(donor, today=None):
    """Available AND (never donated OR last donation >= 90 days ago)."""
    if today is None:
        today = datetime.now()

    if not donor["availability"]:
        return False

    last_date_str = donor["last_donation_date"]
    if not last_date_str:
        return True

    last_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
    days_since = (today - last_date).days
    return days_since >= DONOR_REST_PERIOD_DAYS


def days_since_last_donation(donor, today=None):
    """Large number if donor never donated (treated as 'most rested')."""
    if today is None:
        today = datetime.now()
    last_date_str = donor["last_donation_date"]
    if not last_date_str:
        return float("inf")
    last_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
    return (today - last_date).days


def rank_donors(donors, city, locality=None, patient_blood_group=None, today=None):
    """
    Sort eligible donors by:
      1. Exact blood-group match with what the patient needs -> descending
      2. Same locality as the search (if locality given)       -> descending
      3. Same city as the search                                -> descending
      4. Days since last donation                                -> descending

    Optimized with O(N) pre-decoration to avoid repeated date parsing & string ops
    in O(N log N) sorting comparisons.
    """
    if today is None:
        today = datetime.now()

    target_city = city.strip().lower() if city else ""
    target_locality = locality.strip().lower() if locality else ""

    decorated = []
    for donor in donors:
        exact_match = 1 if (patient_blood_group and donor["blood_group"] == patient_blood_group) else 0

        donor_locality = donor.get("locality", "")
        same_locality = 1 if (target_locality and donor_locality and donor_locality.strip().lower() == target_locality) else 0

        donor_city = donor.get("city", "")
        same_city = 1 if (target_city and donor_city and donor_city.strip().lower() == target_city) else 0

        recency = days_since_last_donation(donor, today)
        recency_score = -recency if recency != float("inf") else float("-inf")

        sort_key = (-exact_match, -same_locality, -same_city, recency_score)
        decorated.append((sort_key, donor))

    decorated.sort(key=lambda x: x[0])
    return [donor for _, donor in decorated]


def search_donors(blood_group_needed, city, locality=None, all_donors=None, today=None):
    """
    Main search function used by the /search route.

    blood_group_needed : e.g. "A+"  (the patient's blood group / what is
                          needed -- we look up which donor groups are
                          compatible with it)
    city, locality      : searcher's location, used for ranking (not a hard
                          filter -- a donor from another city is still
                          shown, just ranked lower, since blood is more
                          important than distance in a genuine emergency)
    all_donors           : list of donor rows fetched from the DB
                          (dict or sqlite3.Row)

    Returns: ranked_donors (list of dicts), each donor keeps ALL its DB
             fields (name, phone, address, locality, city, blood_group,
             last_donation_date, ...) so the UI can render a "Call Now"
             / "View Address" action directly, and can show whether it's
             an exact type match or a compatible substitute.
    """
    if today is None:
        today = datetime.now()
    if all_donors is None:
        all_donors = []

    # Step 1: hashmap lookup for compatible donor blood groups
    compatible_groups = compatible_donor_groups(blood_group_needed)

    # Step 2: hashmap-indexed fetch of only the compatible groups
    index = BloodGroupIndex(all_donors)
    candidates = index.get_by_groups(compatible_groups)

    # Step 3: eligibility filtering
    eligible = [d for d in candidates if is_donor_eligible(d, today)]

    # Step 4: ranking -- exact match first, then locality, city, rest period
    ranked = rank_donors(eligible, city, locality, blood_group_needed, today)

    return ranked


if __name__ == "__main__":
    sample_donors = [
        {"donor_id": 1, "name": "A", "blood_group": "O-", "city": "Mumbai",
         "locality": "Andheri East", "availability": 1, "last_donation_date": None},
        {"donor_id": 2, "name": "B", "blood_group": "O-", "city": "Pune",
         "locality": "Kothrud", "availability": 1, "last_donation_date": "2024-01-01"},
        {"donor_id": 3, "name": "C", "blood_group": "A+", "city": "Mumbai",
         "locality": "Bandra West", "availability": 1, "last_donation_date": None},
    ]
    results = search_donors("A+", "Mumbai", "Andheri East", sample_donors)
    print("Search results for A+ needed, Mumbai / Andheri East:")
    for d in results:
        print(" ", d["name"], d["blood_group"], d["locality"], d["city"])
    # Donor C (exact A+ match, but different locality/city from the search)
    # should now rank ABOVE Donor A (same locality but only compatible O-).
    assert results[0]["name"] == "C", "exact-match donor should rank first"
    print("\n[PASS] Exact blood-group match correctly ranked above locality-only match.")
