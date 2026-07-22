"""Adds common browser-security response headers. Set once, forget forever.

References:
  - OWASP secure-headers project
  - Mozilla observatory recommendations
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

# Deliberately conservative CSP: no inline/eval unless explicitly needed, no
# third-party origins beyond the ones the widget's <img> tag might legitimately
# fetch. The admin panel + widget both work under this default. Loosen if a
# specific origin needs to be trusted (e.g. an external analytics script).
_DEFAULT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https: wss:; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Anti-clickjacking (browsers still honor this; belt-and-suspenders with
        # the CSP frame-ancestors above).
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Prevent MIME-sniffing (browsers treating a .txt as HTML because it
        # happens to start with <html>).
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Referrer leakage — send origin only on cross-origin, nothing on
        # downgrade.
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # Feature access. Disable geolocation, camera, microphone by default.
        # If the voice channel ever grows a browser-side mic surface, relax
        # this specifically for that origin.
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )

        # HSTS — only in prod (in dev the app is served over http://localhost).
        # 2 years, subdomains included. `preload` requires submission at
        # hstspreload.org — leave off until you're ready to commit.
        if settings.APP_ENV == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )

        # CSP — same in dev and prod. Widget host pages set their own CSP; ours
        # only affects the admin panel + JSON API responses (browsers ignore
        # CSP on application/json but it's harmless).
        response.headers.setdefault("Content-Security-Policy", _DEFAULT_CSP)

        return response
