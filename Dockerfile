FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic (self-contained LaTeX compiler)
RUN curl -fsSL \
    'https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz' \
    | tar xz -C /usr/local/bin

# Pre-warm Tectonic: compile a doc using the exact packages from the resume
# template so they are downloaded and cached inside the image. This ensures
# the first real PDF compile is ~3-5s instead of ~30s+.
RUN printf '%s\n' \
    '\documentclass[letterpaper,11pt]{article}' \
    '\usepackage[T1]{fontenc}' \
    '\usepackage[utf8]{inputenc}' \
    '\usepackage{latexsym}' \
    '\usepackage[empty]{fullpage}' \
    '\usepackage{titlesec}' \
    '\usepackage{marvosym}' \
    '\usepackage[usenames,dvipsnames]{color}' \
    '\usepackage{verbatim}' \
    '\usepackage{enumitem}' \
    '\usepackage[hidelinks]{hyperref}' \
    '\usepackage{fancyhdr}' \
    '\usepackage[english]{babel}' \
    '\usepackage{tabularx}' \
    '\begin{document}warmup\end{document}' \
    > /tmp/warmup.tex \
    && tectonic /tmp/warmup.tex --outdir /tmp \
    && rm -f /tmp/warmup.*

WORKDIR /app

# Copy source and install Python deps
COPY backend/ ./backend/
COPY migrations/ ./migrations/

RUN pip install --no-cache-dir -e ./backend

EXPOSE 8000

# On startup: run DB migrations then launch the API server
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
