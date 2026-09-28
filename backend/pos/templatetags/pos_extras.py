from django import template

register = template.Library()


@register.filter
def pesos(cents):
    """150050 -> $1,500.50. Blank for None, so an empty cell stays empty rather than reading $0.00."""
    if cents in (None, ''):
        return ''
    cents = int(cents)
    sign = '-' if cents < 0 else ''
    return f'{sign}${abs(cents) / 100:,.2f}'


@register.filter
def qty(value):
    """Decimal quantities without trailing zeros: 12.00 -> 12, 0.50 -> 0.5."""
    if value is None:
        return ''
    return f'{value:f}'.rstrip('0').rstrip('.') if '.' in f'{value:f}' else f'{value:f}'
