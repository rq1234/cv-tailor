"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from backend.api.routes import applications, cv, experiences, export, rules, tailor  # noqa: E402

settings = get_settings()

app = FastAPI(title="CV Tailor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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


@app.get("/")
async def root():
    return {"name": "CV Tailor API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
