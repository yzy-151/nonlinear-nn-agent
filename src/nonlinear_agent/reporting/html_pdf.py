"""HTML -> PDF via headless Edge (Chromium) on Windows."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path


EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def html_to_pdf(html_path: Path, pdf_path: Path, timeout_seconds: float = 60.0) -> Path:
    """Render an HTML file to PDF with headless Edge."""
    edge = next((p for p in EDGE_CANDIDATES if Path(p).exists()), None)
    if edge is None:
        raise RuntimeError("Microsoft Edge not found; cannot render HTML to PDF.")
    # 独立 user-data-dir：避免被已运行的 Edge GUI 实例劫持 headless 命令
    profile = tempfile.mkdtemp(prefix="edge-pdf-profile-")
    pdf_path.unlink(missing_ok=True)
    try:
        process = subprocess.run(
            [
                edge,
                "--headless",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--no-pdf-header-footer",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}",
                str(html_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        # Edge 返回时文件可能尚未落盘。profile 必须活到写入完成，
        # 否则并发测试中会出现 returncode=0 但 PDF 不存在的竞争。
        deadline = time.time() + 15
        last_size = -1
        stable_since: float | None = None
        while time.time() < deadline:
            size = pdf_path.stat().st_size if pdf_path.exists() else 0
            if size > 0 and size == last_size:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= 0.75:
                    break
            else:
                last_size = size
                stable_since = None
            time.sleep(0.2)
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise RuntimeError(
                f"Edge failed to produce PDF: returncode={process.returncode}; "
                f"stderr={process.stderr[-800:]}"
            )
        return pdf_path
    finally:
        import shutil

        shutil.rmtree(profile, ignore_errors=True)
