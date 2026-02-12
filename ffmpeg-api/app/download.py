"""
Safe HTTP/HTTPS download for URL-based mux input.
Only allows http:// and https://; enforces timeout and max size.
"""

from pathlib import Path

# Defaults (can be overridden by env if needed later)
DOWNLOAD_TIMEOUT = 300  # seconds
DOWNLOAD_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


def _allowed_scheme(url: str) -> bool:
    url_lower = url.strip().lower()
    return url_lower.startswith("http://") or url_lower.startswith("https://")


def _infer_extension_from_url(url: str, default: str) -> str:
    """Infer file extension from URL path. Returns default if unsafe or missing."""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)
        if not path or path == "/":
            return default
        # Take last path segment and its extension
        name = path.rstrip("/").split("/")[-1]
        if "." in name:
            ext = "." + name.rsplit(".", 1)[1].lower()
            # Only allow known safe extensions
            if ext in {".mp4", ".mov", ".m4v", ".webm", ".mp3", ".m4a", ".wav", ".aac"}:
                return ext
    except Exception:
        pass
    return default


def download_url_to_path(
    url: str,
    local_path: str,
    timeout: int = DOWNLOAD_TIMEOUT,
    max_bytes: int = DOWNLOAD_MAX_BYTES,
    default_extension: str = ".bin",
) -> None:
    """
    Download from URL to local file. Only http/https allowed.
    Raises ValueError for invalid URL or scheme; RuntimeError on timeout/size/HTTP error.
    """
    if not _allowed_scheme(url):
        raise ValueError("URL must use http:// or https://")

    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required for URL downloads")

    path = Path(local_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as resp:
        resp.raise_for_status()
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise RuntimeError(f"Content length {content_length} exceeds max {max_bytes}")

        written = 0
        with open(path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                written += len(chunk)
                if written > max_bytes:
                    f.close()
                    path.unlink(missing_ok=True)
                    raise RuntimeError(f"Download exceeded max size ({max_bytes} bytes)")
                f.write(chunk)
