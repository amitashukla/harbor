import csv


# Profile field → (csv_column, weight)
FIELD_MAP = [
    ("clinical",      "primary_focus",      "primary_focus",       3),
    ("clinical",      "substances",         "substances",          3),
    ("demographics",  "population",         "age_groups",          2),
    ("demographics",  "identity_factors",   "identity_factors",    2),
    ("logistics",     "insurance",          "insurance",           2),
    ("preferences",   "setting",            "settings",            2),
    ("preferences",   "therapy_approach",   "therapy_approaches",  1),
    ("demographics",  "language",           "languages",           1),
]


def load_resources(csv_path):
    """Load one or more resource CSVs into a list of dicts.

    Accepts a single path (str) or a list of paths. Called once at init.
    """
    if isinstance(csv_path, str):
        csv_path = [csv_path]
    rows = []
    for path in csv_path:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows.extend(reader)
    return rows


def _get_profile_value(profile, category, field):
    """Safely get a profile value, returning None for missing/empty."""
    val = profile.get(category, {}).get(field)
    if val is None:
        return None
    if isinstance(val, list) and len(val) == 0:
        return None
    return val


def _pipe_values(cell):
    """Split a pipe-delimited CSV cell into a set of lowercase values."""
    if not cell or not cell.strip():
        return set()
    return {v.strip().lower() for v in cell.split("|")}


def filter_resources(resources, user_profile):
    """
    Filter the full resource list down to a relevant subset based on
    user profile values. Applies geographic, primary_focus, and substances
    filters. Progressively relaxes filters if fewer than 3 results remain.
    """
    zipcode = _get_profile_value(user_profile, "logistics", "zipcode")
    region = _get_profile_value(user_profile, "logistics", "region")
    primary_focus = _get_profile_value(user_profile, "clinical", "primary_focus")
    substances = _get_profile_value(user_profile, "clinical", "substances")

    # No profile info → no filtering possible, return empty (no recommendations)
    if not zipcode and not region and not primary_focus and not substances:
        return []

    # Build filter functions in order of relaxation priority
    filters = []

    # Geographic filter (relaxed first if too few results)
    if zipcode:
        zip_prefix = zipcode[:3]
        filters.append(("geo", lambda r, zp=zip_prefix: (
            r.get("zip", "")[:3] == zp
        )))
    elif region:
        region_lower = region.lower()
        filters.append(("geo", lambda r, rl=region_lower: (
            rl in r.get("city", "").lower() or rl in r.get("state", "").lower()
        )))

    # Primary focus filter
    if primary_focus:
        focus_lower = primary_focus.lower()
        filters.append(("focus", lambda r, fl=focus_lower: (
            not r.get("primary_focus", "").strip() or
            fl in _pipe_values(r.get("primary_focus", ""))
        )))

    # Substances filter
    if substances:
        if isinstance(substances, str):
            substances = [substances]
        subs_lower = {s.lower() for s in substances}
        filters.append(("substances", lambda r, sl=subs_lower: (
            not r.get("substances", "").strip() or
            bool(sl & _pipe_values(r.get("substances", "")))
        )))

    # Apply all filters, progressively relax if < 3 results
    result = _apply_filters(resources, filters)
    if len(result) >= 3:
        return result
    best = result  # keep the best partial matches found so far

    # Relax geographic filter first
    relaxed = [f for f in filters if f[0] != "geo"]
    if relaxed:
        result = _apply_filters(resources, relaxed)
        if len(result) >= 3:
            return result
        if len(result) > len(best):
            best = result

    # Relax substances filter next
    relaxed = [f for f in relaxed if f[0] != "substances"]
    if relaxed:
        result = _apply_filters(resources, relaxed)
        if len(result) > len(best):
            best = result

    return best


def _apply_filters(resources, filters):
    """Apply a list of filter functions, keeping rows that pass all."""
    if not filters:
        return []
    result = []
    for row in resources:
        if all(fn(row) for _, fn in filters):
            result.append(row)
    return result


def score_resources(filtered, user_profile, top_n=3):
    """
    Score filtered resources by relevance to the user profile.
    Returns the top_n highest-scoring resources as a list of dicts.
    """
    zipcode = _get_profile_value(user_profile, "logistics", "zipcode")
    region = _get_profile_value(user_profile, "logistics", "region")

    scored = []
    for row in filtered:
        score = 0

        # Score each mapped field
        for category, field, csv_col, weight in FIELD_MAP:
            profile_val = _get_profile_value(user_profile, category, field)
            if profile_val is None:
                continue

            cell_values = _pipe_values(row.get(csv_col, ""))
            if not cell_values:
                continue  # empty cell = neutral

            if isinstance(profile_val, list):
                matches = sum(1 for v in profile_val if v.lower() in cell_values)
                if matches > 0:
                    score += weight * (matches / len(profile_val))
            else:
                if profile_val.lower() in cell_values:
                    score += weight

        # Geographic bonus
        row_zip = row.get("zip", "").strip()
        if zipcode and row_zip:
            if row_zip == zipcode:
                score += 5
            elif row_zip[:3] == zipcode[:3]:
                score += 2
        elif region and not zipcode:
            region_lower = region.lower()
            if region_lower in row.get("city", "").lower():
                score += 3

        if score > 0:
            scored.append((score, row))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:top_n]]


def format_recommendations(results):
    """
    Format a list of resource dicts into a readable recommendation block.
    Returns empty string if no results.
    """
    if not results:
        return ""

    lines = [
        "---",
        "Here are some resources that may be a good fit for you:",
        "",
    ]

    for i, row in enumerate(results, 1):
        name = row.get("name", "Unknown Facility")
        lines.append(f"{i}. {name}")

        # Address
        parts = [row.get("address", ""), row.get("city", ""),
                 row.get("state", ""), row.get("zip", "")]
        address = ", ".join(p.strip() for p in parts if p.strip())
        if address:
            lines.append(f"   {address}")

        # Phone
        phone = row.get("phone", "").strip()
        if phone:
            lines.append(f"   Phone: {phone}")

        # Website
        website = row.get("website", "").strip()
        if website:
            lines.append(f"   Website: {website}")

        # Summary line: focus, substances, settings
        details = []
        focus = row.get("primary_focus", "").strip()
        if focus:
            details.append("Focus: " + ", ".join(
                v.strip().replace("_", " ").title() for v in focus.split("|")
            ))
        subs = row.get("substances", "").strip()
        if subs:
            details.append("Substances: " + ", ".join(
                v.strip().replace("_", " ").title() for v in subs.split("|")
            ))
        settings = row.get("settings", "").strip()
        if settings:
            details.append("Settings: " + ", ".join(
                v.strip().replace("_", " ").title() for v in settings.split("|")
            ))
        if details:
            lines.append("   " + " | ".join(details))

        lines.append("")

    return "\n".join(lines).rstrip()
