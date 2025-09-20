# app: store (or any loaded app)
# store/templatetags/rating_tags.py
from django import template
import math

register = template.Library()

@register.simple_tag
def star_breakdown(rating):
    """Return a dict: {'full': n, 'half': 0|1, 'empty': n} for a 0..5 rating."""
    try:
        r = float(rating or 0)
    except (TypeError, ValueError):
        r = 0.0
    full = int(math.floor(r))
    half = 1 if (r - full) >= 0.5 and full < 5 else 0
    empty = 5 - full - half
    return {"full": full, "half": half, "empty": empty}

@register.filter
def times(n):
    """Loop helper: {% for _ in n|times %} ... {% endfor %}"""
    try:
        return range(int(n))
    except (TypeError, ValueError):
        return range(0)
