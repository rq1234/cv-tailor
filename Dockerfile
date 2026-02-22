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

# Pre-warm Tectonic: compile a doc that uses common resume packages so they
# get downloaded and cached inside the image. This means the first real PDF
# compile on EC2 is ~3-5s instead of ~30s.
RUN printf '%s\n' \
    '\documentclass[letterpaper,11pt]{article}' \
    '\usepackage{geometry}' \
    '\usepackage{enumitem}' \
    '\usepackage{hyperref}' \
    '\usepackage{fontawesome5}' \
    '\usepackage{multicol}' \
    '\usepackage{tabularx}' \
    '\usepackage{titlesec}' \
    '\usepackage{xcolor}' \
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
