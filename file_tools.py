"""
file_tools.py — File I/O helpers for the autograder.

Handles: ZIP download, ZIP inspection, SQL extraction, DOCX parsing.
Extracted from autograde_tools.py; no grading logic lives here.
"""

import tempfile
import zipfile
import logging
from typing import List, Optional, Tuple

import requests

try:
    import docx  # python-docx
except ImportError:
    docx = None
    logging.warning("python-docx is not installed; DOCX grading will be limited.")

logger = logging.getLogger(__name__)

# ============================================================
# ZIP / DOWNLOAD HELPERS
# ============================================================

def download_file(url: str) -> Optional[str]:
    if not url:
        return None
    local = tempfile.mktemp()
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception as e:
        logger.warning(f"Download failed: {e}")
        return None

def inspect_zip_extensions(zip_path: Optional[str]) -> List[str]:
    if not zip_path:
        return []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            exts = []
            for name in z.namelist():
                if "." in name:
                    exts.append(name.split(".")[-1].lower())
            return exts
    except Exception:
        return []

def extract_sql_from_zip(zip_path: Optional[str]) -> str:
    if not zip_path:
        return ""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".sql"):
                    return z.open(name).read().decode(errors="ignore")
    except Exception:
        pass
    return ""

# ============================================================
# DOCX HELPERS
# ============================================================

def _extract_docx_from_zip(zip_path: str) -> Tuple[str, int]:
    """
    Return (text, image_count) from the FIRST .docx in the ZIP.
    If python-docx not available or parsing fails, returns ("", 0).
    """
    if not docx:
        return "", 0

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".docx"):
                    tmp_path = tempfile.mktemp(suffix=".docx")
                    with z.open(name) as src, open(tmp_path, "wb") as dst:
                        dst.write(src.read())
                    d = docx.Document(tmp_path)
                    text = "\n".join(p.text for p in d.paragraphs)
                    image_count = len(d.inline_shapes)
                    return text, image_count
    except Exception as e:
        logger.warning(f"Error extracting DOCX from ZIP: {e}")

    return "", 0

def _count_nonempty_paragraphs(doc_text: str) -> int:
    lines = [ln.strip() for ln in (doc_text or "").split("\n")]
    nonempty = [ln for ln in lines if ln]
    return len(nonempty)
