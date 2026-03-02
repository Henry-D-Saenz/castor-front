"""
Formatting utilities.
"""


def format_location(location: str) -> str:
    """
    Format location string (title case).

    Args:
        location: Location string

    Returns:
        Formatted location
    """
    if not location:
        return ""

    # Title case but preserve special cases
    words = location.split()
    formatted_words = []

    for word in words:
        if word.lower() in ['de', 'del', 'la', 'el', 'y', 'en']:
            formatted_words.append(word.lower())
        else:
            formatted_words.append(word.capitalize())

    return ' '.join(formatted_words)
