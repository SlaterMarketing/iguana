import json

from django.conf import settings
from django.http import HttpResponse

from sales.i18n import normalize, tr

CORS_HEADERS = 'Authorization, X-Customer-Authorization, X-Kintana-Channel, X-Iguana-Locale, Content-Type, Accept'


class TranslateErrorsMiddleware:
    """API errors are written in English, and the site's account and membership screens show them as they arrive.

    The site sends the page language as `X-Iguana-Locale`, so a JSON `{"error": ...}` answer is translated here, in
    one place, instead of in every view. Unknown messages pass through unchanged.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        lang = normalize(request.headers.get('X-Iguana-Locale'))
        if lang == 'en' or response.status_code < 400 or not response.get('Content-Type', '').startswith('application/json'):
            return response
        try:
            data = json.loads(response.content)
        except ValueError:
            return response
        if isinstance(data, dict) and isinstance(data.get('error'), str):
            translated = tr(lang, data['error'])
            if translated != data['error']:
                data['error'] = translated
                response.content = json.dumps(data)
                response['Content-Length'] = str(len(response.content))
        return response


class CorsMiddleware:
    """The Astro site calls the API from the browser (sign-in, membership, forms), so allow its origins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_api = request.path.startswith(('/api/', '/_t/'))
        origin = request.headers.get('Origin', '').rstrip('/')
        allowed = is_api and (origin in settings.SITE_URLS or (settings.DEBUG and origin.startswith(('http://localhost', 'http://127.0.0.1'))))

        if is_api and request.method == 'OPTIONS':
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if allowed:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Headers'] = CORS_HEADERS
            response['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, OPTIONS'
            response['Access-Control-Max-Age'] = '600'
            response['Vary'] = 'Origin'
        elif request.path.startswith('/api/ingest/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
