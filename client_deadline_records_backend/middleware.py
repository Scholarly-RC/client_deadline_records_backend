import re

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin


class CSRFExemptMiddleware(MiddlewareMixin):
    """
    Middleware to exempt specific URL patterns from CSRF validation.
    Useful for API endpoints that use token-based authentication.
    """

    def process_request(self, request):
        # Get exempt URLs from settings
        exempt_urls = getattr(settings, "CSRF_EXEMPT_URLS", [])

        # Check if current URL matches any exempt pattern
        for exempt_url in exempt_urls:
            if re.match(exempt_url, request.path):
                setattr(request, "_dont_enforce_csrf_checks", True)
                break

        return None
