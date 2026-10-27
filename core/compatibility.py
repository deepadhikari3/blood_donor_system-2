"""
compatibility.py
------------------
Blood group compatibility rules implemented as O(1) hashmap (dict) lookups.

Two views are provided:
  1. CAN_DONATE_TO   -> given a donor's blood group, which patient groups can
                         receive it.
  2. CAN_RECEIVE_FROM -> given a patient's blood group, which donor groups
                          are compatible (this is the one primarily used by
                          the matching engine, since we start from a request).

Both are derived from a single source of truth so they can never go out of
sync.
"""

# Donor group -> list of patient groups it can donate to
CAN_DONATE_TO = {
    "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],  # universal donor
    "O+":  ["O+", "A+", "B+", "AB+"],
    "A-":  ["A-", "A+", "AB-", "AB+"],
    "A+":  ["A+", "AB+"],
    "B-":  ["B-", "B+", "AB-", "AB+"],
    "B+":  ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"],                                            # can only give to AB+
}


def _build_can_receive_from(donate_map):
    """Invert CAN_DONATE_TO to build the receiver-centric hashmap."""
    receive_map = {bg: [] for bg in donate_map}
    for donor_group, receivers in donate_map.items():
        for receiver_group in receivers:
            receive_map[receiver_group].append(donor_group)
    return receive_map


# Patient group -> list of donor groups it can receive from
CAN_RECEIVE_FROM = _build_can_receive_from(CAN_DONATE_TO)
# Example: CAN_RECEIVE_FROM["AB+"] == ['O-','O+','A-','A+','B-','B+','AB-','AB+']
#          CAN_RECEIVE_FROM["O-"]  == ['O-']   (universal recipient... wait: O- receives only O-)


ALL_BLOOD_GROUPS = list(CAN_DONATE_TO.keys())


def compatible_donor_groups(patient_blood_group: str):
    """Return the list of donor blood groups compatible with a patient.
    O(1) hashmap lookup."""
    return CAN_RECEIVE_FROM.get(patient_blood_group, [])


def compatible_recipient_groups(donor_blood_group: str):
    """Return the list of patient blood groups a donor can give to.
    O(1) hashmap lookup."""
    return CAN_DONATE_TO.get(donor_blood_group, [])


def is_compatible(donor_blood_group: str, patient_blood_group: str) -> bool:
    """O(1) check whether donor_blood_group can donate to patient_blood_group."""
    return patient_blood_group in CAN_DONATE_TO.get(donor_blood_group, [])


if __name__ == "__main__":
    # quick self-test
    for bg in ALL_BLOOD_GROUPS:
        print(f"{bg} can donate to: {CAN_DONATE_TO[bg]}")
    print()
    for bg in ALL_BLOOD_GROUPS:
        print(f"{bg} can receive from: {CAN_RECEIVE_FROM[bg]}")
