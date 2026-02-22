"""Server-side LaTeX → PDF compilation using Tectonic.

Tectonic is a single-binary LaTeX engine that downloads packages on demand
from CTAN and caches them locally. Install on Render via the build command.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# First compile downloads packages (~20s). Subsequent compiles on same dyno
# use the local cache and finish in ~3-5s.
_TIMEOUT_SECONDS = 120


async def compile_latex_to_pdf(latex_content: str) -> bytes:
    """Compile LaTeX source to PDF bytes using Tectonic.

    Raises:
        FileNotFoundError: Tectonic binary not found — not installed on this server.
        RuntimeError: Compilation failed or timed out.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "cv.tex"
        tex_path.write_text(latex_content, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                "tectonic",
                "--keep-logs",
                "--outdir", tmpdir,
                str(tex_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                "Tectonic is not installed on this server. "
                "Add tectonic to the Render build command to enable PDF export."
            )

        try:
            _stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("PDF compilation timed out after 120 seconds")

        if proc.returncode != 0:
            logger.error("Tectonic compilation failed:\n%s", stderr.decode(errors="replace"))
            raise RuntimeError("PDF compilation failed")

        pdf_path = Path(tmpdir) / "cv.pdf"
        if not pdf_path.exists():
            raise RuntimeError("PDF output not found after compilation")

        return pdf_path.read_bytes()
