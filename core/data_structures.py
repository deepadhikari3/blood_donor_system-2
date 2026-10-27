"""
data_structures.py
--------------------
Standard data-structure implementation used for fast donor search.

BloodGroupIndex
  An in-memory HASHMAP: {blood_group: [donor rows]}. Built once per search
  request from the DB result set. Gives O(1) average-time lookup of "all
  donors with blood group X" instead of scanning the full donor list in a
  Python loop, and lets us fetch several compatible groups in one pass
  (O(k) for k compatible groups, not O(n) over all donors).

This is the core data-structure optimisation module (Module 6: Search
Optimization) referenced by core/search_engine.py.
"""


class BloodGroupIndex:
    """Builds {blood_group: [donor dict, ...]} from a flat list of donors."""

    def __init__(self, donors):
        self._index = {}
        self.build(donors)

    def build(self, donors):
        self._index.clear()
        for donor in donors:
            bg = donor["blood_group"]
            self._index.setdefault(bg, []).append(donor)

    def get_by_group(self, blood_group):
        """O(1) average lookup."""
        return self._index.get(blood_group, [])

    def get_by_groups(self, blood_groups):
        """O(k) lookup across k compatible blood groups."""
        result = []
        for bg in blood_groups:
            result.extend(self._index.get(bg, []))
        return result

    def all_groups(self):
        return list(self._index.keys())


if __name__ == "__main__":
    sample = [
        {"donor_id": 1, "blood_group": "O+"},
        {"donor_id": 2, "blood_group": "O-"},
        {"donor_id": 3, "blood_group": "O+"},
    ]
    idx = BloodGroupIndex(sample)
    print("O+ donors:", idx.get_by_group("O+"))
    print("O+/O- donors:", idx.get_by_groups(["O+", "O-"]))
