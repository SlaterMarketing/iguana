import functools
import json
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from crm.models import Contact

FAN_TOKEN_SALT = 'iguana.fan-session'
FAN_TOKEN_MAX_AGE = timedelta(days=30)


def error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def _bearer(value):
    value = (value or '').strip()
    return value[7:].strip() if value.lower().startswith('bearer ') else ''


def json_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def api_view(methods=('GET',), secret=False):
    """Checks the site's API key (what the SDK sends as `Authorization: Bearer`) and parses JSON bodies."""

    def decorator(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return error('Method not allowed', 405)
            key = _bearer(request.headers.get('Authorization'))
            allowed = settings.SECRET_API_KEYS if secret else settings.PUBLIC_API_KEYS + settings.SECRET_API_KEYS
            if not key or key not in allowed:
                return error('Invalid or missing token', 401)
            if request.method in ('POST', 'PATCH'):
                request.json = json_body(request)
                if request.json is None:
                    return error('Body must be a JSON object')
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def issue_fan_token(email):
    expires = timezone.now() + FAN_TOKEN_MAX_AGE
    token = signing.dumps({'email': email}, salt=FAN_TOKEN_SALT, compress=True)
    return token, expires


def contact_from_fan_token(token):
    if not token:
        return None
    try:
        data = signing.loads(token, salt=FAN_TOKEN_SALT, max_age=FAN_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    return Contact.objects.filter(email=data.get('email', '')).first()


def fan_contact(request):
    """Signed-in fan, from X-Customer-Authorization (SDK fan calls) or a plain Authorization header."""
    return contact_from_fan_token(_bearer(request.headers.get('X-Customer-Authorization')))


def fan_required(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        request.contact = fan_contact(request)
        if request.contact is None:
            return error('Sign in required', 401)
        return view(request, *args, **kwargs)

    return wrapper
