from django import template

from sales.i18n import tr
from sales.services import format_money

register = template.Library()


@register.filter
def clock12(value, lang='en'):
    """`19:30` -> `7:30 PM` (`7:30 p. m.` in Spanish), matching formatEventTime on the Astro site."""
    try:
        hours, minutes = (int(part) for part in str(value).split(':')[:2])
    except ValueError:
        return value
    pm = hours >= 12
    suffix = ('p. m.' if pm else 'a. m.') if lang == 'es' else ('PM' if pm else 'AM')
    return f'{hours % 12 or 12}:{minutes:02d} {suffix}'


@register.filter
def money(cents, currency):
    """`5000|money:"mxn"` -> `50 MXN`."""
    return format_money(int(cents or 0), currency or '')


@register.simple_tag
def t(lang, text, *params):
    """`{% t lang "Ticket {0} of {1}" n total %}`: the text in `lang` from sales.i18n, autoescaped."""
    return tr(lang, text, *params)
