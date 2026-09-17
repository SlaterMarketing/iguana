from django import template

from sales.services import format_money

register = template.Library()


@register.filter
def money(cents, currency):
    """`5000|money:"mxn"` -> `50 MXN`."""
    return format_money(int(cents or 0), currency or '')


@register.filter
def clock12(value):
    """`19:30` -> `7:30 PM`, matching formatEventTime on the Astro site."""
    try:
        hours, minutes = (int(part) for part in str(value).split(':')[:2])
    except ValueError:
        return value
    return f'{hours % 12 or 12}:{minutes:02d} {"PM" if hours >= 12 else "AM"}'
