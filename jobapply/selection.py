import re


def parse_id_ranges(expression: str) -> list[int]:
    """Parse comma-separated IDs and inclusive ranges, preserving order."""
    result = []
    for part in expression.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if match:
            start, end = map(int, match.groups())
            if start > end:
                raise ValueError(f"Invalid descending range: {part}")
            values = range(start, end + 1)
        elif part.isdigit():
            values = (int(part),)
        else:
            raise ValueError(f"Invalid ID expression: {part}")
        for value in values:
            if value not in result:
                result.append(value)
    if not result:
        raise ValueError("ID expression is empty")
    return result
