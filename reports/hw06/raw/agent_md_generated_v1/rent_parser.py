# rent_parser.py
def parse_monthly_rent(text: str) -> int:
    """
    Converts a rent string from a listing into whole US dollars per month.

    Args:
    text (str): The rent string to parse.

    Returns:
    int: The monthly rent in whole US dollars.

    Raises:
    ValueError: If the input string is empty, contains no number, or represents a negative or zero amount.
    """
    # Remove leading and trailing whitespace
    text = text.strip()
    
    # Check if the string is empty
    if not text:
        raise ValueError("Input string is empty")
    
    # Remove currency symbols and units (e.g., "k" for thousand)
    text = text.replace("$", "").replace("per month", "").replace("per ", "").replace("k", "")
    
    # Check if the string contains a number
    if not text.isdigit():
        raise ValueError("Input string contains no number")
    
    # Convert the string to an integer
    rent = int(text)
    
    # Check if the amount is negative or zero
    if rent <= 0:
        raise ValueError("Input string represents a negative or zero amount")
    
    return rent
