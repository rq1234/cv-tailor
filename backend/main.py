"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from backend.api.routes import applications, auth, cv, experiences, export, rules, tailor  # noqa: E402
from backend.config import get_settings
from backend.exceptions import AppError

settings = get_settings()
logger.info("CORS origins: %s", settings.cors_origins)

app = FastAPI(title="CV Tailor API", version="0.1.0")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


class SecurityHeadersMiddleware:
    """Add security headers to all responses (pure ASGI — compatible with CORSMiddleware)."""

    _HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"x-xss-protection", b"1; mode=block"),
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
    ]

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", [])) + self._HEADERS
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://cv-tailor(-[a-z0-9]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(cv.router)
app.include_router(experiences.router)
app.include_router(applications.router)
app.include_router(tailor.router)
app.include_router(export.router)
app.include_router(rules.router)
app.include_router(auth.router)


@app.get("/")
async def root():
    return {"name": "CV Tailor API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
