CANONICAL_STATES_UTS = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

_CANONICAL_BY_KEY = {
    " ".join(name.lower().split()): name for name in CANONICAL_STATES_UTS
}

# Common historical names, abbreviations and typing variants.
_STATE_ALIASES = {
    "orissa": "Odisha",
    "odhisa": "Odisha",
    "odisa": "Odisha",
    "uttaranchal": "Uttarakhand",
    "pondicherry": "Puducherry",
    "nct of delhi": "Delhi",
    "new delhi": "Delhi",
    "jammu & kashmir": "Jammu and Kashmir",
    "jammu and kashmir union territory": "Jammu and Kashmir",
    "dadra & nagar haveli and daman & diu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra and nagar haveli & daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
}


def _clean(value):
    if value is None:
        return None
    value = " ".join(str(value).strip().split())
    return value or None


def normalize_state(value):
    value = _clean(value)
    if not value:
        return None

    key = value.lower()
    if key in _STATE_ALIASES:
        return _STATE_ALIASES[key]
    if key in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[key]

    # Keep unexpected legacy data readable instead of silently discarding it.
    return value.title()


def normalize_district(value):
    value = _clean(value)
    if not value:
        return None
    return value.title()


def normalize_location(state, district):
    return normalize_state(state), normalize_district(district)
