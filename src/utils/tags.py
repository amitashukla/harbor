def tag_user_input(file_path, user_input):
    """
    Tag user input with keywords/substances from a file.
    
    This function:
    1. Loads tags from the specified file (preserving original case)
    2. Detects matches in user input (case-insensitive, partial matches)
    3. Returns a list of matching tags in their original case
    
    Args:
        file_path (str): Path to the file containing tags (one per line)
        user_input (str): The user's input text to search for tags
        
    Returns:
        list: List of matching tags in their original case from the file
    """
    # Load tags (preserve original case)
    tags_original = []
    tags_lower = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                tags_original.append(stripped)
                tags_lower.append(stripped.lower())
    
    # Convert user input to lowercase for case-insensitive matching
    user_input_lower = user_input.lower()
    
    # Find matching tags (case-insensitive, partial matches)
    matching_tags = []
    for i, tag_lower in enumerate(tags_lower):
        if tag_lower in user_input_lower:
            matching_tags.append(tags_original[i])
    
    return matching_tags

