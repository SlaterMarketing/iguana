from django.conf import settings
from django.http import HttpResponse

CORS_HEADERS = 'Authorization, X-Customer-Authorization, X-Kintana-Channel, Content-Type, Accept'


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
