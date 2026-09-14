from django import template

register = template.Library()


@register.filter
def clock12(value):
    """`19:30` -> `7:30 PM`, matching formatEventTime on the Astro site."""
    try:
        hours, minutes = (int(part) for part in str(value).split(':')[:2])
    except ValueError:
        return value
    return f'{hours % 12 or 12}:{minutes:02d} {"PM" if hours >= 12 else "AM"}'
