"""
Normalize treatment facility data into a unified CSV that can be filtered
against the user profile schema.

Data sources:
  1. findtreatment.gov/findtreatment_facilities.csv  (national, ~96K rows)
  2. resources/*.pdf  (Boston metro area — requires manual CSV extraction)

Output:
  normalized_resources.csv — one row per facility, with columns aligned to
  the user profile schema for filtering in get_response().

Usage:
    python normalize_resources.py
"""

import ast
import csv
import os
import re

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINDTREATMENT_CSV = os.path.join(SCRIPT_DIR, "findtreatment.gov", "findtreatment_facilities.csv")
BOSTON_CSV = os.path.join(SCRIPT_DIR, "resources", "boston_resources.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "normalized_resources.csv")

# ---------------------------------------------------------------------------
# Mapping tables: findtreatment.gov service strings → profile schema values
# ---------------------------------------------------------------------------

# Maps f2 service codes to the profile-aligned column they populate
SERVICE_CODE_TO_COLUMN = {
    "TC":  "type_of_care",
    "SET": "service_setting",
    "PAY": "insurance",
    "SG":  "special_programs",
    "AGE": "age_groups",
    "TAP": "treatment_approaches",
    "SN":  "sex_accepted",
    "OM":  "opioid_medications",
    "OT":  "opioid_treatment",
    "PHR": "pharmacotherapies",
    "AS":  "ancillary_services",
}

# --- age_groups → profile.demographics.population ---
AGE_MAP = {
    "children/adolescents": "adolescent",
    "young adults":         "young_adult",
    "adults":               "adult",
    "seniors":              "older_adult",  # some facilities list this
}

# --- special_programs → profile.demographics.identity_factors ---
IDENTITY_MAP = {
    "veterans":                         "veteran",
    "lgbtq":                            "lgbtq",  # not literally in data but kept for future
    "lesbian, gay, bisexual, transgender": "lgbtq",
    "persons with hearing impairments": "accessibility",
    "persons in recovery":              None,  # not an identity factor
    "adult women":                      "woman",
    "pregnant/postpartum women":        "woman",
    "homeless":                         "homeless",
    "persons experiencing homelessness": "homeless",
}

# --- insurance/payment → profile.logistics.insurance ---
INSURANCE_MAP = {
    "medicaid":                             "medicaid_medicare",
    "medicare":                             "medicaid_medicare",
    "private health insurance":             "private",
    "cash or self-payment":                 "uninsured",
    "sliding fee scale":                    "uninsured",
    "payment assistance":                   "uninsured",
    "federal military insurance":           "va_tricare",
    "ihs/tribal/urban (itu) funds":         None,
}

# --- service_setting → profile.preferences.setting ---
SETTING_MAP = {
    "outpatient":                           "outpatient",
    "regular outpatient treatment":         "outpatient",
    "intensive outpatient treatment":       "intensive_outpatient",
    "partial hospitalization/day treatment": "intensive_outpatient",
    "residential/24-hour residential":      "residential",
    "long-term residential":                "residential",
    "short-term residential":               "residential",
    "residential detoxification":           "residential",
    "hospital inpatient":                   "residential",
    "telemedicine/telehealth therapy":      "telehealth",
    "outpatient methadone/buprenorphine or naltrexone treatment": "outpatient",
}

# --- treatment_approaches → profile.preferences.therapy_approach ---
THERAPY_MAP = {
    "cognitive behavioral therapy":     "cbt",
    "12-step facilitation":             "twelve_step",
    "medication assisted treatment":    "mat",
    # The presence of opioid medications (OM) or pharmacotherapies (PHR)
    # also implies MAT — handled separately below.
}

# --- type_of_care → profile.clinical.primary_focus ---
FOCUS_MAP = {
    "substance use treatment":          "substance_use",
    "mental health treatment":          "mental_health",
    "detoxification":                   "substance_use",
    # Facilities offering both get tagged dual_diagnosis below
}

# --- substances: inferred from opioid_medications, pharmacotherapies, and
#     type of care strings ---
SUBSTANCE_KEYWORDS = {
    "alcohol":          "alcohol",
    "opioid":           "opioids",
    "heroin":           "opioids",
    "methadone":        "opioids",
    "buprenorphine":    "opioids",
    "naltrexone":       "opioids",    # used for both, but primarily opioids
    "naloxone":         "opioids",
    "cocaine":          "stimulants",
    "methamphetamine":  "stimulants",
    "stimulant":        "stimulants",
    "cannabis":         "cannabis",
    "marijuana":        "cannabis",
    "benzodiazepine":   "benzodiazepines",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_services(services_str):
    """Parse the services JSON string from findtreatment.gov into a dict
    keyed by service code (f2) with semicolon-delimited values (f3)."""
    if not services_str or not services_str.strip():
        return {}
    try:
        items = ast.literal_eval(services_str)
    except (ValueError, SyntaxError):
        return {}
    result = {}
    for item in items:
        code = item.get("f2", "").strip()
        values = item.get("f3", "")
        if code:
            result[code] = [v.strip() for v in values.split(";") if v.strip()]
    return result


def map_values(raw_list, mapping):
    """Map a list of raw strings to profile-aligned values using a mapping dict.
    Matching is case-insensitive and uses substring containment."""
    mapped = set()
    for raw in raw_list:
        raw_lower = raw.lower()
        for key, value in mapping.items():
            if key in raw_lower and value is not None:
                mapped.add(value)
    return sorted(mapped)


def infer_substances(services_dict):
    """Infer substance types from multiple service fields."""
    substances = set()
    # Check across all service fields for substance keywords
    for code in ("OM", "OT", "PHR", "TC", "AUT", "TAP"):
        for item in services_dict.get(code, []):
            item_lower = item.lower()
            for keyword, substance in SUBSTANCE_KEYWORDS.items():
                if keyword in item_lower:
                    substances.add(substance)
    # Alcohol-specific check
    aut = services_dict.get("AUT", [])
    for item in aut:
        if "alcohol" in item.lower() and "does not" not in item.lower():
            substances.add("alcohol")
    return sorted(substances)


def infer_primary_focus(services_dict):
    """Determine primary_focus from type of care."""
    tc_values = services_dict.get("TC", [])
    focuses = set()
    for val in tc_values:
        mapped = map_values([val], FOCUS_MAP)
        focuses.update(mapped)
    if "substance_use" in focuses and "mental_health" in focuses:
        return ["dual_diagnosis"]
    # Also check for co-occurring in special programs
    sg_values = services_dict.get("SG", [])
    for val in sg_values:
        if "co-occurring" in val.lower():
            if "substance_use" in focuses:
                focuses.add("mental_health")
                return ["dual_diagnosis"]
    return sorted(focuses)


def infer_mat(services_dict):
    """Check if facility offers MAT based on medications/pharmacotherapies."""
    for code in ("OM", "OT", "PHR"):
        if services_dict.get(code):
            return True
    return False


def join_list(items):
    """Join a list into a pipe-delimited string for CSV storage."""
    return "|".join(items) if items else ""


# ---------------------------------------------------------------------------
# Process findtreatment.gov
# ---------------------------------------------------------------------------

def process_findtreatment():
    """Parse findtreatment.gov CSV and yield normalized row dicts."""
    with open(FINDTREATMENT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            services = parse_services(row.get("services", ""))

            # Basic facility info
            name = f"{row.get('name1', '').strip()} {row.get('name2', '').strip()}".strip()
            facility_type = row.get("typeFacility", "").strip()

            # Map service fields to profile-aligned values
            age_groups = map_values(services.get("AGE", []), AGE_MAP)
            identity_factors = map_values(services.get("SG", []), IDENTITY_MAP)
            insurance = map_values(services.get("PAY", []), INSURANCE_MAP)
            settings = map_values(services.get("SET", []), SETTING_MAP)
            therapy_approaches = map_values(services.get("TAP", []), THERAPY_MAP)
            primary_focus = infer_primary_focus(services)
            substances = infer_substances(services)

            # MAT: infer from medications or add to therapy approaches
            if infer_mat(services) and "mat" not in therapy_approaches:
                therapy_approaches.append("mat")
                therapy_approaches.sort()

            # Telehealth: also check treatment approaches for telemedicine
            tap_values = services.get("TAP", [])
            for val in tap_values:
                if "telemedicine" in val.lower() or "telehealth" in val.lower():
                    if "telehealth" not in settings:
                        settings.append("telehealth")
                        settings.sort()

            # Language: check special programs for Spanish
            languages = ["english"]  # assume English baseline
            sg_values = services.get("SG", [])
            for val in sg_values:
                if "spanish" in val.lower():
                    languages.append("spanish")
                    break

            yield {
                "name":               name,
                "address":            row.get("street1", "").strip(),
                "city":               row.get("city", "").strip(),
                "state":              row.get("state", "").strip(),
                "zip":                row.get("zip", "").strip(),
                "phone":              row.get("phone", "").strip(),
                "website":            row.get("website", "").strip(),
                "latitude":           row.get("latitude", "").strip(),
                "longitude":          row.get("longitude", "").strip(),
                "scope":              "national",
                "source":             "findtreatment.gov",
                "facility_type":      facility_type,
                "primary_focus":      join_list(primary_focus),
                "substances":         join_list(substances),
                "age_groups":         join_list(age_groups),
                "identity_factors":   join_list(identity_factors),
                "insurance":          join_list(insurance),
                "settings":           join_list(settings),
                "therapy_approaches": join_list(therapy_approaches),
                "languages":          join_list(languages),
            }


# ---------------------------------------------------------------------------
# Process Boston-area resources (from manually extracted CSV)
# ---------------------------------------------------------------------------

def process_boston():
    """Parse the hand-curated Boston resources CSV if it exists.

    Expected columns in boston_resources.csv:
        name, address, city, state, zip, phone, website,
        primary_focus, substances, age_groups, identity_factors,
        insurance, settings, therapy_approaches, languages, notes

    All multi-value columns should use pipe (|) as delimiter.
    """
    if not os.path.exists(BOSTON_CSV):
        print(f"  [SKIP] {BOSTON_CSV} not found — create it from the PDF resources.")
        print(f"         See boston_resources_template.csv for the expected format.")
        return

    with open(BOSTON_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "name":               row.get("name", "").strip(),
                "address":            row.get("address", "").strip(),
                "city":               row.get("city", "").strip(),
                "state":              row.get("state", "MA").strip(),
                "zip":                row.get("zip", "").strip(),
                "phone":              row.get("phone", "").strip(),
                "website":            row.get("website", "").strip(),
                "latitude":           "",
                "longitude":          "",
                "scope":              "boston_metro",
                "source":             "local_directory",
                "facility_type":      "",
                "primary_focus":      row.get("primary_focus", "").strip(),
                "substances":         row.get("substances", "").strip(),
                "age_groups":         row.get("age_groups", "").strip(),
                "identity_factors":   row.get("identity_factors", "").strip(),
                "insurance":          row.get("insurance", "").strip(),
                "settings":           row.get("settings", "").strip(),
                "therapy_approaches": row.get("therapy_approaches", "").strip(),
                "languages":          row.get("languages", "english").strip(),
            }


# ---------------------------------------------------------------------------
# Write template for Boston resources
# ---------------------------------------------------------------------------

TEMPLATE_HEADER = [
    "name", "address", "city", "state", "zip", "phone", "website",
    "primary_focus", "substances", "age_groups", "identity_factors",
    "insurance", "settings", "therapy_approaches", "languages", "notes",
]

TEMPLATE_ROWS = [
    {
        "name": "Example: Boston Recovery Center",
        "address": "123 Main St",
        "city": "Boston",
        "state": "MA",
        "zip": "02101",
        "phone": "617-555-0100",
        "website": "https://example.com",
        "primary_focus": "substance_use|mental_health",
        "substances": "alcohol|opioids",
        "age_groups": "adult|young_adult",
        "identity_factors": "veteran|lgbtq",
        "insurance": "medicaid_medicare|private|uninsured",
        "settings": "outpatient|intensive_outpatient",
        "therapy_approaches": "cbt|mat|twelve_step",
        "languages": "english|spanish",
        "notes": "DELETE THIS ROW — it is just an example. Use pipe (|) to separate multiple values.",
    }
]


def write_template():
    """Write a template CSV for manually entering Boston-area resources."""
    template_path = os.path.join(SCRIPT_DIR, "resources", "boston_resources_template.csv")
    with open(template_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TEMPLATE_HEADER)
        writer.writeheader()
        for row in TEMPLATE_ROWS:
            writer.writerow(row)
    print(f"  [TEMPLATE] Wrote {template_path}")
    print(f"             Fill this in from the PDF resource directories, then")
    print(f"             save as boston_resources.csv (same folder) and re-run.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "name", "address", "city", "state", "zip", "phone", "website",
    "latitude", "longitude", "scope", "source", "facility_type",
    "primary_focus", "substances", "age_groups", "identity_factors",
    "insurance", "settings", "therapy_approaches", "languages",
]


def main():
    print("=== Normalizing treatment resource data ===\n")

    rows = []

    # 1. findtreatment.gov
    print("[1/2] Processing findtreatment.gov facilities...")
    ft_count = 0
    for row in process_findtreatment():
        rows.append(row)
        ft_count += 1
    print(f"      {ft_count} facilities loaded.\n")

    # 2. Boston-area resources
    print("[2/2] Processing Boston-area resources...")
    boston_count = 0
    for row in process_boston():
        rows.append(row)
        boston_count += 1
    if boston_count:
        print(f"      {boston_count} resources loaded.\n")

    # Write template if Boston CSV doesn't exist yet
    if not os.path.exists(BOSTON_CSV):
        write_template()
        print()

    # 3. Write unified output
    print(f"Writing {len(rows)} rows to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Done. Output: {OUTPUT_CSV}")

    # Summary stats
    with_focus = sum(1 for r in rows if r["primary_focus"])
    with_insurance = sum(1 for r in rows if r["insurance"])
    with_settings = sum(1 for r in rows if r["settings"])
    with_substances = sum(1 for r in rows if r["substances"])
    print(f"\nCoverage stats:")
    print(f"  primary_focus:  {with_focus:,} / {len(rows):,} ({100*with_focus/len(rows):.1f}%)")
    print(f"  insurance:      {with_insurance:,} / {len(rows):,} ({100*with_insurance/len(rows):.1f}%)")
    print(f"  settings:       {with_settings:,} / {len(rows):,} ({100*with_settings/len(rows):.1f}%)")
    print(f"  substances:     {with_substances:,} / {len(rows):,} ({100*with_substances/len(rows):.1f}%)")


if __name__ == "__main__":
    main()
