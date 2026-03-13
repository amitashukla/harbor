import json
import re


def load_schema(schema_path):
    """Load the user profile schema from a JSON file."""
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_empty_profile():
    """
    Create an empty user profile with all fields set to null/empty.
    This represents a user we know nothing about yet.
    """
    return {
        "demographics": {
            "population": None,
            "identity_factors": [],
            "language": None,
            "pronouns": None
        },
        "logistics": {
            "zipcode": None,
            "region": None,
            "profession": None,
            "accessibility_needs": [],
            "insurance": None,
            "treatment_history": None
        },
        "status": {
            "current_state": None,
            "crisis_level": None,
            "temporary_factors": []
        },
        "clinical": {
            "primary_focus": None,
            "substances": []
        },
        "preferences": {
            "setting": None,
            "therapy_approach": None,
            "scheduling": [],
            "barriers": [],
            "contact_channel": None
        }
    }


def extract_profile_updates(schema, user_input):
    """
    Scan user input against the schema and return a dict of detected profile updates.

    For 'single' type fields, returns the first matched option value.
    For 'multi' type fields, returns a list of all matched option values.
    For 'extracted' type fields (zipcode, region, treatment_history), uses
    pattern matching or returns raw text snippets.

    Args:
        schema: The loaded profile schema dict.
        user_input: The user's message text.

    Returns:
        dict: Nested dict mirroring the profile structure, containing only
              fields where matches were found.
    """
    input_lower = user_input.lower()
    updates = {}

    for category_name, category in schema.items():
        category_updates = {}

        for field_name, field_def in category.items():
            field_type = field_def.get("type")

            if field_type == "extracted":
                # Special handling for pattern-based or free-text fields
                value = _extract_field(field_name, field_def, user_input, input_lower)
                if value is not None:
                    category_updates[field_name] = value

            elif field_type in ("single", "multi"):
                matches = []
                for option in field_def.get("options", []):
                    for keyword in option.get("keywords", []):
                        if keyword and keyword.lower() in input_lower:
                            matches.append(option["value"])
                            break  # one keyword match per option is enough

                if matches:
                    if field_type == "single":
                        category_updates[field_name] = matches[0]
                    else:
                        category_updates[field_name] = matches

        if category_updates:
            updates[category_name] = category_updates

    return updates


def _extract_field(field_name, field_def, user_input, input_lower):
    """Handle extraction for non-option fields like zipcode and treatment_history."""
    if field_name == "zipcode":
        pattern = field_def.get("pattern", r"\b\d{5}\b")
        match = re.search(pattern, user_input)
        if match:
            return match.group()
        return None

    if field_name == "region":
        # Region is typically set explicitly or by the LLM, not keyword-matched.
        # We do a lightweight check for common geographic indicators.
        geo_patterns = [
            r"\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "in Boston", "in Pocahontas County"
            r"\bnear\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "near Springfield"
            r"\bfrom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "from Cambridge"
        ]
        for pattern in geo_patterns:
            match = re.search(pattern, user_input)
            if match:
                return match.group(1)
        return None

    if field_name == "treatment_history":
        history_keywords = ["rehab", "treatment before", "been to", "tried",
                            "previous treatment", "went to", "was in",
                            "12-step", "residential before", "relapsed"]
        for keyword in history_keywords:
            if keyword in input_lower:
                return user_input  # store the raw message as context
        return None

    return None


def merge_profile(profile, updates):
    """
    Merge new updates into the existing profile.

    - For 'single' fields (non-list values): new values overwrite old ones.
    - For 'multi' fields (list values): new values are appended (no duplicates).
    - None values in updates are ignored (don't clear existing data).

    Args:
        profile: The current user profile dict (modified in place).
        updates: The updates dict from extract_profile_updates().

    Returns:
        dict: The updated profile (same object as input).
    """
    for category_name, category_updates in updates.items():
        if category_name not in profile:
            continue

        for field_name, new_value in category_updates.items():
            if field_name not in profile[category_name]:
                continue

            if new_value is None:
                continue

            existing = profile[category_name][field_name]

            if isinstance(existing, list) and isinstance(new_value, list):
                # Append new values, skip duplicates
                for v in new_value:
                    if v not in existing:
                        existing.append(v)
            elif isinstance(existing, list) and not isinstance(new_value, list):
                # Single value going into a list field
                if new_value not in existing:
                    existing.append(new_value)
            else:
                # Single value field: overwrite
                profile[category_name][field_name] = new_value

    return profile


def profile_to_summary(profile):
    """
    Convert a user profile dict into a concise text summary for injection
    into the system prompt. Only includes fields that have been filled in.

    Returns:
        str: A human-readable summary, or empty string if profile is empty.
    """
    lines = []

    category_labels = {
        "demographics": "Demographics",
        "logistics": "Logistics & History",
        "status": "Current Status",
        "clinical": "Clinical Needs",
        "preferences": "Preferences & Barriers"
    }

    for category_name, category_label in category_labels.items():
        category = profile.get(category_name, {})
        category_lines = []

        for field_name, value in category.items():
            if value is None:
                continue
            if isinstance(value, list) and len(value) == 0:
                continue

            # Format the field name nicely
            display_name = field_name.replace("_", " ").title()

            if isinstance(value, list):
                category_lines.append(f"  - {display_name}: {', '.join(str(v) for v in value)}")
            else:
                category_lines.append(f"  - {display_name}: {value}")

        if category_lines:
            lines.append(f"[{category_label}]")
            lines.extend(category_lines)

    if not lines:
        return ""

    return "USER PROFILE (gathered so far):\n" + "\n".join(lines)
