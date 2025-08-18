from django import template
import json

register = template.Library()

@register.filter
def pprint(value):
    """Pretty print JSON data"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    
    try:
        return json.dumps(value, indent=2)
    except (TypeError, ValueError):
        return str(value)
