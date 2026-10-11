"""Small deterministic derivations, explicitly separated from printed university facts."""

import re

CREDIT_CATEGORIES = {"CC", "DC", "DE", "MS", "ES", "GE"}


def credit_category_sum(content):
    rows = re.findall(r"^.+?\((CC|DC|DE|MS|ES|GE)\)\s+(\d+)\s*$", content, re.M)
    if len(rows) != 6 or {name for name, _ in rows} != CREDIT_CATEGORIES:
        return None
    values = {name: int(value) for name, value in rows}
    return {
        "value": sum(values.values()),
        "inputs": values,
        "method": "Sum of the six printed credit categories; a calculation, not a quoted printed total.",
    }
