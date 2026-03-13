"""
Extract structured facility/resource data from Boston-area PDF directories
and produce boston_resources.csv for the normalize_resources.py pipeline.

PDFs processed:
  1. Resource Directory August 2025 v9.pdf — DMH Area offices & inpatient facilities
  2. Combined-2019-Multicultural-Directory-v2.pdf — Multicultural mental health orgs
  3. Western Mass Young Adult Resource Guide — Young adult resources

Uses pdfplumber column-cropping for the three-column Multicultural directory
and pdftotext for the single-column PDFs.

Usage:
    python extract_boston_pdfs.py
"""

import csv
import os
import re
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(SCRIPT_DIR, "resources")
OUTPUT_CSV = os.path.join(RESOURCES_DIR, "boston_resources.csv")

# ---------------------------------------------------------------------------
# Profile-aligned value vocabulary (must match normalize_resources.py)
# ---------------------------------------------------------------------------

SERVICE_KEYWORDS_TO_FOCUS = {
    "substance abuse":      "substance_use",
    "substance use":        "substance_use",
    "addiction":            "substance_use",
    "recovery from addiction": "substance_use",
    "detox":                "substance_use",
    "mental health":        "mental_health",
    "psychiatric":          "mental_health",
    "psychiatry":           "mental_health",
    "counseling":           "mental_health",
    "psychotherapy":        "mental_health",
    "behavioral health":    "mental_health",
    "eating disorder":      "mental_health",
    "dual recovery":        "dual_diagnosis",
    "co-occurring":         "dual_diagnosis",
}

SERVICE_KEYWORDS_TO_SETTING = {
    "inpatient":            "residential",
    "residential":          "residential",
    "emergency shelter":    "residential",
    "outpatient":           "outpatient",
    "day program":          "intensive_outpatient",
    "day treatment":        "intensive_outpatient",
    "telehealth":           "telehealth",
    "telemedicine":         "telehealth",
    "drop-in":              "outpatient",
}

SERVICE_KEYWORDS_TO_SUBSTANCE = {
    "alcohol":              "alcohol",
    "opioid":               "opioids",
    "heroin":               "opioids",
    "methadone":            "opioids",
    "buprenorphine":        "opioids",
    "substance abuse":      "substance_use",  # generic
    "drug":                 "substance_use",
}

SERVICE_KEYWORDS_TO_IDENTITY = {
    "lgbtq":                "lgbtq",
    "gay":                  "lgbtq",
    "lesbian":              "lgbtq",
    "bisexual":             "lgbtq",
    "transgender":          "lgbtq",
    "veteran":              "veteran",
    "military":             "veteran",
    "women":                "woman",
    "woman":                "woman",
    "deaf":                 "accessibility",
    "hard of hearing":      "accessibility",
    "disability":           "accessibility",
    "disabilities":         "accessibility",
    "wheelchair":           "wheelchair_user",
    "homeless":             "homeless",
    "unhoused":             "homeless",
    "refugee":              "immigrant_refugee",
    "immigrant":            "immigrant_refugee",
}

AGE_KEYWORDS = {
    "children":             "adolescent",
    "child":                "adolescent",
    "adolescent":           "adolescent",
    "youth":                "adolescent",
    "teen":                 "adolescent",
    "young adult":          "young_adult",
    "college":              "young_adult",
    "adult":                "adult",
    "elder":                "older_adult",
    "senior":               "older_adult",
    "older adult":          "older_adult",
    "aging":                "older_adult",
}

LANGUAGE_NORMALIZE = {
    "spanish": "spanish",
    "portuguese": "portuguese",
    "haitian creole": "haitian_creole",
    "french": "french",
    "mandarin chinese": "mandarin",
    "cantonese chinese": "cantonese",
    "mandarin": "mandarin",
    "cantonese": "cantonese",
    "chinese": "mandarin",
    "vietnamese": "vietnamese",
    "arabic": "arabic",
    "russian": "russian",
    "korean": "korean",
    "japanese": "japanese",
    "hindi": "hindi",
    "urdu": "urdu",
    "bengali": "bengali",
    "bangla": "bengali",
    "khmer": "khmer",
    "cambodian": "khmer",
    "somali": "somali",
    "cape verdean creole": "cape_verdean_creole",
    "cape verdean": "cape_verdean_creole",
    "nepali": "nepali",
    "thai": "thai",
    "lao": "lao",
    "laotian": "lao",
    "tagalog": "tagalog",
    "italian": "italian",
    "hebrew": "hebrew",
    "punjabi": "punjabi",
    "gujarati": "gujarati",
    "tamil": "tamil",
    "american sign language": "asl",
    "asl": "asl",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def extract_text(pdf_path):
    """Extract full text from a PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: pdftotext failed on {pdf_path}: {result.stderr}")
        return ""
    return result.stdout


def classify_services(text_block):
    """Scan a text block for keywords and return profile-aligned tags."""
    lower = text_block.lower()

    focuses = set()
    for kw, val in SERVICE_KEYWORDS_TO_FOCUS.items():
        if kw in lower:
            focuses.add(val)
    if "substance_use" in focuses and "mental_health" in focuses:
        focuses = {"dual_diagnosis"}

    settings = set()
    for kw, val in SERVICE_KEYWORDS_TO_SETTING.items():
        if kw in lower:
            settings.add(val)

    substances = set()
    for kw, val in SERVICE_KEYWORDS_TO_SUBSTANCE.items():
        if kw in lower:
            substances.add(val)
    substances.discard("substance_use")

    identities = set()
    for kw, val in SERVICE_KEYWORDS_TO_IDENTITY.items():
        if kw in lower:
            identities.add(val)

    ages = set()
    for kw, val in AGE_KEYWORDS.items():
        if kw in lower:
            ages.add(val)

    return {
        "primary_focus":    sorted(focuses),
        "settings":         sorted(settings),
        "substances":       sorted(substances),
        "identity_factors": sorted(identities),
        "age_groups":       sorted(ages),
    }


def extract_languages(text_block):
    """Extract language tags from a text block."""
    lower = text_block.lower()
    langs = {"english"}
    for kw, val in LANGUAGE_NORMALIZE.items():
        if kw in lower:
            langs.add(val)
    if re.search(r'interpret(?:er|ation)\s+(?:services?\s+)?(?:for\s+)?(?:over|more than)\s+\d+', lower):
        langs.add("multilingual_interpretation")
    return sorted(langs)


def extract_phone(text):
    """Extract the first phone number from text."""
    m = re.search(r'[\(]?\d{3}[\)\-\.\s]+\d{3}[\-\.\s]+\d{4}', text)
    return m.group(0).strip() if m else ""


def extract_address_parts(text):
    """Try to extract address, city, state, zip from text."""
    m = re.search(
        r'(\d+\s+[A-Za-z\s\.]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Way|Boulevard|Blvd|Place|Pl|Court|Ct|Floor)[\w\s,#]*?)\s*\n?\s*'
        r'([A-Za-z\s\.]+),\s*(MA)\s+(\d{5})',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
    m2 = re.search(r'([A-Za-z\s\.]+),\s*(MA)\s+(\d{5})', text, re.IGNORECASE)
    if m2:
        return "", m2.group(1).strip(), m2.group(2).strip(), m2.group(3).strip()
    return "", "", "MA", ""


def extract_website(text):
    """Extract the first URL or domain from text."""
    m = re.search(r'https?://[^\s,\)]+', text)
    if m:
        return m.group(0).strip().rstrip('.')
    m = re.search(r'(?:www\.)?[a-zA-Z0-9\-]+\.[a-z]{2,}(?:/[^\s,\)]*)?', text)
    if m:
        url = m.group(0).strip().rstrip('.')
        if not url.startswith('http'):
            url = 'https://' + url
        return url
    return ""


def _build_record(name, addr, city, state, zipcode, phone, website,
                  tags, languages, region, source_note):
    """Build a normalized record dict."""
    return {
        "name":               name,
        "address":            addr,
        "city":               city if city else "",
        "state":              state,
        "zip":                zipcode,
        "phone":              phone,
        "website":            website,
        "primary_focus":      "|".join(tags["primary_focus"]),
        "substances":         "|".join(tags["substances"]),
        "age_groups":         "|".join(tags["age_groups"]),
        "identity_factors":   "|".join(tags["identity_factors"]),
        "insurance":          "",
        "settings":           "|".join(tags["settings"]),
        "therapy_approaches": "",
        "languages":          "|".join(languages),
        "dmh_region":         region,
        "notes":              source_note,
    }


# ---------------------------------------------------------------------------
# Parser: Resource Directory August 2025 v9.pdf
# (DMH offices, inpatient facilities, area service sites)
# ---------------------------------------------------------------------------

def parse_resource_directory():
    """Parse the DMH Resource Directory into facility records."""
    pdf_path = os.path.join(RESOURCES_DIR, "Resource Directory August 2025 v9.pdf")
    if not os.path.exists(pdf_path):
        print(f"  [SKIP] {pdf_path} not found")
        return []

    text = extract_text(pdf_path)
    records = []
    current_region = "Statewide"

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect region headers
        if re.match(r'^Metro Boston Area$', line):
            current_region = "Metro Boston"
        elif re.match(r'^Southeast Area$', line):
            current_region = "Southeast"
        elif re.match(r'^Northeast Area$', line):
            current_region = "Northeast"
        elif re.match(r'^Central (?:Massachusetts )?Area$', line):
            current_region = "Central MA"
        elif re.match(r'^Western (?:Massachusetts )?Area$', line):
            current_region = "Western MA"

        # Detect facility/site blocks
        if re.search(r'(?:Site Office|Mental Health Center|Hospital|Recovery Center)', line, re.IGNORECASE):
            block_lines = [line]
            j = i + 1
            blank_count = 0
            while j < len(lines) and blank_count < 2 and j < i + 30:
                if lines[j].strip() == "":
                    blank_count += 1
                else:
                    blank_count = 0
                block_lines.append(lines[j])
                j += 1
            block = "\n".join(block_lines)

            phone = extract_phone(block)
            if phone:
                addr, city, state, zipcode = extract_address_parts(block)
                name = line.strip()
                website = extract_website(block)
                tags = classify_services(block)
                if not tags["primary_focus"]:
                    tags["primary_focus"] = ["mental_health"]

                records.append(_build_record(
                    name, addr, city or current_region, state, zipcode,
                    phone, website, tags, ["english"],
                    current_region, "DMH Resource Directory 2025"
                ))
        i += 1

    return records


# ---------------------------------------------------------------------------
# Parser: Combined-2019-Multicultural-Directory-v2.pdf
# Uses pdfplumber column-cropping for the three-column table layout
# ---------------------------------------------------------------------------

MULTICULTURAL_REGIONS = {
    "STATEWIDE":    "Statewide",
    "METRO BOSTON":  "Metro Boston",
    "CENTRAL":      "Central MA",
    "NORTHEAST":    "Northeast",
    "SOUTHEAST":    "Southeast",
    "WESTERN":      "Western MA",
}

SKIP_PATTERNS = [
    "table of contents", "how to use", "disclaimer", "welcome",
    "acknowledgement", "quick search", "2019 multicultural",
    "mental health education materials", "resource directory home",
    "statewide services", "other provider organizations",
    "government agencies", "emergency services program",
]


def parse_multicultural_directory():
    """Parse the 2019 Multicultural Mental Health Resource Directory.

    Uses pdfplumber to crop each page into three columns (Organization,
    Services, Languages) matching the PDF's table layout, then parses
    entries from the left column and classifies them using all three.
    Falls back to single-column parsing for narrative pages.
    """
    import pdfplumber

    pdf_path = os.path.join(RESOURCES_DIR, "Combined-2019-Multicultural-Directory-v2.pdf")
    if not os.path.exists(pdf_path):
        print(f"  [SKIP] {pdf_path} not found")
        return []

    records = []
    current_region = "Statewide"
    region_pattern = re.compile(
        r'(?:2019 )?DMH MULTICULTURAL MENTAL HEALTH RESOURCE DIRECTORY \(([^)]+)\)'
    )

    pdf = pdfplumber.open(pdf_path)

    for page in pdf.pages:
        page_text = page.extract_text() or ""

        # Detect region from page text
        rm = region_pattern.search(page_text)
        if rm:
            region_text = rm.group(1).upper()
            for key, val in MULTICULTURAL_REGIONS.items():
                if key in region_text:
                    current_region = val
                    break

        w = page.width
        h = page.height
        is_table_page = ("ORGANIZATION" in page_text
                         and "SERVICES OFFERED" in page_text
                         and page_text.count('−') >= 2)

        if is_table_page:
            # Crop three columns matching the PDF's table layout
            col1_text = (page.crop((0, 0, w * 0.33, h)).extract_text() or "")
            col2_text = (page.crop((w * 0.33, 0, w * 0.70, h)).extract_text() or "")
            col3_text = (page.crop((w * 0.70, 0, w, h)).extract_text() or "")

            entries = _split_column_into_entries(col1_text)
            services_blocks = _split_column_into_entries(col2_text)
            language_blocks = _split_column_into_entries(col3_text)

            for idx, entry_text in enumerate(entries):
                org_name, addr, city, state, zipcode, phone, website = _parse_org_block(entry_text)
                if not org_name or len(org_name) < 3:
                    continue
                if any(sp in org_name.lower() for sp in SKIP_PATTERNS):
                    continue

                svc_text = services_blocks[idx] if idx < len(services_blocks) else ""
                lang_text = language_blocks[idx] if idx < len(language_blocks) else ""

                tags = classify_services(svc_text + "\n" + entry_text)
                languages = extract_languages(lang_text)

                if not tags["primary_focus"]:
                    tags["primary_focus"] = ["mental_health"]

                records.append(_build_record(
                    org_name, addr, city, state, zipcode, phone, website,
                    tags, languages, current_region,
                    "DMH Multicultural Directory 2019"
                ))
        else:
            # Single-column pages (statewide section, intro pages)
            page_records = _parse_single_column_page(page_text, current_region)
            for rec in page_records:
                if any(sp in rec["name"].lower() for sp in SKIP_PATTERNS):
                    continue
                records.append(rec)

    pdf.close()

    # De-duplicate by normalized name
    seen = set()
    deduped = []
    for rec in records:
        key = re.sub(r'\s+', ' ', rec["name"].lower().strip())
        if key not in seen:
            seen.add(key)
            deduped.append(rec)

    return deduped


def _split_column_into_entries(col_text):
    """Split a column's text into individual entry blocks.

    Each entry is separated by one or more blank lines.
    We skip column header lines (ORGANIZATION, SERVICES OFFERED, etc.).
    """
    lines = col_text.split('\n')
    entries = []
    current_block = []

    # Skip header lines
    headers = {"ORGANIZATION", "SERVICES OFFERED", "LANGUAGES",
               "OTHER THAN", "ENGLISH", "LANGUAGES OTHER THAN ENGLISH"}
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped in headers or not stripped:
                continue
            started = True

        if not stripped:
            if current_block:
                entries.append("\n".join(current_block))
                current_block = []
            continue

        current_block.append(stripped)

    if current_block:
        entries.append("\n".join(current_block))

    return entries


def _parse_org_block(text):
    """Parse an organization block from column 1 into structured fields.

    Returns: (org_name, addr, city, state, zipcode, phone, website)
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return "", "", "", "MA", "", "", ""

    org_name_parts = []
    addr = ""
    city = ""
    state = "MA"
    zipcode = ""
    phone = ""
    website = ""

    for line in lines:
        # Phone number
        if re.search(r'[\(]?\d{3}[\)\-\.\s]+\d{3}[\-\.\s]+\d{4}', line) and not phone:
            phone = extract_phone(line)
            continue
        # Website/URL
        if re.search(r'[a-z]+\.[a-z]{2,}/', line) or re.search(r'^(?:www\.)?[a-z][\w\-]*\.[a-z]{2,}$', line, re.I):
            if not website:
                website = extract_website(line)
            continue
        # Address with city, state, zip
        addr_match = re.search(r'([A-Za-z\s\.]+),\s*(MA)\s+(\d{5})', line)
        if addr_match:
            street_match = re.match(r'^(\d+\s+.+?),?\s*$', line.split(',')[0] if ',' in line else "")
            if street_match:
                addr = street_match.group(1).strip()
            city = addr_match.group(1).strip()
            state = addr_match.group(2).strip()
            zipcode = addr_match.group(3).strip()
            continue
        # PO Box
        if re.match(r'^P\.?O\.?\s+Box', line, re.I):
            addr = line
            continue
        # Street address without city/state
        if re.match(r'^\d+\s+[A-Za-z]', line) and re.search(r'(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Way|Floor|Suite)', line, re.I):
            addr = line
            continue
        # Skip known non-name lines
        if line.startswith(('−', '-', '•', 'Fax', 'TTY', 'Toll')):
            continue
        if re.match(r'^\d+$', line):
            continue
        if 'DMH MULTICULTURAL' in line:
            continue
        if 'Hotline:' in line or 'Helpline:' in line:
            phone_in_line = extract_phone(line)
            if phone_in_line and not phone:
                phone = phone_in_line
            continue
        # Remaining lines are part of the org name
        org_name_parts.append(line)

    org_name = " ".join(org_name_parts).strip()
    org_name = re.sub(r'\s+', ' ', org_name)

    return org_name, addr, city, state, zipcode, phone, website


def _parse_single_column_page(page_text, region):
    """Parse organization entries from a single-column (narrative) page."""
    records = []
    lines = page_text.split('\n')
    phone_pattern = re.compile(r'[\(]?\d{3}[\)\-\.\s]+\d{3}[\-\.\s]+\d{4}')

    for idx, line in enumerate(lines):
        if not phone_pattern.search(line):
            continue

        # Look backwards for org name
        org_name = ""
        for j in range(idx - 1, max(0, idx - 10), -1):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if phone_pattern.search(candidate):
                continue
            if candidate.startswith(('−', '-', '•', 'Fax', 'TTY', 'Toll')):
                continue
            if re.search(r'mass\.gov|\.org|\.com|http', candidate, re.I) and len(candidate) < 80:
                continue
            if re.match(r'^P\.?O\.?\s+Box', candidate, re.I):
                continue
            if re.match(r'^\d+\s+[A-Za-z]', candidate) and re.search(r'(?:Street|St|Avenue|Ave|Road|Rd)', candidate, re.I):
                continue
            if re.match(r'^\d+$', candidate):
                continue
            if 'DMH MULTICULTURAL' in candidate:
                continue
            if re.search(r'[A-Z][a-z]', candidate) or candidate.isupper():
                org_name = candidate
                break

        if not org_name or len(org_name) < 3:
            continue

        block_start = max(0, idx - 8)
        block_end = min(len(lines), idx + 20)
        full_block = "\n".join(lines[block_start:block_end])

        phone = extract_phone(line)
        addr, city, state, zipcode = extract_address_parts(
            "\n".join(lines[max(0, idx - 6):idx + 2])
        )
        website = extract_website(full_block)
        tags = classify_services(full_block)
        languages = extract_languages(full_block)

        if not tags["primary_focus"]:
            tags["primary_focus"] = ["mental_health"]

        records.append(_build_record(
            org_name, addr, city, state, zipcode, phone, website,
            tags, languages, region, "DMH Multicultural Directory 2019"
        ))

    return records


# ---------------------------------------------------------------------------
# Parser: Western Mass Young Adult Resource Guide
# ---------------------------------------------------------------------------

def parse_western_mass_guide():
    """Parse the Western Mass Young Adult Resource Guide."""
    pdf_path = os.path.join(RESOURCES_DIR,
        "Mental Health Support & Recovery - Western Mass. Young Adult Resource Guide _ Mass.gov.pdf")
    if not os.path.exists(pdf_path):
        print(f"  [SKIP] {pdf_path} not found")
        return []

    text = extract_text(pdf_path)
    records = []
    lines = text.split('\n')
    phone_pattern = re.compile(r'[\(]?\d{3}[\)\-\.\s]+\d{3}[\-\.\s]+\d{4}')

    seen = set()
    for idx, line in enumerate(lines):
        if not phone_pattern.search(line):
            continue

        start = max(0, idx - 10)
        block = "\n".join(lines[start:min(len(lines), idx + 15)])

        org_name = ""
        for j in range(idx - 1, max(0, idx - 10), -1):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if phone_pattern.search(candidate):
                continue
            if candidate.startswith(('−', '-', '•', 'Fax', 'TTY', 'Toll')):
                continue
            if re.search(r'mass\.gov|\.org|\.com|http', candidate, re.I):
                continue
            if re.match(r'^P\.?O\.?\s+Box', candidate, re.I):
                continue
            if re.search(r'(?:Street|St|Avenue|Ave|Road|Rd),?\s', candidate, re.I) and re.search(r'MA\s+\d{5}', candidate):
                continue
            org_name = candidate
            break

        if not org_name or len(org_name) < 3:
            continue
        key = org_name.lower().strip()
        if key in seen:
            continue
        seen.add(key)

        phone = extract_phone(line)
        addr, city, state, zipcode = extract_address_parts(block)
        website = extract_website(block)
        tags = classify_services(block)
        languages = extract_languages(block)

        if not tags["primary_focus"]:
            tags["primary_focus"] = ["mental_health"]
        if "young_adult" not in tags["age_groups"]:
            tags["age_groups"].append("young_adult")
            tags["age_groups"].sort()

        records.append(_build_record(
            org_name, addr, city, state, zipcode, phone, website,
            tags, languages, "Western MA", "Western Mass Young Adult Guide"
        ))

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "name", "address", "city", "state", "zip", "phone", "website",
    "primary_focus", "substances", "age_groups", "identity_factors",
    "insurance", "settings", "therapy_approaches", "languages",
    "dmh_region", "notes",
]


def main():
    print("=== Extracting Boston-area PDF resources ===\n")

    all_records = []

    # 1. DMH Resource Directory 2025
    print("[1/3] Parsing Resource Directory August 2025 v9.pdf...")
    recs = parse_resource_directory()
    print(f"      {len(recs)} entries extracted.")
    all_records.extend(recs)

    # 2. Multicultural Directory 2019
    print("[2/3] Parsing Combined-2019-Multicultural-Directory-v2.pdf...")
    recs = parse_multicultural_directory()
    print(f"      {len(recs)} entries extracted.")
    all_records.extend(recs)

    # 3. Western Mass Young Adult Guide
    print("[3/3] Parsing Western Mass Young Adult Resource Guide...")
    recs = parse_western_mass_guide()
    print(f"      {len(recs)} entries extracted.")
    all_records.extend(recs)

    # De-duplicate by (name, phone) across sources
    seen = set()
    deduped = []
    for rec in all_records:
        key = (rec["name"].lower().strip(), rec["phone"])
        if key not in seen:
            seen.add(key)
            deduped.append(rec)

    print(f"\n{len(deduped)} unique records after de-duplication (from {len(all_records)} total).")

    # Write output
    print(f"Writing to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for rec in deduped:
            writer.writerow(rec)

    print(f"Done. Output: {OUTPUT_CSV}")

    # Summary
    regions = {}
    for r in deduped:
        reg = r.get("dmh_region", "Unknown")
        regions[reg] = regions.get(reg, 0) + 1
    print(f"\nBy DMH region:")
    for reg, count in sorted(regions.items()):
        print(f"  {reg}: {count}")

    sources = {}
    for r in deduped:
        src = r.get("notes", "Unknown")
        sources[src] = sources.get(src, 0) + 1
    print(f"\nBy source:")
    for src, count in sorted(sources.items()):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
